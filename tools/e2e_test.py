# -*- coding: utf-8 -*-
"""端到端测试：上传模板 → 填信息 → 生成 → 预览 → 聊天修改 → 下载。"""
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = os.environ.get('LAB_BASE', 'http://127.0.0.1:8765')
SID = 'e2e_' + str(int(time.time()))
PY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(PY_DIR)


def req(path, method='GET', body=None, ctype='application/json'):
    url = BASE + path
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
    r = urllib.request.Request(url, data=data, method=method,
                               headers={'Content-Type': ctype} if data else {})
    with urllib.request.urlopen(r, timeout=300) as resp:
        raw = resp.read()
        if resp.headers.get('Content-Type', '').startswith('application/json'):
            return json.loads(raw.decode('utf-8'))
        return raw


def upload(path, field, filepath):
    boundary = '----b' + uuid.uuid4().hex
    fn = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        content = f.read()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode('utf-8') + content + f'\r\n--{boundary}--\r\n'.encode()
    return req(path, 'POST', body,
               f'multipart/form-data; boundary={boundary}')


def step(name, ok, detail=''):
    mark = 'PASS' if ok else 'FAIL'
    print(f'[{mark}] {name} {detail}')
    if not ok:
        FAILS.append(name)


FAILS = []

print(f'== 会话 {SID} ==')

# 1. 模板解析
tpl = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Users\ZH\Desktop\南信\c语言\学号 姓名 实验报告-4 数组及其应用.docx'
r = upload(f'/api/upload/template?sid={SID}', 'file', tpl)
step('上传模板', r.get('ok'), f"{r.get('fields') and len(r['fields'])}字段 "
     f"{len(r.get('sections', []))}章节 {len(r.get('tasks', []))}任务")
for t in r.get('tasks', []):
    print('   任务（%s）%s' % (t['no'], t['text'][:44]))

# 2. 个人信息
r = req(f'/api/profile?sid={SID}', 'POST', {'profile': {
    'student_name': '仲恒', 'sid': '202613050166',
    'college': '电子与信息工程学院', 'major': '电子信息工程',
    'grade': '2026', 'class': '4板块1-1', 'teacher': '郑关胜',
    'date': '05.13'}})
step('填写个人信息', r.get('ok'))

# 3. 生成
t0 = time.time()
r = req(f'/api/generate?sid={SID}', 'POST', {'requirement': '', 'run_programs': True})
step('一键生成', r.get('ok'), f"耗时{time.time()-t0:.1f}s 图片{r.get('images')}")
for line in r.get('summary', []):
    print('   •', line)
if not r.get('ok'):
    print(r.get('trace', '')[:1500])
    sys.exit(1)

# 4. 预览
raw = req(f'/api/preview?sid={SID}')
html = raw.decode('utf-8')
ok = ('仲恒' in html and '202613050166' in html
      and '实验步骤和实验结果' in html and '分析与讨论' in html
      and html.count('<img') >= 3)
step('预览HTML', ok, f'图片{html.count("<img")}张 长度{len(html)}')

# 5. 状态
st = req(f'/api/state?sid={SID}')
step('状态接口', st['generated'] and st['fields'].get('student_name', {}).get('value') == '仲恒',
     f"姓名字段={st['fields'].get('student_name', {}).get('value')!r}")

# 6. 聊天修改：字段
r = req(f'/api/chat?sid={SID}', 'POST', {'message': '把姓名改成测试同学'})
st = req(f'/api/state?sid={SID}')
step('聊天-改姓名', st['fields'].get('student_name', {}).get('value') == '测试同学',
     r.get('reply', '')[:60])
req(f'/api/chat?sid={SID}', 'POST', {'message': '把姓名改成仲恒'})

# 7. 聊天修改：未知指令回退
r = req(f'/api/chat?sid={SID}', 'POST', {'message': '今天天气怎么样'})
step('聊天-兜底提示', '我可以' in r.get('reply', ''), r.get('reply', '')[:40])

# 8. 重写分析
r = req(f'/api/chat?sid={SID}', 'POST', {'message': '重写分析与讨论'})
step('聊天-重写分析', '重写' in r.get('reply', ''), r.get('reply', '')[:60])

# 9. 权限流程：申请执行 → 批准
r = req(f'/api/agent/plan?sid={SID}', 'POST', {'goal': '测试命令执行通道'})
cmds = r.get('commands', [])
step('权限-生成待批命令', len(cmds) >= 1, f'{len(cmds)}条')
if cmds:
    r2 = req(f'/api/agent/approve?sid={SID}', 'POST',
             {'ids': [cmds[0]['id']], 'approve': True})
    ok = r2['results'] and (r2['results'][0]['ok'] or '通道' in str(r2['results'][0]['output']))
    step('权限-批准执行', bool(ok), f"输出: {r2['results'][0]['output'][:60]!r}")

# 10. 下载 docx 并用解析器验证
raw = req(f'/api/download?sid={SID}')
out = os.path.join(PROJ, 'data', 'e2e_output.docx')
with open(out, 'wb') as f:
    f.write(raw)
step('下载docx', os.path.getsize(out) > 20000, f'{os.path.getsize(out)}字节')

sys.path.insert(0, PY_DIR)
sys.path.insert(0, PROJ)
from tools.inspect_docx import dump  # noqa

print('\n---- 生成的 docx 结构（前若干行）----')
import io
from contextlib import redirect_stdout
buf = io.StringIO()
with redirect_stdout(buf):
    dump(out, os.path.join(PROJ, 'data', 'e2e_imgs'))
text = buf.getvalue()
print('\n'.join(text.split('\n')[:26]))
n_img = text.count('-> saved')
step('docx内含图片', n_img >= 3, f'{n_img}张')

# 11. 原文保真校验：模板原有内容必须全部保留（只增不删）
from docx import Document as _D2  # noqa
out_texts = [p.text.strip() for p in _D2(out).paragraphs]
need = ['1．实验目的', '2．实验内容',
        '（1）运行下面的C程序，根据运行结果，可以说明什么？',
        '（2）为一个冒泡排序程序设计测试用例，并测试之。',
        '3．实验步骤和实验结果', '4．分析与讨论']
missing = [t for t in need if t not in out_texts]
step('模板原文全部保留', not missing, '缺失:' + str(missing[:3]))

print('\n== 结果: %s ==' % ('全部通过' if not FAILS else '失败项: ' + ', '.join(FAILS)))
