# -*- coding: utf-8 -*-
"""打包发布版 → dist/NUIST-LabReportStudio-v1.0/（解压即用，免装 Python）。

包含：
- 应用代码（server.py / engine / web / samples）
- runtime/：精简 CPython 3.12 运行时 + 所需依赖（python-docx / Pillow / lxml / pip）
- start.bat：优先用内置运行时，其次系统 Python
- LICENSE.txt / 第三方组件许可.txt / 说明.txt
"""
import os
import shutil
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_SRC = os.environ.get(
    'LAB_RUNTIME_SRC',
    r'C:\Users\ZH\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python')
DIST = os.path.join(PROJ, 'dist')
NAME = 'NUIST-LabReportStudio-v1.0'
APP = os.path.join(DIST, NAME)

# Lib 里整个剔除的目录
EXCLUDE_LIB_DIRS = {'site-packages', 'test', 'idlelib', 'tkinter',
                    'turtledemo', 'lib2to3'}
# site-packages 里只保留的包/文件（python-docx + Pillow + lxml + pip 及其元数据）
KEEP_SITE_DIRS = ['docx', 'PIL', 'lxml', 'pip',
                  'python_docx-1.2.0.dist-info',
                  'pillow-12.3.0.dist-info',
                  'lxml-6.1.3.dist-info',
                  'pip-26.2.1.dist-info',
                  'typing_extensions-4.16.0.dist-info']
KEEP_SITE_FILES = ['typing_extensions.py']


