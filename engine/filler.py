# -*- coding: utf-8 -*-
"""报告内容生成引擎。

generate_report(): 按模板结构 + 课程知识库（可选叠加 LLM）自动补全报告。
regenerate_task()/rerun_task(): 交互式重新生成/重新运行某一题。
"""
import os
import re

from . import courses, llm
from .docmodel import FILLABLE_KEYS
from .render import render_code_png, find_gcc
from .runner import run_c_program


def _code_groups_of_section(td, sec_key):
    """提取模板"实验内容"里给出的代码段（连续的 程序 样式段落）。"""
    sc = td.scan()
    groups = []
    cur = []
    for b in sc['blocks']:
        if b['section'] == sec_key and b['kind'] == 'p':
            if b['style'] in ('程序', 'Code', '代码'):
                cur.append(b['text'])
                continue
        if cur:
            groups.append('\n'.join(cur))
            cur = []
    if cur:
        groups.append('\n'.join(cur))
    return groups


def _generic_c_code(task_text):
    return f'''#include <stdio.h>
int main()
{{
    /* 任务：{task_text[:40]} */
    printf("任务完成：{task_text[:30]}\\n");
    return 0;
}}'''


def _section_has_content(td, key):
    """判断章节里是否已有非空内容（用于“只增不删”：已有内容不重写）。"""
    s = td._section_range(key)
    if not s:
        return False
    sc = td.scan()
    for i in range(s['start'], min(s['end'], len(sc['blocks']))):
        b = sc['blocks'][i]
        if b['kind'] == 'tbl':
            return True
        if b['kind'] == 'p' and b['text'].strip():
            return True
    return False


def _section_texts(td, key):
    """读取章节内已有文本段落（跳过空段）。"""
    s = td._section_range(key)
    if not s:
        return []
    sc = td.scan()
    out = []
    for i in range(s['start'], min(s['end'], len(sc['blocks']))):
        b = sc['blocks'][i]
        if b['kind'] == 'p' and b['text'].strip():
            out.append(b['text'])
    return out


def generate_report(td, opts):
    """主入口。opts: workdir, profile, requirement, course, exp_name,
    use_llm, cfg, run_programs, assets(用户上传的图片路径列表)
    返回 {'course', 'summary':[str], 'images':int}
    """
    workdir = opts['workdir']
    art = os.path.join(workdir, 'artifacts')
    os.makedirs(art, exist_ok=True)
    sc = td.scan(refresh=True)
    profile = opts.get('profile') or {}
    requirement = opts.get('requirement') or ''
    cfg = opts.get('cfg') or {}
    use_llm = llm.ready(cfg) and opts.get('use_llm', True)
    summary = []
    img_count = 0

    exp_name = (profile.get('exp_name')
                or sc['fields'].get('exp_name', {}).get('value', '')
                or opts.get('exp_name') or '')
    course = opts.get('course') or courses.guess_course(
        requirement, exp_name + ' ' + (opts.get('template_name') or ''))

    # ---------- 1. 页眉/表单字段 ----------
    filled = 0
    for key in FILLABLE_KEYS:
        val = profile.get(key)
        if val and str(val).strip():
            ok, err = td.set_field(key, str(val).strip())
            if ok:
                filled += 1
    summary.append(f'已填写信息字段 {filled} 项（姓名/学号/学院等）')

    assets = list(opts.get('assets') or [])

    # ---------- 2. 按课程填充 ----------
    if course == 'drawing':
        img_count = _fill_drawing(td, opts, sc, exp_name, requirement, assets,
                                  use_llm, cfg, art, summary)
    else:
        img_count = _fill_c(td, opts, sc, exp_name, requirement, use_llm,
                            cfg, art, summary)
    return {'course': course, 'summary': summary, 'images': img_count}


# =====================================================================
# C 语言课程
# =====================================================================

