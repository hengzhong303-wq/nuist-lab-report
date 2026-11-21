# -*- coding: utf-8 -*-
"""南信实验报告工坊 — 本地网站服务端（仅监听 127.0.0.1）。

零第三方依赖（除 python-docx / Pillow）：标准库 http.server 实现。
"""
import json
import mimetypes
import os
import re
import shutil
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from docx import Document as _WordDoc

from engine import courses, convert, filler, intent, llm, preview, runner
from engine.docmodel import TemplateDoc, FIELD_LABELS_ZH

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, 'web')
DATA = os.path.join(BASE, 'data')
SESSIONS = os.path.join(DATA, 'sessions')
os.makedirs(SESSIONS, exist_ok=True)

MAX_BODY = 80 * 1024 * 1024


# =====================================================================
# 会话
# =====================================================================

class Session:
    def __init__(self, sid):
        self.sid = sid
        self.dir = os.path.join(SESSIONS, sid)
        self.lock = threading.RLock()
        self.ensure_dirs()
        self.meta = {
            'template_name': '', 'template_path': '', 'course': None,
            'profile': {}, 'requirement': '', 'chat': [], 'assets': [],
            'generated': False, 'created': time.time(),
        }
        self.pending = []      # 待批准命令
        self.history = []      # 已执行命令结果
        self.td = None
        self.rev = 1
        self._load_meta()

    # ---------- 路径 ----------
    @property
    def output_path(self):
        return os.path.join(self.dir, 'output.docx')

    def ensure_dirs(self):
        """确保会话目录结构存在（运行中被删也能自愈）。"""
        for sub in ('uploads', 'artifacts', os.path.join('files', 'img'), 'src'):
            os.makedirs(os.path.join(self.dir, sub), exist_ok=True)

    def meta_path(self):
        return os.path.join(self.dir, 'meta.json')

    def _load_meta(self):
        p = self.meta_path()
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    self.meta.update(json.load(f))
            except Exception:
                pass

    def save_meta(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.meta_path(), 'w', encoding='utf-8') as f:
            json.dump(self.meta, f, ensure_ascii=False)

    def bump(self):
        self.rev += 1
        self.save_meta()

    # ---------- 文档 ----------
    def get_td(self):
        with self.lock:
            if self.td is None:
                src = (self.output_path if self.meta['generated']
                       and os.path.exists(self.output_path)
                       else self.meta['template_path'])
                if not src or not os.path.exists(src):
                    return None
                self.td = TemplateDoc(src)
            return self.td

    def reset_template(self, path, name):
        with self.lock:
            self.meta['template_path'] = path
            self.meta['template_name'] = name
            self.meta['generated'] = False
            self.meta['course'] = None
            try:
                if os.path.exists(self.output_path):
                    os.remove(self.output_path)   # 换模板后，旧模板的报告立即作废
            except OSError:
                pass
            self.td = TemplateDoc(path)
            self.bump()

    def chat_add(self, role, text, extra=None):
        self.meta['chat'].append(
            {'role': role, 'text': text, 'ts': time.strftime('%H:%M:%S'),
             **(extra or {})})
        if len(self.meta['chat']) > 200:
            self.meta['chat'] = self.meta['chat'][-200:]


MANAGER = {'sessions': {}, 'mu': threading.Lock()}


def get_session(sid):
    if not re.match(r'^[\w\-]{1,40}$', sid or ''):
        sid = 'default'
    with MANAGER['mu']:
        s = MANAGER['sessions'].get(sid)
        if s is None:
            s = Session(sid)
            MANAGER['sessions'][sid] = s
        return s


# =====================================================================
# multipart 解析
# =====================================================================

