# -*- coding: utf-8 -*-
"""docx 模板解析与编辑核心。

负责：
- 解析模板：正文块顺序、页眉/正文中的信息字段（姓名/学号/学院...）、
  一级章节（实验目的/内容/步骤/分析...）与每节可填写区域、任务条目（（1）（2）...）
- 编辑操作：填写字段、替换段落文本、清空/追加章节内容、插入图片、删除段落
- 保存：保留模板原有样式（标题4/程序/Heading4 等），直接在模板副本上修改
"""
import copy
import os
import re

from docx import Document
from docx.document import Document as _Doc
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Emu
from docx.table import Table
from docx.text.paragraph import Paragraph

# ---------------------------------------------------------------- 字段定义

# 标签候选（长词在前，避免 "实验（实习）日期" 被 "日期" 抢先匹配）
_LABEL_PAT = re.compile(
    r'实验（实习）名称|实验（实习）日期|实验名称|指导教师|指导老师|学院|专业|年级|班次|姓名|学号|日期|得分'
)
_LABEL2KEY = {
    '实验（实习）名称': 'exp_name', '实验名称': 'exp_name',
    '实验（实习）日期': 'date', '日期': 'date',
    '指导教师': 'teacher', '指导老师': 'teacher',
    '学院': 'college', '专业': 'major', '年级': 'grade', '班次': 'class',
    '姓名': 'student_name', '学号': 'sid', '得分': 'score',
}
FILLABLE_KEYS = ['exp_name', 'date', 'teacher', 'college', 'major', 'grade',
                 'class', 'student_name', 'sid']
FIELD_LABELS_ZH = {
    'exp_name': '实验名称', 'date': '实验日期', 'teacher': '指导教师',
    'college': '学院', 'major': '专业', 'grade': '年级', 'class': '班次',
    'student_name': '姓名', 'sid': '学号', 'score': '得分',
}

_HEADING_STYLE_PAT = re.compile(r'(标题|Heading)\s*\d', re.I)
_CN_NUM_PAT = re.compile(r'^[一二三四五六七八九十]+\s*、\s*\S')
_SECTION_PAT = re.compile(r'^\d+\s*[．.]\s*\S')
_TASK_PAT = re.compile(r'^（([0-9一二三四五六七八九十]+)）')

# 章节关键词 → 归一化 id（用于后续定位填充位置）
_SECTION_KEYS = [
    ('purpose', ('实验目的', '目的')),
    ('content', ('实验内容', '内容与要求', '内容')),
    ('steps_result', ('实验步骤和实验结果', '实验步骤与结果', '步骤和实验结果',
                      '实验步骤', '实验过程')),
    ('result', ('实验结果', '结果')),
    ('analysis', ('分析与讨论', '分析讨论', '讨论', '心得体会', '心得', '总结')),
]


def _norm_section(title):
    t = title.replace(' ', '').replace('　', '')
    for key, words in _SECTION_KEYS:
        for w in words:
            if w in t:
                return key
    return None


def _iter_blocks(doc):
    """按文档顺序产出 ('p', Paragraph) / ('t', Table)。"""
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn('w:p'):
            yield 'p', Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            yield 't', Table(child, doc)


def _run_rpr(run):
    rPr = run._element.rPr
    return copy.deepcopy(rPr) if rPr is not None else None


