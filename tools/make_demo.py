# -*- coding: utf-8 -*-
"""生成两份演示成品报告（不走聊天修改，纯净输出）。"""
import json
import os
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_test import req, upload  # noqa

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def make(kind, tpl, profile, requirement, out_name, course=None):
    sid = f'demo_{kind}_{int(time.time())}'
    r = upload(f'/api/upload/template?sid={sid}', 'file', tpl)
    assert r.get('ok'), r
    req(f'/api/profile?sid={sid}', 'POST', {'profile': profile})
    r = req(f'/api/generate?sid={sid}', 'POST',
            {'requirement': requirement, 'course': course, 'run_programs': True})
    assert r.get('ok'), r
    raw = req(f'/api/download?sid={sid}')
    out = os.path.join(PROJ, out_name)
    with open(out, 'wb') as f:
        f.write(raw)
    print(f'[{kind}] 生成完成 → {out} ({len(raw)} 字节)')
    for line in r.get('summary', []):
        print('   •', line)


if __name__ == '__main__':
    make('c',
         r'C:\Users\ZH\Desktop\南信\c语言\学号 姓名 实验报告-4 数组及其应用.docx',
         {'student_name': '仲恒', 'sid': '202613050166',
          'college': '电子与信息工程学院', 'major': '电子信息工程',
          'grade': '2026', 'class': '4板块1-1', 'teacher': '郑关胜',
          'date': '05.13'},
         '',
         '示例输出-C语言-数组及其应用.docx')
    make('drawing',
         os.path.join(PROJ, 'samples', '示例模板-工程制图.docx'),
         {'student_name': '仲恒', 'sid': '202613050166',
          'college': '电子与信息工程学院', 'major': '电子信息工程',
          'class': '4班', 'date': '2026.11.10',
          'exp_name': '平面图形的绘制、修改与编辑'},
         '根据图一、图二所示尺寸准确绘制出图形，并完成尺寸标注',
         '示例输出-工程制图.docx', course='drawing')