def _fill_c(td, opts, sc, exp_name, requirement, use_llm, cfg, art, summary):
    workdir = opts['workdir']
    runnable = bool(opts.get('run_programs', True)) and bool(find_gcc())
    if not find_gcc():
        summary.append('⚠ 未检测到 gcc：将插入代码截图，运行结果需你批准后配置或手动截图')
    tasks = [t for t in sc['tasks'] if t['text']]
    if not tasks:
        t = re.sub(r'\s+', ' ', requirement.strip() or exp_name or '本次实验')
        tasks = [{'no': '1', 'text': t, 'block_idx': -1}]
        summary.append('模板里没有识别到（1）（2）…任务，已按实验要求生成单题')
    code_groups = _code_groups_of_section(td, 'content')
    img_count = 0

    blocks = []
    task_records = []
    for i, task in enumerate(tasks):
        no = task['no'] or str(i + 1)
        text = task['text']
        hint = code_groups[i] if i < len(code_groups) else ''
        kb = courses.match_c_code(text)
        code = ''
        if use_llm:
            try:
                code = llm.generate_code(cfg, text, 'c', template_hint=hint)
                summary.append(f'第（{no}）题代码由 LLM 生成')
            except Exception as e:
                summary.append(f'第（{no}）题 LLM 生成失败（{e}），改用内置知识库')
        if not code:
            if hint and re.search(r'运行|说明|结果', text):
                code = hint                     # 模板已给出程序 → 直接用
            elif kb:
                code = kb['code']
            else:
                code = _generic_c_code(text)
        png_code = os.path.join(art, f'code_{i + 1}.png')
        render_code_png(code, png_code)
        blocks.append({'type': 'text', 'text': f'（{no}）', 'style': '标题4'})
        blocks.append({'type': 'image', 'path': png_code})
        img_count += 1
        rec = {'no': no, 'text': text, 'code': code,
               'code_png': png_code, 'console_png': None}

        if runnable:
            r = run_c_program(code, (kb or {}).get('stdin', ''),
                              os.path.join(workdir, 'src'), name=f'task{no}')
            if r.get('ok'):
                if r.get('png'):
                    blocks.append({'type': 'image', 'path': r['png'],
                                   'caption': None})
                    img_count += 1
                    rec['console_png'] = r['png']
                if r.get('timed_out'):
                    blocks.append({'type': 'text',
                                   'text': '（程序等待输入，运行超时已终止）'})
            else:
                summary.append(f'第（{no}）题程序未能运行：{r.get("reason")}'
                               + (f' {r.get("compile_log", "")[:120]}'
                                  if r.get('compile_log') else ''))
        # 问答题（"说明什么"）补一句结论
        if re.search(r'说明什么|为什么|试问|回答|？|\?', text):
            ans = (kb or {}).get('explain')
            if not ans and use_llm:
                try:
                    ans = llm.chat(cfg, [
                        {'role': 'system', 'content': '用一两句话直接回答实验问题，口语化、第一人称。'},
                        {'role': 'user', 'content': text}], max_tokens=300)
                except Exception:
                    ans = None
            if ans:
                blocks.append({'type': 'text', 'text': '答：' + ans.strip()})
        task_records.append(rec)

    if _section_has_content(td, 'steps_result'):
        summary.append('第3节已有内容 —— 按「只增不删」原则本次未改动；'
                       '如需重写请先在聊天里发「清空第3节」')
    else:
        target = None
        for key in ('steps_result', 'result'):
            if td._section_range(key):
                td.clear_section(key)
                target = key
                break
        if target is None:
            summary.append('⚠ 模板中没有"实验步骤和实验结果"章节，内容将追加到文档末尾')
            target = 'steps_result'
        ok, added = td.append_blocks(target, blocks)
        summary.append(f'第3节（实验步骤和实验结果）：已写入 {len(tasks)} 题，'
                       f'插入 {img_count} 张图片（代码截图 + 运行结果截图）')

    # ---------- 分析与讨论（已有内容不重写） ----------
    if td._section_range('analysis'):
        if _section_has_content(td, 'analysis'):
            summary.append('第4节已有内容 —— 未改动（只增不删）；'
                           '重写可发「重写分析与讨论」')
            paras = _section_texts(td, 'analysis')
        else:
            paras = None
            if use_llm:
                try:
                    paras = llm.generate_analysis(
                        cfg, exp_name or 'C语言实验',
                        [t['text'] for t in tasks],
                        style_hint='\n'.join(courses.c_analysis_paragraphs(exp_name)))
                except Exception as e:
                    summary.append(f'LLM 生成分析与讨论失败（{e}），改用内置模板')
            if not paras:
                paras = courses.c_analysis_paragraphs(exp_name)
            td.append_blocks('analysis',
                             [{'type': 'text', 'text': p} for p in paras if p.strip()])
            summary.append(f'第4节（分析与讨论）：已写入 {len(paras)} 段')
    else:
        paras = None
        summary.append('模板中没有"分析与讨论"章节，跳过')
    _save_task_records(workdir, task_records, paras or [])
    return img_count


