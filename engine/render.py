# -*- coding: utf-8 -*-
"""把文本渲染成实验报告里用的截图样式图片。

- render_code_png:    C/Python 代码 → VS Code 浅色主题风格的代码截图
- render_console_png: 程序真实运行输出 → 控制台窗口风格截图（黑底白字 + 标题栏）
- take_screenshot:    调用 PowerShell 截取真实屏幕（用于 AutoCAD 等软件的操作过程截图）
"""
import os
import re
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------------ 字体

_FONT_CANDIDATES = {
    'mono': ['consola.ttf', 'Consolas', 'COUR.ttf', 'Courier New',
             'msyh.ttc', '微软雅黑', 'simhei.ttf'],
    'cn':   ['msyh.ttc', '微软雅黑', 'simhei.ttf', 'simsun.ttc'],
}


def _load_font(size, kind='mono', bold=False):
    """在 Windows 字体目录里找一个可用字体。"""
    dirs = [os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')]
    names = list(_FONT_CANDIDATES[kind])
    if bold and kind == 'mono':
        names = ['consolab.ttf', 'CourB.ttf'] + names
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
            if os.path.isdir(p):
                continue
    # 最后尝试按字体名让 PIL 自己找
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_w(draw, s, font):
    try:
        return draw.textlength(s, font=font)
    except Exception:
        return font.size * len(s)


# ------------------------------------------------------------------ C 代码高亮

C_KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
    'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'inline',
    'int', 'long', 'register', 'restrict', 'return', 'short', 'signed',
    'sizeof', 'static', 'struct', 'switch', 'typedef', 'union', 'unsigned',
    'void', 'volatile', 'while',
}
C_COLORS = {
    'kw': (0, 16, 222),        # 关键字 蓝
    'str': (162, 21, 21),      # 字符串 暗红
    'num': (9, 134, 88),       # 数字 绿
    'comment': (0, 128, 0),    # 注释 绿
    'prep': (111, 66, 193),    # 预处理 紫
    'plain': (32, 32, 32),
}


def tokenize_c_line(line):
    """产出一个 token 列表 [(kind, text)]，kind ∈ kw/str/num/comment/prep/plain。"""
    tokens = []
    i, n = 0, len(line)
    s = line
    if s.lstrip().startswith('#'):
        # 预处理行：# 后的 include/define 等保持紫色，<> 内的文件名暗红
        m = re.match(r'^(\s*#\s*\w+)(.*)$', s)
        if m:
            tokens.append(('prep', m.group(1)))
            rest = m.group(2)
            m2 = re.match(r'^(\s*[<"][^>"]*[>"])(.*)$', rest)
            if m2:
                tokens.append(('str', m2.group(1)))
                tokens.append(('plain', m2.group(2)))
            else:
                tokens.append(('plain', rest))
            return tokens
        tokens.append(('prep', s))
        return tokens
    pat = re.compile(
        r'(?P<comment>//.*|/\*.*?\*/)'
        r'|(?P<str>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
        r'|(?P<num>\b\d+(?:\.\d+)?[fFuUlL]*\b)'
        r'|(?P<id>[A-Za-z_]\w*)'
        r'|(?P<other>.)'
    )
    while i < n:
        m = pat.match(s, i)
        if not m:
            tokens.append(('plain', s[i]))
            i += 1
            continue
        if m.lastgroup == 'comment':
            tokens.append(('comment', m.group(0)))
        elif m.lastgroup == 'str':
            tokens.append(('str', m.group(0)))
        elif m.lastgroup == 'num':
            tokens.append(('num', m.group(0)))
        elif m.lastgroup == 'id':
            w = m.group(0)
            tokens.append(('kw', w) if w in C_KEYWORDS else ('plain', w))
        else:
            tokens.append(('plain', m.group(0)))
        i = m.end()
    return tokens


def wrap_code_line(line, max_chars=62):
    """超长代码行折行，续行缩进 4 空格。"""
    if len(line) <= max_chars:
        return [line]
    out = []
    cur = line
    while len(cur) > max_chars:
        cut = max_chars if not out else max_chars - 4
        seg = cur[:cut]
        best = cut
        for ch in (',', ' ', ';', '(', ')', '+', '-', '*'):
            p = seg.rfind(ch)
            if p > cut * 0.6:
                best = p + 1
                break
        piece = seg[:best]
        out.append(piece if not out else '    ' + piece)
        cur = cur[best:]
    if cur:
        out.append(cur if not out else '    ' + cur)
    return out