def parse_multipart(body, content_type):
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        raise ValueError('缺少 multipart boundary')
    boundary = ('--' + m.group(1)).encode('utf-8')
    fields, files = {}, []
    for chunk in body.split(boundary):
        chunk = chunk.strip(b'\r\n-')
        if not chunk or chunk == b'--':
            continue
        if b'\r\n\r\n' not in chunk:
            continue
        head, content = chunk.split(b'\r\n\r\n', 1)
        head = head.decode('utf-8', 'replace')
        name = re.search(r'name="([^"]*)"', head)
        fname = re.search(r'filename="([^"]*)"', head)
        if fname and fname.group(1):
            files.append({'field': name.group(1) if name else 'file',
                          'filename': os.path.basename(fname.group(1)),
                          'content': content})
        elif name:
            fields[name.group(1)] = content.decode('utf-8', 'replace')
    return fields, files


# =====================================================================
# 业务逻辑
# =====================================================================

def _resolve_asset(sess, name):
    """按文件名在会话目录里找素材，返回绝对路径或 None。"""
    if not name:
        return None
    if os.path.isabs(name) and os.path.exists(name):
        return name
    for sub in ('uploads', 'artifacts', os.path.join('files', 'img')):
        d = os.path.join(sess.dir, sub)
        cand = os.path.join(d, name)
        if os.path.exists(cand):
            return cand
        # 模糊匹配前缀
        for fn in os.listdir(d):
            if fn.startswith(name[:12]) or name in fn:
                return os.path.join(d, fn)
    return None


def apply_ops(sess, ops):
    """执行文档操作。返回 (done:[str], errors:[str])"""
    td = sess.get_td()
    done, errors = [], []
    if td is None:
        return done, ['请先上传模板']
    for op in ops:
        try:
            kind = op.get('op')
            if kind == 'set_field':
                ok, err = td.set_field(op['field'], op.get('value', ''))
                done.append(f"字段 {FIELD_LABELS_ZH.get(op['field'], op['field'])} 已更新") if ok else errors.append(err)
            elif kind == 'set_paragraph':
                ok, err = td.set_paragraph(op['index'], op.get('text', ''))
                done.append(f"段落 {op['index']} 已修改") if ok else errors.append(err)
            elif kind == 'delete_block':
                ok, _ = td.delete_block(op['index'])
                done.append(f"段落 {op['index']} 已删除") if ok else errors.append('删除失败')
            elif kind == 'clear_section':
                ok, err = td.clear_section(op['section'])
                done.append('章节已清空') if ok else errors.append(str(err))
            elif kind == 'append_blocks':
                blocks = op.get('blocks') or []
                for b in blocks:
                    if b.get('type') == 'image' and b.get('resolve', True):
                        p = _resolve_asset(sess, b.get('path', ''))
                        if p:
                            b['path'] = p
                        else:
                            b['type'] = 'text'
                            b['text'] = f'[图片未找到: {b.get("path")}]'
                ok, err = td.append_blocks(op.get('section', 'steps_result'), blocks)
                done.append('已追加内容') if ok else errors.append(str(err))
            elif kind == 'insert_image':
                p = _resolve_asset(sess, op.get('path', ''))
                if not p:
                    errors.append(f"图片 {op.get('path') or '(未指明)'} 不存在，"
                                  '请先在左侧上传，或点击素材的"插入报告"按钮')
                    continue
                if op.get('after_index') is not None:
                    ok, err = td.insert_image_after(op['after_index'], p,
                                                    op.get('width_in'))
                else:
                    ok, err = td.append_blocks(op.get('section', 'steps_result'),
                                               [{'type': 'image', 'path': p,
                                                 'caption': op.get('caption')}])
                done.append(f'已插入图片 {os.path.basename(p)}') if ok else errors.append(str(err))
                sess.meta.setdefault('assets', []).append(p) if ok else None
            elif kind == 'replace_image':
                p = _resolve_asset(sess, op.get('path', ''))
                if not p:
                    errors.append('图片不存在')
                    continue
                ok, err = td.replace_image(op['index'], p, op.get('width_in'))
                done.append('图片已替换') if ok else errors.append(str(err))
            elif kind == 'regenerate_task':
                opts = _gen_opts(sess)
                ok, msg = filler.regenerate_task(td, opts, op.get('no'),
                                                 use_llm=llm.ready(_cfg()))
                done.append(msg) if ok else errors.append(msg)
            elif kind == 'rerun_task':
                ok, msg = filler.rerun_task(td, _gen_opts(sess), op.get('no'))
                done.append(msg) if ok else errors.append(msg)
            elif kind == 'regenerate_analysis':
                ok, msg = _regen_analysis(sess, td)
                done.append(msg) if ok else errors.append(msg)
            elif kind == 'set_analysis_para':
                ok, msg = _set_analysis_para(sess, td, op.get('index'),
                                             op.get('text', ''))
                done.append(msg) if ok else errors.append(msg)
            else:
                errors.append(f'未知操作: {kind}')
        except Exception as e:
            errors.append(f'操作失败: {e}')
    if done:
        sess.ensure_dirs()
        td.save(sess.output_path)
        sess.meta['generated'] = True
        sess.bump()
    return done, errors


