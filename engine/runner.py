# -*- coding: utf-8 -*-
"""本地命令执行器：所有命令都必须经用户在网页上批准后才会运行。

- run_c_program: 编译并运行 C 程序，捕获输出 → 控制台截图
- execute_command: 执行任意已批准命令（记录日志）
- detect_tools: 探测 gcc / AutoCAD / LibreOffice / Python
"""
import os
import subprocess
import time

from .render import render_console_png, find_gcc, find_acad, find_soffice


def _decode(b):
    if b is None:
        return ''
    for enc in ('utf-8', 'gbk', 'utf-16'):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('utf-8', 'replace')


def detect_tools():
    return {
        'gcc': find_gcc(),
        'acad': find_acad(),
        'soffice': find_soffice(),
        'python': None if __import__('sys').executable is None else __import__('sys').executable,
    }


def execute_command(command, workdir, timeout=60, stdin_text=None, log_file=None):
    """执行一条已获用户批准的命令。command 为字符串（cmd /c 语义）。"""
    os.makedirs(workdir, exist_ok=True)
    out_path = os.path.join(workdir, '_cmd_out.txt')
    err_path = os.path.join(workdir, '_cmd_err.txt')
    in_path = None
    stdin_arg = None
    if stdin_text:
        in_path = os.path.join(workdir, '_cmd_in.txt')
        with open(in_path, 'w', encoding='utf-8') as f:
            f.write(stdin_text)
        stdin_arg = open(in_path, 'r', encoding='utf-8')
    t0 = time.time()
    try:
        with open(out_path, 'w', encoding='utf-8') as fo, \
                open(err_path, 'w', encoding='utf-8') as fe:
            p = subprocess.run(
                command, cwd=workdir, shell=True,
                stdin=stdin_arg, stdout=fo, stderr=fe, timeout=timeout)
            rc = p.returncode
        ok = rc == 0
    except subprocess.TimeoutExpired:
        rc = -1
        ok = False
        with open(err_path, 'a', encoding='utf-8') as fe:
            fe.write(f'\n[超时：超过 {timeout} 秒已终止]')
    except Exception as e:
        rc = -2
        ok = False
        with open(err_path, 'a', encoding='utf-8') as fe:
            fe.write(str(e))
    finally:
        if stdin_arg:
            stdin_arg.close()
    stdout = ''
    stderr = ''
    try:
        with open(out_path, 'rb') as f:
            stdout = _decode(f.read())
    except Exception:
        pass
    try:
        with open(err_path, 'rb') as f:
            stderr = _decode(f.read())
    except Exception:
        pass
    result = {'ok': ok, 'returncode': rc, 'stdout': stdout,
              'stderr': stderr, 'duration': round(time.time() - t0, 2),
              'command': command}
    if log_file:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] $ {command}\n"
                        f"exit={rc}\n{stdout[:2000]}\n---\n")
        except Exception:
            pass
    for tmp in (out_path, err_path, in_path):
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
    return result


def run_c_program(code, stdin_text, workdir, name='task', timeout=30):
    """编译运行 C 程序。返回 dict：
    ok, reason, compile_log, output, png(控制台截图路径), exe
    """
    os.makedirs(workdir, exist_ok=True)
    gcc = find_gcc()
    if not gcc:
        return {'ok': False, 'reason': '未找到 gcc 编译器（可安装 MinGW/Dev-C++ 后重试）'}
    c_path = os.path.join(workdir, f'{name}.c')
    exe_path = os.path.join(workdir, f'{name}.exe')
    with open(c_path, 'w', encoding='utf-8') as f:
        f.write(code)
    comp = execute_command(f'"{gcc}" "{c_path}" -o "{exe_path}" -w',
                           workdir, timeout=60)
    if not comp['ok']:
        return {'ok': False, 'reason': '编译失败',
                'compile_log': (comp['stderr'] or comp['stdout'])[:1500]}
    stdin_text = stdin_text if stdin_text is not None else ''
    r = execute_command(f'"{exe_path}"', workdir, timeout=timeout,
                        stdin_text=stdin_text or None)
    output = (r['stdout'] or '')
    if r['stderr']:
        output += ('\n[stderr] ' + r['stderr'])
    png = None
    if output.strip():
        lines = [f'D:\\...\\报告工程> {name}.exe'] + output.rstrip().split('\n')
        png = os.path.join(workdir, 'artifacts', f'console_{name}.png')
        os.makedirs(os.path.dirname(png), exist_ok=True)
        render_console_png(lines, png, title=f'{name}.exe — 运行结果')
    return {'ok': True, 'output': output, 'png': png,
            'exe': exe_path, 'timed_out': rc_timeout(r)}


def rc_timeout(r):
    return r.get('returncode') == -1
