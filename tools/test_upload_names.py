# -*- coding: utf-8 -*-
"""上传文件名健壮性测试：文件名随意 / 无扩展名 / 假 docx。"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_test import req, upload, step, FAILS  # noqa

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = r'C:\Users\ZH\Desktop\南信\c语言\学号 姓名 实验报告-4 数组及其应用.docx'
TMP = os.path.join(PROJ, 'data')
os.makedirs(TMP, exist_ok=True)
sid = 'fntest_' + str(int(time.time()))

# 1 正常文件名
r = upload(f'/api/upload/template?sid={sid}', 'file', TPL)
step('正常文件名', r.get('ok'), str(len(r.get('fields', {}))) + '字段')

# 2 奇怪文件名（空格/括号/波浪号/感叹号）
weird = os.path.join(TMP, '随便 起 (1)~最终版!命名很乱.docx')
shutil.copy(TPL, weird)
r = upload(f'/api/upload/template?sid={sid}', 'file', weird)
step('奇怪文件名', r.get('ok'))

# 3 无扩展名（按内容自动识别 docx）
noext = os.path.join(TMP, '没有扩展名的报告模板')
shutil.copy(TPL, noext)
r = upload(f'/api/upload/template?sid={sid}', 'file', noext)
step('无扩展名（内容识别）', r.get('ok'))

# 4 伪 docx（内容不是 Word）必须被拒绝
fake = os.path.join(TMP, '假装是模板.docx')
with open(fake, 'w', encoding='utf-8') as f:
    f.write('这不是一个 Word 文档，只是个文本文件')
r = upload(f'/api/upload/template?sid={sid}', 'file', fake)
step('非Word内容被拒绝', r.get('ok') is False, r.get('error', '')[:40])

print('\n== 文件名测试: %s ==' % ('全部通过' if not FAILS else '失败: ' + ', '.join(FAILS)))