def size_of(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def copytree_filtered(src, dst, exclude_dirs=(), skip_pyc=True):
    os.makedirs(dst, exist_ok=True)
    n = 0
    for entry in os.listdir(src):
        if entry in exclude_dirs or entry == '__pycache__':
            continue
        s = os.path.join(src, entry)
        d = os.path.join(dst, entry)
        if os.path.isdir(s):
            n += copytree_filtered(s, d, exclude_dirs, skip_pyc)
        else:
            if skip_pyc and entry.endswith(('.pyc', '.pyo')):
                continue
            shutil.copy2(s, d)
            n += 1
    return n


def build_runtime():
    rt_dst = os.path.join(APP, 'runtime')
    os.makedirs(rt_dst, exist_ok=True)
    # 根目录文件与必要子目录
    for f in ('python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll',
              'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        s = os.path.join(RUNTIME_SRC, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(rt_dst, f))
    for d in ('DLLs', 'libs'):
        s = os.path.join(RUNTIME_SRC, d)
        if os.path.isdir(s):
            copytree_filtered(s, os.path.join(rt_dst, d))
    # Lib（剔除 site-packages/test/idlelib/tkinter 等）
    lib_dst = os.path.join(rt_dst, 'Lib')
    copytree_filtered(os.path.join(RUNTIME_SRC, 'Lib'), lib_dst,
                      exclude_dirs=EXCLUDE_LIB_DIRS)
    # site-packages 子集
    sp_src = os.path.join(RUNTIME_SRC, 'Lib', 'site-packages')
    sp_dst = os.path.join(lib_dst, 'site-packages')
    os.makedirs(sp_dst, exist_ok=True)
    for d in KEEP_SITE_DIRS:
        s = os.path.join(sp_src, d)
        if os.path.isdir(s):
            copytree_filtered(s, os.path.join(sp_dst, d))
    for f in KEEP_SITE_FILES:
        s = os.path.join(sp_src, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(sp_dst, f))
    return rt_dst


def build_app():
    # 清理旧数据（避免把测试会话/个人信息打进发布包）
    data_dir = os.path.join(APP, 'data')
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    os.makedirs(os.path.join(data_dir, 'sessions'), exist_ok=True)
    # 应用代码
    shutil.copy2(os.path.join(PROJ, 'server.py'), os.path.join(APP, 'server.py'))
    copytree_filtered(os.path.join(PROJ, 'engine'), os.path.join(APP, 'engine'))
    copytree_filtered(os.path.join(PROJ, 'web'), os.path.join(APP, 'web'))
    copytree_filtered(os.path.join(PROJ, 'samples'), os.path.join(APP, 'samples'))
    req = os.path.join(PROJ, 'requirements.txt')
    if os.path.exists(req):
        shutil.copy2(req, os.path.join(APP, 'requirements.txt'))
    # 自检工具
    os.makedirs(os.path.join(APP, 'tools'), exist_ok=True)
    diag = os.path.join(PROJ, 'tools', 'diagnose.py')
    if os.path.exists(diag):
        shutil.copy2(diag, os.path.join(APP, 'tools', 'diagnose.py'))
    selftest = os.path.join(PROJ, 'SelfCheck.bat')
    if os.path.exists(selftest):
        shutil.copy2(selftest, os.path.join(APP, 'SelfCheck.bat'))


LICENSE_TXT = '''南信实验报告工坊 (NUIST Lab Report Studio)
Copyright (c) 2026 <在此填写你的名字>

本项目以 MIT 协议发布（见下）。使用本项目生成并提交的实验报告，
请遵守所在课程的作业与学术诚信规定。

----------------------------------------
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

THIRD_PARTY_TXT = '''第三方组件及其许可（随本包内置分发）：

1. CPython 3.12 运行时 — Python Software Foundation License (PSF-2.0)
2. python-docx 1.2.0 — MIT License
3. Pillow 12.3.0 — HPND License / MIT-CMU
4. lxml 6.1.3 — BSD-3-Clause
5. pip — MIT License

以上组件的完整许可文本可在其官方仓库或 runtime/Lib/site-packages
对应 dist-info 目录中找到。
'''

README_TXT = '''南信实验报告工坊 —— 免安装版使用说明
========================================

【开始使用】
1. 解压后双击 start.bat（如被 SmartScreen 拦截，点"仍要运行"）
2. 浏览器会自动打开 http://127.0.0.1:8765
3. 按页面左侧 ①②③④ 操作：上传模板 → 填信息 → 生成 → 下载

【免安装说明】
本包内置了精简 Python 运行时（runtime\\），无需安装 Python，
无需联网，数据全部保存在本机。

【想让程序真正运行并截图？】
安装任一 C 编译器后重启工具即可自动检测：
  - Dev-C++（很多同学已装）
  - MinGW-w64（winlibs.com）
没装也没关系：报告会插入代码截图，运行结果可自行截图上传。

【详细功能与聊天指令】见 使用说明.md（即 README.md）。
'''


def write_docs():
    shutil.copy2(os.path.join(PROJ, 'README.md'),
                 os.path.join(APP, '使用说明.md'))
    with open(os.path.join(APP, '说明.txt'), 'w', encoding='utf-8') as f:
        f.write(README_TXT)
    with open(os.path.join(APP, 'LICENSE.txt'), 'w', encoding='utf-8') as f:
        f.write(LICENSE_TXT)
    with open(os.path.join(APP, '第三方组件许可.txt'), 'w', encoding='utf-8') as f:
        f.write(THIRD_PARTY_TXT)


def crlf_fix(path):
    """Windows 批处理必须是 CRLF 换行，否则 cmd 解析会错乱。"""
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8', newline='') as f:
        data = f.read()
    data = data.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(data)


def main():
    if os.path.exists(APP):
        shutil.rmtree(APP)
    os.makedirs(APP, exist_ok=True)
    print('打包应用代码...')
    build_app()
    print('打包内置运行时（精简）...')
    build_runtime()
    print('写说明与许可...')
    write_docs()
    # start.bat 从项目根复制（已兼容内置运行时）
    shutil.copy2(os.path.join(PROJ, 'start.bat'), os.path.join(APP, 'start.bat'))
    crlf_fix(os.path.join(APP, 'start.bat'))
    crlf_fix(os.path.join(APP, 'SelfCheck.bat'))
    total = size_of(APP)
    print(f'\n完成：{APP}')
    print(f'总大小: {total / 1024 / 1024:.1f} MB')
    for sub in sorted(os.listdir(APP)):
        p = os.path.join(APP, sub)
        print(f'  {size_of(p) / 1024 / 1024:8.1f} MB  {sub}')


if __name__ == '__main__':
    main()
