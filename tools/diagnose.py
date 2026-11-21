# -*- coding: utf-8 -*-
"""环境自检：检查运行时、依赖、目录权限、端口占用情况。"""
import os
import socket
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OK = 0


def check(name, fn, hint=''):
    global OK
    try:
        detail = fn()
        print(f'[通过] {name}' + (f'  —— {detail}' if detail else ''))
    except Exception as e:
        OK += 1
        print(f'[失败] {name}  —— {e}')
        if hint:
            print(f'        建议：{hint}')


def check_python():
    if sys.version_info < (3, 9):
        raise RuntimeError(f'Python 版本过低：{sys.version.split()[0]}')
    return f'{sys.version.split()[0]}  {sys.executable}'


def check_docx():
    import docx
    return 'python-docx ' + getattr(docx, '__version__', '')


def check_pil():
    import PIL
    return 'Pillow ' + PIL.__version__


def check_data_dir():
    d = os.path.join(BASE, 'data')
    os.makedirs(d, exist_ok=True)
    t = os.path.join(d, '_selftest.tmp')
    with open(t, 'w', encoding='utf-8') as f:
        f.write('ok')
    os.remove(t)
    return d


def check_ports():
    free = []
    for p in range(8765, 8775):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            s.bind(('127.0.0.1', p))
            free.append(p)
        except OSError:
            pass
        finally:
            s.close()
    if not free:
        raise RuntimeError('8765-8774 端口全部被占用')
    return f'可用端口：{free[0]}' + (f' 等 {len(free)} 个' if len(free) > 1 else '')


def check_server_running():
    import urllib.request
    for p in (8765, 8766):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{p}/api/tools', timeout=1) as r:
                if r.status == 200:
                    return f'检测到已有一个工坊在运行：http://127.0.0.1:{p}'
        except Exception:
            continue
    return ''


if __name__ == '__main__':
    print('==== 南信实验报告工坊 环境自检 ====\n')
    check('Python 运行时', check_python)
    check('python-docx 依赖', check_docx, '重新解压完整 zip')
    check('Pillow 依赖', check_pil, '重新解压完整 zip')
    check('data 目录可写', check_data_dir, '把文件夹移到 D 盘或桌面后再试')
    check('端口可用性', check_ports, '关闭占用 8765 的程序后重试')
    print()
    try:
        running = check_server_running()
        if running:
            print('[提示] ' + running)
    except Exception:
        pass
    print()
    if OK == 0:
        print('结论：环境正常，请双击 start.bat 启动。')
    else:
        print(f'结论：有 {OK} 项异常，请按上方建议处理后重试。')
    try:
        input('按回车键退出…')
    except EOFError:
        pass