def _clear_runs(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def _add_run(p, text, rpr=None):
    r = p.add_run(text)
    if rpr is not None:
        r._element.insert(0, copy.deepcopy(rpr))
    return r


def replace_span(p, start, end, new_text):
    """把段落 p 中 [start,end) 的文本替换为 new_text，尽量保留原 run 格式。"""
    pos = 0
    inserted = False
    last_rpr = None
    for r in p.runs:
        t = r.text or ''
        rs, re_ = pos, pos + len(t)
        pos = re_
        if r.text:
            last_rpr = _run_rpr(r)
        if re_ <= start or rs >= end:
            continue
        head = t[:max(0, start - rs)]
        tail = t[max(0, min(len(t), end - rs)):]
        if not inserted:
            r.text = head + new_text + tail
            inserted = True
        else:
            r.text = head + tail
    if not inserted:  # 区间超出所有 run（罕见）：追加一个 run
        _add_run(p, new_text, last_rpr)
    return inserted


# ---------------------------------------------------------------- 解析

def scan_doc(doc):
    """返回文档结构快照。

    {
      'fields': {key: {'scope','block_idx','start','end','value','label'}},
      'blocks': [ {idx,kind,style,text,align,images,heading,task_no,section} ],
      'sections': [ {'idx','title','key','start','end'} ],   # 一级章节
      'tasks': [ {'no','text','block_idx'} ],                # 实验内容中的任务
    }
    """
    fields = {}
    blocks = []

    # ---- 页眉字段（含首页页眉），用稳定的位置三元组定位
    header_paras_scan = []   # [(pos, para, text)]

    for si, sec in enumerate(doc.sections):
        kinds = [('header', sec.header)]
        if sec.different_first_page_header_footer:
            kinds.append(('first', sec.first_page_header))
        for kind, hdr in kinds:
            if hdr is None:
                continue
            for pi, p in enumerate(hdr.paragraphs):
                header_paras_scan.append(((si, kind, pi), p, p.text))

    def parse_header_fields():
        for pos, p, text in header_paras_scan:
            if not text:
                continue
            found = []
            for m in _LABEL_PAT.finditer(text):
                key = _LABEL2KEY.get(m.group(0))
                if key and key not in [k for _, k, _ in found]:
                    found.append((m.start(), key, m.end()))
            for i, (ls, key, le) in enumerate(found):
                nxt = found[i + 1][0] if i + 1 < len(found) else len(text)
                region = text[le:nxt]
                if key in fields:      # 每个字段只取第一次出现（值里可能含"学院"等字样）
                    continue
                fields[key] = {
                    'scope': 'header', 'pos': pos, 'label': text[ls:le],
                    'start': le, 'end': nxt,
                    'value': region.strip(), 'raw_region': region,
                }

    parse_header_fields()
    # ---- 正文块 + 正文中的表单字段（工程制图模板在正文里填信息）
    idx = 0
    cur_section = None
    sections = []
    for kind, obj in _iter_blocks(doc):
        if kind == 'p':
            text = obj.text
            style = obj.style.name if obj.style is not None else 'Normal'
            images = []
            for blip in obj._element.iter(qn('a:blip')):
                rid = blip.get(qn('r:embed'))
                if rid:
                    images.append(rid)
            is_h1 = False
            # 表单行（一行里有 ≥2 个信息标签）不算章节标题
            n_labels = len({m.group(0) for m in _LABEL_PAT.finditer(text)})
            form_like = n_labels >= 2 and len(text) < 120
            if _HEADING_STYLE_PAT.search(style) and not _TASK_PAT.match(text.strip()) \
                    and not re.match(r'^\d+\.\d+', text.strip()) and not form_like:
                is_h1 = True
            elif _CN_NUM_PAT.match(text.strip()) and len(text.strip()) <= 24:
                is_h1 = True
            task_no = None
            tm = _TASK_PAT.match(text.strip())
            if tm:
                task_no = tm.group(1)
            blk = {'idx': idx, 'kind': 'p', 'style': style, 'text': text,
                   'align': int(obj.alignment) if obj.alignment is not None else None,
                   'images': images, 'heading': is_h1, 'task_no': task_no,
                   'section': cur_section['key'] if cur_section else None,
                   '_obj': obj}
            # 正文表单字段（仅短行，形如"学号  xxx 姓名 xxx"，且页眉里没有时）
            if not cur_section and len(text) < 120:
                found = []
                for m in _LABEL_PAT.finditer(text):
                    key = _LABEL2KEY.get(m.group(0))
                    if key and key not in fields and \
                            key not in [k for _, k, _ in found]:
                        found.append((m.start(), key, m.end()))
                for i, (ls, key, le) in enumerate(found):
                    nxt = found[i + 1][0] if i + 1 < len(found) else len(text)
                    region = text[le:nxt]
                    fields[key] = {'scope': 'body', 'block_idx': idx,
                                   'label': text[ls:le], 'start': le,
                                   'end': nxt, 'value': region.strip(),
                                   'raw_region': region}
            blocks.append(blk)
            if is_h1:
                key = _norm_section(text)
                cur_section = {'idx': idx, 'title': text.strip(), 'key': key,
                               'start': idx + 1, 'end': idx + 1}
                sections.append(cur_section)
            elif cur_section is not None:
                cur_section['end'] = idx + 1
        else:  # table
            rows = []
            for row in obj.rows:
                rows.append([c.text for c in row.cells])
            blocks.append({'idx': idx, 'kind': 'tbl', 'style': obj.style.name if obj.style else '',
                           'rows': rows, 'text': '', 'images': [], 'heading': False,
                           'task_no': None,
                           'section': cur_section['key'] if cur_section else None,
                           '_obj': obj})
            if cur_section is not None:
                cur_section['end'] = idx + 1
        idx += 1

    # 正文表单字段需要记录所属 block 引用，供编辑时定位
    # （header 字段用位置三元组定位）
    tasks = [{'no': b['task_no'], 'text': b['text'].strip(),
              'block_idx': b['idx']}
             for b in blocks if b['task_no'] and b['section'] in ('content', None)
             and b['kind'] == 'p']
    # 任务也允许出现在"步骤与结果"节（如模板已给出（1）（2）锚点）
    if not tasks:
        tasks = [{'no': b['task_no'], 'text': b['text'].strip(),
                  'block_idx': b['idx']}
                 for b in blocks if b['task_no'] and b['kind'] == 'p']

    return {'fields': fields, 'blocks': blocks, 'sections': sections,
            'tasks': tasks,
            'header_lines': [{'pos': pos, 'text': t}
                              for pos, _, t in header_paras_scan if t.strip()]}


class TemplateDoc:
    """在模板副本上执行编辑操作。所有 op 都以“当前文档最新 scan”为准。"""

    def __init__(self, template_path):
        self.template_path = template_path
        self.doc = Document(template_path)
        self.scan_cache = None

    # ---------- 基础 ----------
    def scan(self, refresh=False):
        if self.scan_cache is None or refresh:
            self.scan_cache = scan_doc(self.doc)
        return self.scan_cache

    def save(self, out_path):
        self.doc.save(out_path)

    def _find_header_para(self, pos):
        """按 (section序号, header/first, 段落序号) 定位页眉段落。"""
        si, kind, pi = pos
        try:
            sec = self.doc.sections[si]
        except IndexError:
            return None
        hdr = sec.first_page_header if kind == 'first' else sec.header
        if hdr is None:
            return None
        try:
            return hdr.paragraphs[pi]
        except IndexError:
            return None

    def _find_body_para(self, block_idx):
        blk = self.scan()['blocks'][block_idx]
        return blk['_obj'] if blk['kind'] == 'p' else None

    # ---------- 字段 ----------
    def set_field(self, key, value):
        f = self.scan()['fields'].get(key)
        if not f:
            return False, f'模板中未找到字段“{FIELD_LABELS_ZH.get(key, key)}”'
        if f['scope'] == 'header':
            p = self._find_header_para(f['pos'])
        else:
            p = self._find_body_para(f.get('block_idx', -1))
        if p is None:
            return False, '字段所在段落定位失败'
        # 重新按当前文本定位（前面的 op 可能改过段落）
        text = p.text
        found = []
        for m in _LABEL_PAT.finditer(text):
            k = _LABEL2KEY.get(m.group(0))
            if k and k not in [x for _, x, _ in found]:
                found.append((m.start(), k, m.end()))
        target = None
        for i, (ls, k, le) in enumerate(found):
            if k == key:
                nxt = found[i + 1][0] if i + 1 < len(found) else len(text)
                target = (le, nxt)
                break
        if target is None:
            return False, '字段标签未匹配'
        le, nxt = target
        region = text[le:nxt]
        lead = len(region) - len(region.lstrip(' '))
        trail = len(region) - len(region.rstrip(' '))
        keep = max(2, (lead + trail) // 3)
        new_region = ' ' * keep + str(value) + ' ' * keep
        replace_span(p, le, nxt, new_region)
        self.scan_cache = None
        return True, None

    # ---------- 段落 ----------
    def set_paragraph(self, idx, text):
        p = self._find_body_para(idx)
        if p is None:
            return False, f'段落 {idx} 不存在或不是文本段'
        rpr = None
        for r in p.runs:
            if r.text:
                rpr = _run_rpr(r)
                break
        if rpr is None and p.runs:
            rpr = _run_rpr(p.runs[0])
        _clear_runs(p)
        _add_run(p, text, rpr)
        self.scan_cache = None
        return True, None

    def delete_block(self, idx):
        blk = self.scan()['blocks'][idx]
        obj = blk['_obj']
        obj._element.getparent().remove(obj._element)
        self.scan_cache = None
        return True, None

    # ---------- 章节填充 ----------
    def _section_range(self, key_or_title):
        sc = self.scan()
        target = None
        for s in sc['sections']:
            if (s['key'] and s['key'] == key_or_title) or s['title'] == key_or_title:
                target = s
                break
        if target is None:
            # 模糊匹配标题
            for s in sc['sections']:
                if key_or_title in s['title']:
                    target = s
                    break
        return target

    def _donor_paragraph(self, style_hint=None):
        """找一个可复用样式的正文段落作为新段落模板。"""
        sc = self.scan()
        candidates = []
        for b in sc['blocks']:
            if b['kind'] != 'p':
                continue
            candidates.append(b)
        # 优先：指定样式 → Normal → 第一个
        for want in ([style_hint] if style_hint else []) + ['Normal']:
            for b in candidates:
                if b['style'] == want and (b['text'].strip() or b['images']):
                    return b['_obj']
        return candidates[0]['_obj'] if candidates else None

    def _new_paragraph_like(self, donor, text=None, align=None):
        from docx.text.paragraph import Paragraph as _P
        if donor is None:
            from docx.oxml import OxmlElement
            p = OxmlElement('w:p')
            np = _P(p, self.doc)
        else:
            p = copy.deepcopy(donor._p)
            # 清掉内容（runs、图片），保留 pPr（样式/缩进/行距）
            for child in list(p):
                if child.tag != qn('w:pPr'):
                    p.remove(child)
            np = _P(p, donor._parent)
        if text:
            _add_run(np, text)
        if align is not None:
            np.alignment = align
        return np

    def _insert_paragraph(self, ref_paragraph, before=True, donor=None,
                          text=None, align=None):
        np = self._new_paragraph_like(donor or self._donor_paragraph(),
                                      text=text, align=align)
        if ref_paragraph is None:
            # 文档末尾：插到 body 的 sectPr 之前
            body = self.doc.element.body
            sect_pr = body.find(qn('w:sectPr'))
            if sect_pr is not None:
                sect_pr.addprevious(np._p)
            else:
                body.append(np._p)
        elif before:
            ref_paragraph._p.addprevious(np._p)
        else:
            ref_paragraph._p.addnext(np._p)
        return _ParagraphWrap(np, self)

    def clear_section(self, key_or_title, keep_heading=True):
        s = self._section_range(key_or_title)
        if not s:
            return False, f'未找到章节“{key_or_title}”'
        blocks = self.scan()['blocks']
        removed = 0
        for i in range(s['start'], min(s['end'], len(blocks))):
            blk = blocks[i]
            if blk['kind'] == 'p' and blk['heading']:
                continue
            obj = blk['_obj']
            obj._element.getparent().remove(obj._element)
            removed += 1
        self.scan_cache = None
        return True, removed

    def append_blocks(self, key_or_title, blocks):
        """向章节末尾追加内容块。

        blocks 元素：
          {'type':'text','text':..., 'style':'Normal'|'code'|'task', 'bold':bool}
          {'type':'image','path':..., 'width_in':float|None, 'caption':str|None}
          {'type':'code','text':...}          → 使用“程序”样式（若无则等宽观感由预览处理）
        """
        s = self._section_range(key_or_title)
        if not s:
            return False, f'未找到章节“{key_or_title}”'
        sc = self.scan()
        blocks_all = sc['blocks']
        # 章节末尾 = 下一章 heading 前；没有下一章则文档末尾
        end_i = min(s['end'], len(blocks_all))
        ref_obj = None
        if end_i < len(blocks_all) and blocks_all[end_i]['heading']:
            ref_obj = blocks_all[end_i]['_obj']
        added = []
        for spec in blocks:
            ttype = spec.get('type', 'text')
            if ttype in ('text', 'code', 'task', 'caption'):
                style_hint = spec.get('style') or {'code': '程序'}.get(ttype)
                text = spec.get('text', '')
                if ttype == 'caption':
                    align = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    align = None
                wrap = self._insert_paragraph(ref_obj, donor=self._donor_paragraph(style_hint),
                                              text=text, align=align)
                if spec.get('bold'):
                    for r in wrap.p.runs:
                        r.font.bold = True
                added.append(wrap.p.text)
            elif ttype == 'image':
                path = spec['path']
                if not os.path.exists(path):
                    added.append(f'[图片缺失:{path}]')
                    continue
                wrap = self._insert_paragraph(ref_obj, align=WD_ALIGN_PARAGRAPH.CENTER)
                width = spec.get('width_in')
                if not width:
                    width = _suggest_width(path)
                run = wrap.p.add_run()
                run.add_picture(path, width=Inches(width))
                added.append(f'[图片 {os.path.basename(path)}]')
                if spec.get('caption'):
                    self._insert_paragraph(ref_obj, text=spec['caption'],
                                           align=WD_ALIGN_PARAGRAPH.CENTER)
            elif ttype == 'images_row':
                for path in spec['paths']:
                    w = spec.get('width_in') or _suggest_width(path)
                    wrap = self._insert_paragraph(ref_obj, align=WD_ALIGN_PARAGRAPH.CENTER)
                    wrap.p.add_run().add_picture(path, width=Inches(w))
        self.scan_cache = None
        return True, added

    def insert_image_after(self, idx, path, width_in=None, caption=None):
        p = self._find_body_para(idx)
        if p is None:
            return False, f'段落 {idx} 不存在'
        wrap = self._insert_paragraph(p, before=False, align=WD_ALIGN_PARAGRAPH.CENTER)
        run = wrap.p.add_run()
        run.add_picture(path, width=Inches(width_in or _suggest_width(path)))
        if caption:
            self._insert_paragraph(p, before=False, text=caption,
                                   align=WD_ALIGN_PARAGRAPH.CENTER)
        self.scan_cache = None
        return True, None

    def replace_image(self, idx, path, width_in=None):
        """把某个含图段落里的图替换为 path 的图（重新截图场景）。"""
        p = self._find_body_para(idx)
        if p is None:
            return False, f'段落 {idx} 不存在'
        # 删除原有 drawing
        for d in p._element.findall(qn('w:r')):
            if d.findall(qn('w:drawing')):
                p._element.remove(d)
        run = p.add_run()
        run.add_picture(path, width=Inches(width_in or _suggest_width(path)))
        self.scan_cache = None
        return True, None


class _ParagraphWrap:
    def __init__(self, p, model):
        self.p = p
        self.model = model


def _suggest_width(path):
    """根据图片长宽比建议插入宽度（英寸）。竖长图（代码截图）窄一些。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        ratio = h / max(1, w)
        content = 6.3
        if ratio > 1.15:          # 竖图
            return min(5.2, content)
        if ratio < 0.45:          # 横长图
            return min(6.1, content)
        return min(5.7, content)
    except Exception:
        return 5.5
