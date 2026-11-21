# -*- coding: utf-8 -*-
"""回归测试：sid 在 body 里（网页端真实行为）也必须路由到同一会话。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_test import req, upload, step, FAILS  # noqa

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = r'C:\Users\ZH\Desktop\南信\c语言\学号 姓名 实验报告-4 数组及其应用.docx'
sid = 'route_' + str(int(time.time()))

# 1. 上传：sid 在 URL 查询串（网页端上传的真实行为）
r = upload(f'/api/upload/template?sid={sid}', 'file', TPL)
step('上传（query sid）', r.get('ok'))

# 2. 生成：sid 只在 JSON body、URL 无参数 —— 用户遇到 bug 的确切场景
r = req('/api/generate', 'POST', {'sid': sid, 'requirement': '',
                                  'run_programs': False})
step('生成（body sid，无 query）', r.get('ok'), str(r.get('error', ''))[:50])

# 3. 聊天修改：sid 只在 body
r = req('/api/chat', 'POST', {'sid': sid, 'message': '把姓名改成测试路由'})

# 4. 用查询串读状态，验证以上操作都落在同一会话
st = req(f'/api/state?sid={sid}')
ok = (st.get('generated')
      and st['fields'].get('student_name', {}).get('value') == '测试路由')
step('所有操作落在同一会话', ok)

# 5. 生成结果注明所用模板（防“传错模板”看不见）
step('生成结果注明模板名', '数组及其应用' in str(st.get('template_name', '')))

# 6. 开新报告：返回新会话
r = req('/api/new', 'POST', {'sid': sid})
step('开启新报告（新会话）', r.get('ok') and r.get('sid') and r['sid'] != sid)

# 7. 换模板：上传函数模板 → 旧（数组）报告立即作废、不可下载
import urllib.error  # noqa
TPL3 = r'C:\Users\ZH\Desktop\南信\c语言\学号 姓名 实验报告-3 函数及其应用.docx'
r = upload(f'/api/upload/template?sid={sid}', 'file', TPL3)
step('换模板重新上传', r.get('ok'))
try:
    req(f'/api/download?sid={sid}')
    blocked = False
except urllib.error.HTTPError as e:
    blocked = e.code == 404
step('换模板后旧报告不可下载', blocked)
st = req(f'/api/state?sid={sid}')
step('换模板后状态重置', not st.get('generated'))

# 8. 基于新模板重新生成，输出应注明函数模板
r = req('/api/generate', 'POST', {'sid': sid, 'requirement': '',
                                  'run_programs': False})
step('换模板后重新生成', r.get('ok') and '函数及其应用' in str(r.get('template', '')),
     str(r.get('template', '')))

print('\n== 会话路由: %s ==' % ('全部通过' if not FAILS else '失败: ' + ', '.join(FAILS)))
