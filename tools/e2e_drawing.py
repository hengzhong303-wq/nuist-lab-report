# -*- coding: utf-8 -*-
"""工程制图流程端到端测试。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_test import req, upload, step, FAILS  # noqa

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID = 'draw_' + str(int(time.time()))

print(f'== 工程制图测试 会话 {SID} ==')

tpl = os.path.join(PROJ, 'samples', '示例模板-工程制图.docx')
r = upload(f'/api/upload/template?sid={SID}', 'file', tpl)
step('上传工程制图模板', r.get('ok'),
     f"{len(r.get('fields', {}))}字段 {len(r.get('sections', []))}章节")

req(f'/api/profile?sid={SID}', 'POST', {'profile': {
    'student_name': '仲恒', 'sid': '202613050166',
    'college': '电子与信息工程学院', 'major': '电子信息工程',
    'class': '4班', 'teacher': '', 'date': '2026.11.10',
    'exp_name': '平面图形的绘制、修改与编辑'}})

r = req(f'/api/generate?sid={SID}', 'POST', {
    'requirement': '根据图一、图二所示尺寸准确绘制出图形，并完成尺寸标注',
    'course': 'drawing', 'run_programs': False})
step('一键生成', r.get('ok'), f"图片{r.get('images')}")
for line in r.get('summary', []):
    print('   •', line)

raw = req(f'/api/preview?sid={SID}')
html = raw.decode('utf-8')
ok = ('平面图形的绘制、修改与编辑' in html and '实验步骤' in html
      and '环形阵列' in html and '学习通' in html)
step('预览内容', ok, f'长度{len(html)}')

raw = req(f'/api/download?sid={SID}')
out = os.path.join(PROJ, 'data', 'e2e_drawing.docx')
with open(out, 'wb') as f:
    f.write(raw)
step('下载docx', os.path.getsize(out) > 10000, f'{os.path.getsize(out)}字节')

from tools.inspect_docx import dump  # noqa
import io
from contextlib import redirect_stdout
buf = io.StringIO()
with redirect_stdout(buf):
    dump(out, os.path.join(PROJ, 'data', 'e2e_dimgs'))
text = buf.getvalue()
print('\n'.join(text.split('\n')[:22]))

print('\n== 结果: %s ==' % ('全部通过' if not FAILS else '失败: ' + ', '.join(FAILS)))