def render_code_png(code, out_path, lang='c', font_size=17, max_width=780):
    """生成代码截图。返回输出路径。"""
    font = _load_font(font_size, 'mono')
    font_bold = _load_font(font_size, 'mono', bold=True)
    lh = int(font_size * 1.45)
    pad_l, pad_t = 26, 14
    lines = []
    for raw in code.rstrip('\n').split('\n'):
        raw = raw.replace('\t', '    ')
        lines.extend(wrap_code_line(raw) or [''])
    tmp = Image.new('RGB', (10, 10))
    dtxt = ImageDraw.Draw(tmp)
    # 按行累计宽度取最大（token 求和，而非单 token 最大值）
    line_widths = []
    for ln in lines:
        wsum = 0
        for _, t in tokenize_c_line(ln):
            f = font_bold if _is_keyword_token(t) else font
            wsum += _text_w(dtxt, t, f)
        line_widths.append(wsum)
    maxw = max(line_widths, default=200)
    width = max(360, min(max_width, int(maxw) + pad_l * 2))
    height = pad_t * 2 + lh * len(lines)
    img = Image.new('RGB', (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    y = pad_t
    for ln in lines:
        x = pad_l
        for kind, tok in tokenize_c_line(ln):
            color = C_COLORS.get(kind, C_COLORS['plain'])
            f = font_bold if kind == 'kw' else font
            d.text((x, y), tok, fill=color, font=f)
            x += _text_w(d, tok, f)
        y += lh
    img.save(out_path)
    return out_path


def _is_keyword_token(t):
    return t in C_KEYWORDS


# ------------------------------------------------------------------ 控制台窗口

def render_console_png(lines, out_path, title=None, font_size=16,
                       max_lines=38, max_cols=90):
    """把程序输出渲染成 Windows 控制台窗口截图。lines: list[str]"""
    font = _load_font(font_size, 'mono')
    cn_font = _load_font(font_size, 'cn')
    lh = int(font_size * 1.5)
    bar_h = 34
    pad_l, pad_t = 16, 12
    shown = []
    for ln in lines:
        ln = ln.replace('\t', '    ').rstrip('\n')
        while len(ln) > max_cols:
            shown.append(ln[:max_cols])
            ln = '  ' + ln[max_cols:]
        shown.append(ln)
    if len(shown) > max_lines:
        shown = shown[:max_lines] + ['... （输出过长已截断）']
    tmp = Image.new('RGB', (10, 10))
    d0 = ImageDraw.Draw(tmp)
    colw = max((_text_w(d0, s, font) for s in shown), default=300)
    width = min(1100, int(colw) + pad_l * 2 + 10)
    height = bar_h + pad_t * 2 + lh * len(shown)
    img = Image.new('RGB', (width, height), (12, 12, 12))
    d = ImageDraw.Draw(img)
    # 标题栏
    d.rectangle([0, 0, width, bar_h], fill=(43, 43, 43))
    tfont = _load_font(14, 'cn')
    d.text((12, 9), title or '命令提示符 — 程序运行结果', fill=(230, 230, 230), font=tfont)
    d.rectangle([width - 46, 0, width, bar_h], fill=(200, 60, 60))
    d.text((width - 34, 9), '✕', fill=(255, 255, 255), font=tfont)
    y = bar_h + pad_t
    for s in shown:
        x = pad_l
        # 中英文混排：逐字符选字体
        for ch in s:
            f = font if ord(ch) < 256 else cn_font
            color = (236, 236, 236)
            d.text((x, y), ch, fill=color, font=f)
            x += _text_w(d, ch, f)
        y += lh
    img.save(out_path)
    return out_path


# ------------------------------------------------------------------ 真实屏幕截图

PS_SCREENSHOT = r'''
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$bmp.Save($args[0], [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK"
'''


def take_screenshot(out_path, timeout=15):
    """全屏截图（PowerShell）。成功返回 True。"""
    ps1 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'tools', 'screenshot.ps1')
    if not os.path.exists(ps1):
        os.makedirs(os.path.dirname(ps1), exist_ok=True)
        with open(ps1, 'w', encoding='utf-8-sig') as f:
            f.write(PS_SCREENSHOT)
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', ps1, os.path.abspath(out_path)],
            capture_output=True, text=True, timeout=timeout)
        ok = os.path.exists(out_path) and os.path.getsize(out_path) > 1000
        return ok
    except Exception:
        return False


def find_executable(name, extra_dirs=()):
    """在 PATH 和常见目录里找可执行文件。"""
    p = shutil.which(name)
    if p:
        return p
    for d in extra_dirs:
        cand = os.path.join(d, name)
        if os.path.exists(cand):
            return cand
        cand += '.exe'
        if os.path.exists(cand):
            return cand
    return None


GCC_DIRS = [
    r'C:\MinGW\bin', r'C:\msys64\mingw64\bin', r'C:\TDM-GCC-64\bin',
    r'C:\Program Files\CodeBlocks\MinGW\bin',
    r'C:\Program Files (x86)\Dev-Cpp\MinGW64\bin',
    r'C:\Program Files\Dev-Cpp\MinGW64\bin',
]


def find_gcc():
    return find_executable('gcc', GCC_DIRS)


def find_soffice():
    dirs = [r'C:\Program Files\LibreOffice\program',
            r'C:\Program Files (x86)\LibreOffice\program']
    return find_executable('soffice', dirs)


ACAD_DIRS = [
    r'C:\Program Files\Autodesk', r'C:\Program Files\Autodesk\AutoCAD 2024',
    r'C:\Program Files\Autodesk\AutoCAD 2023',
    r'C:\Program Files\Autodesk\AutoCAD 2022',
    r'C:\Program Files\Autodesk\AutoCAD 2020 - Simplified Chinese',
]


def find_acad():
    for root in ACAD_DIRS:
        if os.path.isdir(root):
            for dirpath, _, files in os.walk(root):
                if 'acad.exe' in [f.lower() for f in files]:
                    return os.path.join(dirpath, 'acad.exe')
    return find_executable('acad', ACAD_DIRS)