def _save_task_records(workdir, records, analysis_paras):
    import json
    meta = {'tasks': records, 'analysis': analysis_paras}
    with open(os.path.join(workdir, 'meta_tasks.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_task_records(workdir):
    import json
    p = os.path.join(workdir, 'meta_tasks.json')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'tasks': [], 'analysis': []}


def _find_task_images(td, no):
    """在 steps_result 节里找到（no）标记后的图片块索引列表。"""
    sc = td.scan()
    zone = None
    for key in ('steps_result', 'result', 'steps'):
        for s in sc['sections']:
            if s['key'] == key:
                zone = s
                break
        if zone:
            break
    if not zone:
        return None, []
    blocks = sc['blocks']
    in_task = False
    found_text = None
    imgs = []
    for i in range(zone['start'], min(zone['end'], len(blocks))):
        b = blocks[i]
        if b['kind'] == 'p' and re.match(rf'^（\s*{re.escape(no)}\s*）$', b['text'].strip()):
            in_task = True
            found_text = i
            continue
        if in_task:
            if b['kind'] == 'p' and re.match(r'^（\s*\d+\s*）$', b['text'].strip()):
                break
            if b['images']:
                imgs.append(i)
    return found_text, imgs


def regenerate_task(td, opts, no, use_llm=True, variant_note=''):
    """重新生成第 no 题的代码截图并替换；随后尝试重新运行替换结果图。"""
    import json
    workdir = opts['workdir']
    art = os.path.join(workdir, 'artifacts')
    os.makedirs(art, exist_ok=True)
    cfg = opts.get('cfg') or {}
    meta = load_task_records(workdir)
    rec = next((t for t in meta['tasks'] if t['no'] == str(no)), None)
    if not rec:
        return False, f'没有找到第（{no}）题的记录'
    code = None
    kb = courses.match_c_code(rec['text'])
    if use_llm and llm.ready(cfg):
        try:
            code = llm.generate_code(
                cfg, rec['text'] + (' 要求：换一种实现思路。' + variant_note if variant_note else ''),
                'c', template_hint=(kb or {}).get('code', ''))
        except Exception as e:
            pass
    if not code and kb:
        code = kb['code']
    if not code:
        code = _generic_c_code(rec['text'])
    png = os.path.join(art, f'code_{no}_v{int(time.time()) % 100000}.png')
    render_code_png(code, png)
    _, imgs = _find_task_images(td, str(no))
    if imgs:
        td.replace_image(imgs[0], png)
    else:
        td.append_blocks('steps_result',
                         [{'type': 'image', 'path': png}])
    rec['code'] = code
    rec['code_png'] = png
    # 重新运行替换结果图
    if find_gcc() and opts.get('run_programs', True):
        r = run_c_program(code, (kb or {}).get('stdin', ''),
                          os.path.join(workdir, 'src'), name=f'task{no}')
        if r.get('ok') and r.get('png'):
            if len(imgs) > 1:
                td.replace_image(imgs[-1], r['png'])
            else:
                td.append_blocks('steps_result',
                                 [{'type': 'image', 'path': r['png']}])
            rec['console_png'] = r['png']
    meta['tasks'] = [t if t['no'] != str(no) else rec for t in meta['tasks']]
    with open(os.path.join(workdir, 'meta_tasks.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return True, f'第（{no}）题已重新生成' + ('并重新运行' if rec.get('console_png') else '')


import time  # noqa: E402  (regenerate_task 里用到)


def rerun_task(td, opts, no):
    """重新编译运行第 no 题并替换/插入运行结果截图。"""
    import json
    workdir = opts['workdir']
    meta = load_task_records(workdir)
    rec = next((t for t in meta['tasks'] if t['no'] == str(no)), None)
    if not rec:
        return False, f'没有找到第（{no}）题的记录'
    kb = courses.match_c_code(rec['text'])
    if not find_gcc():
        return False, '未找到 gcc 编译器，无法运行'
    r = run_c_program(rec['code'], (kb or {}).get('stdin', ''),
                      os.path.join(workdir, 'src'), name=f'task{no}')
    if not r.get('ok'):
        return False, r.get('reason', '运行失败')
    if not r.get('png'):
        return False, '程序没有输出内容'
    _, imgs = _find_task_images(td, str(no))
    if len(imgs) > 1:
        td.replace_image(imgs[-1], r['png'])
    elif imgs:
        td.insert_image_after(imgs[0], r['png'])
    else:
        td.append_blocks('steps_result', [{'type': 'image', 'path': r['png']}])
    return True, f'第（{no}）题已重新运行并更新结果截图'


# =====================================================================
# 工程制图课程
# =====================================================================

def _fill_drawing(td, opts, sc, exp_name, requirement, assets, use_llm, cfg,
                  art, summary):
    exp = courses.match_drawing_exp(
        (exp_name or '') + ' ' + requirement + ' ' + (opts.get('template_name') or ''))
    steps = courses.drawing_step_items(exp['steps'])
    img_count = 0
    blocks = []
    asset_idx = 0
    n = len(steps)
    for m, (title, text) in enumerate(steps):
        blocks.append({'type': 'text', 'text': f'1.{m + 1}、{title}：'})
        blocks.append({'type': 'text', 'text': '步骤：' + text})
        blocks.append({'type': 'text', 'text': '截图：'})
        if asset_idx < len(assets):
            blocks.append({'type': 'image', 'path': assets[asset_idx]})
            img_count += 1
            asset_idx += 1
    ok = td._section_range('steps_result') or td._section_range('steps')
    if ok:
        key = 'steps_result' if td._section_range('steps_result') else 'steps'
        if _section_has_content(td, key):
            summary.append('三、实验步骤已有内容 —— 按「只增不删」原则未改动；'
                           '如需重写请发「清空实验步骤」')
        else:
            td.clear_section(key)
            td.append_blocks(key, blocks)
            summary.append(f'三、实验步骤：已写入 {n} 个步骤'
                           + (f'，自动插入 {img_count} 张过程截图' if img_count else
                              '（截图位已留好，可上传截图后用聊天插入）'))
    else:
        summary.append('⚠ 未找到"实验步骤"章节')
    # 其余素材放到实验结果
    if td._section_range('result'):
        if _section_has_content(td, 'result'):
            summary.append('四、实验结果已有内容 —— 按「只增不删」原则未改动')
        else:
            res_blocks = [{'type': 'text', 'text': '完整截图'}]
            rest = assets[asset_idx:]
            for p in rest:
                res_blocks.append({'type': 'image', 'path': p})
                img_count += 1
            res_blocks.append({'type': 'text', 'text': courses.DRAWING_RESULT_NOTE})
            td.clear_section('result')
            td.append_blocks('result', res_blocks)
            summary.append('四、实验结果：已写入完整截图与提交说明')
    # 若模板带"分析与讨论"
    if td._section_range('analysis'):
        if _section_has_content(td, 'analysis'):
            summary.append('分析与讨论已有内容 —— 按「只增不删」原则未改动')
        else:
            paras = [
                '通过本次实验，我掌握了 AutoCAD 图层的建立与切换方法，理解了不同线型（粗实线、细点画线、虚线）必须放在对应图层上管理的原因。',
                '在使用修改命令（偏移、修剪、阵列）时体会到：先画基准中心线、再利用对象捕捉精确定位，能显著提高绘图效率和准确度。',
                '环形阵列时必须先指定阵列中心与项目数，再选择对象；修剪命令要先选边界再选择要剪掉的线段，操作顺序不能颠倒。',
                '尺寸标注前应先设置符合国标的标注样式（ISO），标注文字、箭头大小要合适，图面才能清晰规范。',
            ]
            td.clear_section('analysis')
            td.append_blocks('analysis', [{'type': 'text', 'text': p} for p in paras])
            summary.append('分析与讨论：已写入 4 段心得')
    return img_count