def _regen_analysis(sess, td):
    cfg = _cfg()
    meta = filler.load_task_records(sess.dir)
    exp_name = sess.meta['profile'].get('exp_name') or ''
    paras = None
    if llm.ready(cfg):
        try:
            paras = llm.generate_analysis(
                cfg, exp_name or 'C语言实验',
                [t['text'] for t in meta.get('tasks', [])] or ['本次实验任务'],
                style_hint='\n'.join(courses.c_analysis_paragraphs(exp_name)))
        except Exception:
            paras = None
    if not paras:
        paras = courses.c_analysis_paragraphs(exp_name)
    if td._section_range('analysis'):
        td.clear_section('analysis')
        td.append_blocks('analysis', [{'type': 'text', 'text': p}
                                      for p in paras if p.strip()])
        meta['analysis'] = paras
        with open(os.path.join(sess.dir, 'meta_tasks.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return True, f'分析与讨论已重写（{len(paras)} 段）'
    return False, '模板中没有分析与讨论章节'


def _set_analysis_para(sess, td, idx, text):
    meta = filler.load_task_records(sess.dir)
    paras = meta.get('analysis') or []
    if 0 <= idx - 1 < len(paras):
        paras[idx - 1] = text
        if td._section_range('analysis'):
            td.clear_section('analysis')
            td.append_blocks('analysis', [{'type': 'text', 'text': p}
                                          for p in paras if p.strip()])
            meta['analysis'] = paras
            with open(os.path.join(sess.dir, 'meta_tasks.json'), 'w',
                      encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            return True, f'分析第 {idx} 段已修改'
        return False, '模板中没有分析与讨论章节'
    return False, f'分析只有 {len(paras)} 段，序号超出范围'


def _cfg():
    return llm.load_config(DATA)


def _gen_opts(sess):
    return {
        'workdir': sess.dir,
        'profile': sess.meta['profile'],
        'requirement': sess.meta['requirement'],
        'course': sess.meta.get('course'),
        'use_llm': True,
        'cfg': _cfg(),
        'run_programs': sess.meta.get('run_programs', True),
        'assets': sess.meta.get('assets', []),
        'template_name': sess.meta.get('template_name', ''),
    }


def do_generate(sess, body):
    sess.ensure_dirs()
    sess.meta['requirement'] = body.get('requirement', '')
    sess.meta['course'] = body.get('course') or None
    sess.meta['run_programs'] = bool(body.get('run_programs', True))
    for k, v in (body.get('profile') or {}).items():
        if v:
            sess.meta['profile'][k] = str(v)
    tpath = sess.meta.get('template_path')
    if not tpath or not os.path.exists(tpath):
        return {'ok': False, 'error': '请先上传模板 docx'}
    # 基准文档：
    #  - 已生成过 → 在“现有报告”基础上继续（保留聊天修改，只增不删）
    #  - 否则/换模板后 → 从最近上传的模板重建
    if sess.meta.get('generated') and os.path.exists(sess.output_path):
        src_path, src_label = sess.output_path, '既有报告'
    else:
        src_path, src_label = tpath, '模板'
    td = TemplateDoc(src_path)
    sess.td = td
    opts = _gen_opts(sess)
    opts['exp_name'] = body.get('exp_name')
    with sess.lock:
        try:
            result = filler.generate_report(td, opts)
        except Exception as e:
            import traceback
            err = traceback.format_exc(limit=6)
            sess.chat_add('assistant', f'生成失败：{e}')
            return {'ok': False, 'error': str(e), 'trace': err}
        td.save(sess.output_path)
        # 保真校验：模板原文正文必须一字不差全部保留（只增不删的硬保证）
        orig = [p.text.strip() for p in _WordDoc(tpath).paragraphs if p.text.strip()]
        out_texts = set(p.text.strip() for p in _WordDoc(sess.output_path).paragraphs)
        missing = [t for t in orig if t and t not in out_texts]
        if missing:
            sess.chat_add('assistant', '⚠ 安全校验未通过：检测到模板原文丢失，本次生成已中止')
            return {'ok': False, 'error': '安全校验未通过：模板原文丢失，已中止',
                    'missing': missing[:5]}
        sess.meta['generated'] = True
        sess.meta['output_template'] = sess.meta['template_name']
        summary = [f'基于「{sess.meta["template_name"]}」（{src_label}）生成：'
                   f'原文内容全部保留，只增不删'] + result['summary']
        sess.chat_add('assistant', '已生成报告：\n• ' + '\n• '.join(summary))
        sess.bump()
        return {'ok': True, 'summary': summary, 'course': result['course'],
                'images': result['images'], 'template': sess.meta['template_name']}


def build_state(sess):
    sc = None
    fields_out = {}
    sections_out = []
    tasks_out = []
    if sess.meta['template_path']:
        td = sess.get_td()
        if td is not None:
            sc = td.scan(refresh=True)
            for k, f in sc['fields'].items():
                fields_out[k] = {'label': FIELD_LABELS_ZH.get(k, k),
                                 'value': f['value']}
            for s in sc['sections']:
                sections_out.append({'key': s['key'], 'title': s['title'],
                                     'start': s['start'], 'end': s['end']})
            tasks_out = [{'no': t['no'], 'text': t['text'][:80]} for t in sc['tasks']]
    tools = runner.detect_tools()
    cfg = _cfg()
    artifacts = sorted(os.listdir(os.path.join(sess.dir, 'artifacts')))
    uploads = sorted(os.listdir(os.path.join(sess.dir, 'uploads')))
    return {
        'sid': sess.sid,
        'rev': sess.rev,
        'template_name': sess.meta['template_name'],
        'generated': sess.meta['generated'],
        'course': sess.meta.get('course'),
        'profile': sess.meta['profile'],
        'requirement': sess.meta['requirement'],
        'fields': fields_out,
        'sections': sections_out,
        'tasks': tasks_out,
        'chat': sess.meta['chat'][-60:],
        'pending': sess.pending,
        'history': sess.history[-20:],
        'artifacts': artifacts,
        'uploads': uploads,
        'tools': {k: bool(v) for k, v in tools.items()},
        'llm': {'enabled': bool(cfg.get('enabled')), 'ready': llm.ready(cfg),
                'model': cfg.get('model')},
        'run_programs': sess.meta.get('run_programs', True),
    }


def agent_plan(sess, goal):
    """根据目标生成待批准命令列表。"""
    tools = runner.detect_tools()
    tools_info = {k: v for k, v in tools.items() if v}
    cmds = []
    g = goal or ''
    if ('autocad' in g.lower() or 'cad' in g.lower() or '制图' in g) and tools['acad']:
        cmds.append({'id': uuid.uuid4().hex[:8], 'label': '启动 AutoCAD',
                     'command': f'"{tools["acad"]}"',
                     'screenshot_after': True,
                     'why': '启动 AutoCAD 后你手动绘图，我定时截屏作为过程截图素材'})
    if ('pdf' in g.lower() or '导出' in g) and tools['soffice']:
        cmds.append({'id': uuid.uuid4().hex[:8], 'label': 'LibreOffice 转 PDF',
                     'command': f'"{tools["soffice"]}" --headless --convert-to pdf '
                                f'--outdir "{sess.dir}" "{sess.output_path}"',
                     'screenshot_after': False, 'why': '把当前报告导出为 PDF'})
    if not cmds and llm.ready(_cfg()):
        try:
            proposed = llm.propose_commands(_cfg(), goal, tools_info)
            for c in proposed:
                cmds.append({'id': uuid.uuid4().hex[:8],
                             'label': c.get('label', '执行命令'),
                             'command': c.get('command', ''),
                             'stdin': c.get('stdin'),
                             'screenshot_after': bool(c.get('screenshot_after')),
                             'why': c.get('why', '')})
        except Exception:
            pass
    if not cmds and goal.strip():
        # 兜底：命令执行通道自检（同时测试截屏能力）
        cmds.append({'id': uuid.uuid4().hex[:8], 'label': '命令通道自检',
                     'command': 'cmd /c echo 本机命令执行通道正常，时间: %DATE% %TIME%',
                     'screenshot_after': True,
                     'why': '验证"批准后执行"通道与截屏能力可用'})
    for c in cmds:
        c['status'] = 'pending'
    sess.pending.extend(cmds)
    sess.chat_add('assistant',
                  '我请求在你的电脑上执行以下命令（请逐条批准）：\n' +
                  '\n'.join(f'· [{c["label"]}] {c["command"]}' for c in cmds))
    sess.bump()
    return cmds


def agent_approve(sess, body):
    ids = body.get('ids') or []
    approve = bool(body.get('approve', True))
    results = []
    remain = []
    for c in sess.pending:
        if (not ids or c['id'] in ids) and approve:
            r = runner.execute_command(
                c['command'], os.path.join(sess.dir, 'src'),
                timeout=90, stdin_text=c.get('stdin'),
                log_file=os.path.join(sess.dir, 'command_log.txt'))
            shot = None
            if c.get('screenshot_after') and r['ok']:
                sess.ensure_dirs()
                shot = os.path.join(sess.dir, 'artifacts',
                                    f'screen_{time.strftime("%H%M%S")}.png')
                from engine.render import take_screenshot
                if not take_screenshot(shot):
                    shot = None
            entry = {'id': c['id'], 'label': c['label'], 'command': c['command'],
                     'ok': r['ok'], 'output': (r['stdout'] or r['stderr'])[:1500],
                     'duration': r['duration'], 'screenshot':
                     os.path.basename(shot) if shot else None}
            sess.history.append(entry)
            results.append(entry)
            sess.chat_add('assistant',
                          f"命令[{c['label']}] {'执行成功' if r['ok'] else '执行失败'}"
                          f"（{r['duration']}s）"
                          + (f"，已截屏 {os.path.basename(shot)}" if shot else ''),
                          {'result': True})
        else:
            remain.append(c)
    sess.pending = remain
    sess.bump()
    return results


# =====================================================================
# HTTP Handler
# =====================================================================

class Handler(BaseHTTPRequestHandler):
    server_version = 'NuistLabReport/1.0'

    def log_message(self, fmt, *args):
        pass  # 安静模式

    # ---------- 工具 ----------
    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path, download_name=None):
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if download_name:
            from urllib.parse import quote
            self.send_header('Content-Disposition',
                             f'attachment; filename*=UTF-8\'\'{quote(download_name)}')
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY:
            raise ValueError('文件太大')
        return self.rfile.read(length) if length else b''

    def _session(self, q):
        return get_session((q.get('sid') or ['default'])[0])

    # ---------- GET ----------
    def do_GET(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path
            if path == '/' or path == '/index.html':
                return self._file(os.path.join(WEB, 'index.html'))
            if path.startswith('/static/'):
                p = os.path.normpath(os.path.join(WEB, path[len('/static/'):]))
                if p.startswith(WEB) and os.path.exists(p):
                    return self._file(p)
                return self._json({'error': 'not found'}, 404)
            if path == '/api/state':
                s = self._session(q)
                since = int((q.get('since') or [0])[0])
                if since and since == s.rev:
                    return self._json({'rev': s.rev, 'unchanged': True})
                return self._json(build_state(s))
            if path == '/api/preview':
                s = self._session(q)
                if s.meta['generated'] and os.path.exists(s.output_path):
                    html, _ = preview.render_preview(
                        s.output_path, os.path.join(s.dir, 'files', 'img'))
                    html = html + _preview_script()
                    data = html.encode('utf-8')
                else:
                    data = ('<div style="padding:60px;color:#888;text-align:center;'
                            'font-size:15px">预览将在这里显示<br><br>'
                            '① 上传模板 docx → ② 填写信息与实验要求 → ③ 点击「生成报告」'
                            '</div>').encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if path == '/api/download':
                s = self._session(q)
                if not (s.meta.get('generated') and os.path.exists(s.output_path)):
                    return self._json({'error': '还没有可下载的报告（更换模板后需要重新生成）'}, 404)
                name = (s.meta['profile'].get('sid') or '') + ' ' + \
                       (s.meta['profile'].get('student_name') or '') + \
                       ' 实验报告.docx'
                return self._file(s.output_path, name.strip() or '实验报告.docx')
            if path.startswith('/api/files/'):
                rest = path[len('/api/files/'):]
                parts = rest.split('/')
                if len(parts) >= 2:
                    s = get_session(parts[0])
                    sub = '/'.join(parts[1:])
                    p = os.path.normpath(os.path.join(s.dir, sub))
                    if p.startswith(os.path.normpath(s.dir)) and os.path.isfile(p):
                        return self._file(p)
                return self._json({'error': 'not found'}, 404)
            if path == '/api/tools':
                return self._json(runner.detect_tools())
            return self._json({'error': 'not found'}, 404)
        except Exception as e:
            import traceback
            return self._json({'error': str(e),
                               'trace': traceback.format_exc(limit=5)}, 500)

    # ---------- POST ----------
    def do_POST(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            body_bytes = self._read_body()
            ctype = self.headers.get('Content-Type', '')
            body = {}
            if body_bytes and 'multipart/form-data' not in ctype:
                try:
                    body = json.loads(body_bytes.decode('utf-8'))
                except Exception:
                    body = {}
            # 会话 id 的来源优先级：URL 查询串 > JSON body > multipart 字段 > default
            sid = (q.get('sid') or [None])[0]
            if not sid and isinstance(body, dict):
                sid = body.get('sid')
            if 'multipart/form-data' in ctype:
                fields, files = parse_multipart(body_bytes, ctype)
                sid = sid or fields.get('sid')
                s = get_session(sid or 'default')
                if u.path == '/api/upload/template':
                    return self._upload_template(s, files)
                if u.path == '/api/assets':
                    return self._upload_assets(s, files)
                body = fields
            else:
                s = get_session(sid or 'default')

            if u.path == '/api/generate':
                return self._json(do_generate(s, body))
            if u.path == '/api/new':
                # 开启一份全新报告：生成新会话，旧会话数据原样保留在磁盘
                new_sid = 's' + uuid.uuid4().hex[:8]
                get_session(new_sid)
                return self._json({'ok': True, 'sid': new_sid})
            if u.path == '/api/profile':
                for k, v in (body.get('profile') or {}).items():
                    if v is not None and str(v).strip():
                        s.meta['profile'][k] = str(v).strip()
                s.bump()
                # 已生成则实时更新文档字段
                if s.meta['generated'] and s.get_td():
                    ops = [{'op': 'set_field', 'field': k, 'value': v}
                           for k, v in s.meta['profile'].items()]
                    done, errs = apply_ops(s, ops)
                return self._json({'ok': True})
            if u.path == '/api/chat':
                return self._chat(s, body.get('message', ''))
            if u.path == '/api/ops':
                with s.lock:
                    done, errs = apply_ops(s, body.get('ops') or [])
                if done:
                    s.chat_add('assistant', '；'.join(done))
                reply = '；'.join(done + errs) or '没有可执行的操作'
                return self._json({'ok': not errs, 'done': done, 'errors': errs,
                                   'reply': reply})
            if u.path == '/api/agent/plan':
                cmds = agent_plan(s, body.get('goal', ''))
                return self._json({'ok': True, 'commands': cmds})
            if u.path == '/api/agent/approve':
                results = agent_approve(s, body)
                return self._json({'ok': True, 'results': results})
            if u.path == '/api/export':
                fmt = body.get('format', 'pdf')
                if fmt == 'pdf':
                    if not (s.meta.get('generated') and os.path.exists(s.output_path)):
                        return self._json({'ok': False,
                                           'error': '还没有生成报告（更换模板后请重新生成）'})
                    pdf, err = convert.docx_to_pdf(
                        s.output_path, os.path.join(s.dir, 'files'))
                    if pdf:
                        return self._json({'ok': True,
                                           'url': f"/api/files/{s.sid}/files/{os.path.basename(pdf)}"})
                    return self._json({'ok': False, 'error': err})
                return self._json({'ok': False, 'error': '未知格式'})
            if u.path == '/api/settings':
                cfg = llm.load_config(DATA)
                cfg.update({k: body.get(k) for k in
                            ('enabled', 'base_url', 'api_key', 'model')
                            if body.get(k) is not None})
                llm.save_config(DATA, cfg)
                s.chat_add('assistant', 'AI 设置已保存'
                            + ('，已启用 LLM 增强' if llm.ready(cfg) else '（未配置 API Key，使用内置知识库）'))
                return self._json({'ok': True, 'ready': llm.ready(cfg)})
            if u.path == '/api/run_programs':
                s.meta['run_programs'] = bool(body.get('enabled', True))
                s.bump()
                return self._json({'ok': True})
            return self._json({'error': 'not found'}, 404)
        except Exception as e:
            import traceback
            return self._json({'error': str(e),
                               'trace': traceback.format_exc(limit=5)}, 500)

    # ---------- 具体业务 ----------
    def _upload_template(self, s, files):
        if not files:
            return self._json({'ok': False, 'error': '没有收到文件'})
        f = files[0]
        fn = f['filename']
        content = f['content']
        s.ensure_dirs()
        # 按内容识别（文件名/扩展名不作要求）：
        #   PK..  = docx（zip 容器）；D0CF11E0 = doc（OLE 老格式）
        is_zip = content[:2] == b'PK'
        is_ole = content[:4] == b'\xd0\xcf\x11\xe0'
        if not (is_zip or is_ole):
            return self._json({'ok': False, 'error':
                               '这不是有效的 Word 文档：请上传 .docx 或 .doc '
                               '（文件名随意，但文件内容必须是 Word）'})
        ext = '.docx' if is_zip else '.doc'
        save_path = os.path.join(s.dir, 'uploads', f'template_{int(time.time())}{ext}')
        with open(save_path, 'wb') as out:
            out.write(content)
        if is_ole:
            conv, err = convert.doc_to_docx(save_path, os.path.join(s.dir, 'uploads'))
            if conv:
                save_path = conv
            else:
                return self._json({'ok': False,
                                   'error': (err or '.doc 转换失败')
                                            + '（.doc 老格式需要本机装有 Word）'})
        try:
            s.reset_template(save_path, fn)
            sc = s.td.scan(refresh=True)
        except Exception as e:
            return self._json({'ok': False, 'error': f'模板解析失败：{e}'})
        fields = {k: {'label': FIELD_LABELS_ZH.get(k, k), 'value': v['value']}
                  for k, v in sc['fields'].items()}
        s.chat_add('assistant',
                   f'模板「{fn}」解析成功：识别到 {len(fields)} 个信息字段、'
                   f'{len(sc["sections"])} 个章节、{len(sc["tasks"])} 个实验任务。'
                   '接下来：① 补全个人信息 ② 粘贴实验要求（可不填） ③ 点「生成报告」')
        s.bump()
        return self._json({'ok': True,
                           'fields': fields,
                           'sections': [{'key': x['key'], 'title': x['title']}
                                        for x in sc['sections']],
                           'tasks': [{'no': t['no'], 'text': t['text'][:100]}
                                     for t in sc['tasks']]})

    def _upload_assets(self, s, files):
        s.ensure_dirs()
        saved = []
        for f in files:
            ext = os.path.splitext(f['filename'])[1].lower()
            sub = 'uploads'
            fn = f"{int(time.time() * 1000) % 100000000}_{f['filename']}"
            p = os.path.join(s.dir, sub, fn)
            with open(p, 'wb') as out:
                out.write(f['content'])
            saved.append({'name': fn, 'path': p,
                          'is_image': ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp')})
            if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                s.meta.setdefault('assets', []).append(p)
        s.bump()
        return self._json({'ok': True, 'saved': saved})

    def _chat(self, s, message):
        if not message.strip():
            return self._json({'ok': False, 'error': '空消息'})
        s.chat_add('user', message)
        ops, reply, need_llm = intent.parse(message)
        if need_llm and llm.ready(_cfg()) and s.meta['template_path']:
            try:
                st = build_state(s)
                ctx = json.dumps({'fields': st['fields'], 'sections': st['sections'],
                                  'tasks': st['tasks']}, ensure_ascii=False)
                parsed = llm.parse_intent_ops(_cfg(), message, ctx)
                ops, reply = parsed['ops'], parsed['reply'] or reply
            except Exception as e:
                reply, ops = intent.HELP_TEXT, []
        elif need_llm:
            reply = intent.HELP_TEXT
            ops = []
        errs = []
        if ops:
            with s.lock:
                done, errs = apply_ops(s, ops)
            if done:
                reply = (reply + '\n' if reply else '') + '；'.join(done)
            if errs:
                reply = (reply + '\n' if reply else '') + '⚠ ' + '；'.join(errs)
        s.chat_add('assistant', reply or intent.HELP_TEXT)
        s.bump()
        return self._json({'ok': True, 'reply': reply, 'errors': errs})


def _preview_script():
    return '''<script>
document.addEventListener('click', function(e){
  var el = e.target.closest('[data-idx]');
  if (el && window.parent !== window) {
    window.parent.postMessage({type:'select-para', idx: el.getAttribute('data-idx')}, '*');
    document.querySelectorAll('.sel').forEach(function(x){x.classList.remove('sel')});
    el.classList.add('sel');
  }
});
</script>
<style>.sel{outline:2px solid #4a90d9;background:#eaf3fd!important;cursor:pointer}</style>'''


def main():
    start_port = int(os.environ.get('PORT', '8765'))
    ThreadingHTTPServer.allow_reuse_address = False  # Windows 下禁止双重绑定
    server = None
    port = None
    # 端口被占（比如已有一份工坊在运行）时自动往后找空闲端口
    for p in range(start_port, start_port + 10):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', p), Handler)
            port = p
            break
        except OSError:
            continue
    if server is None:
        print(f'[错误] 端口 {start_port}-{start_port + 9} 全部被占用。')
        print('       请关闭占用端口的程序（或重启电脑）后重新运行。')
        raise SystemExit(1)
    if port != start_port:
        print(f'[提示] 端口 {start_port} 被占用，已自动改用 {port}')
    tools = runner.detect_tools()
    url = f'http://127.0.0.1:{port}'
    print('==============================================')
    print('  南信实验报告工坊 已启动')
    print(f'  浏览器地址：{url}')
    print('  （浏览器若未自动打开，请把上面的地址复制到浏览器）')
    print(f'  gcc: {"√ " + str(tools["gcc"]) if tools["gcc"] else "× 未找到（运行程序功能受限）"}')
    print(f'  AutoCAD: {"√" if tools["acad"] else "×"}  LibreOffice: {"√" if tools["soffice"] else "×"}')
    print('==============================================')
    if os.environ.get('NO_BROWSER') != '1':
        threading.Timer(0.3, lambda: _open_browser(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def _open_browser(url):
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == '__main__':
    main()
