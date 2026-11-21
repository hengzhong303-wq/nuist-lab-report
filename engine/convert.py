# -*- coding: utf-8 -*-
"""文档格式转换：docx→PDF（LibreOffice 优先，Word COM 兜底）、doc→docx。"""
import os
import subprocess

from .render import find_soffice


def _word_com_convert(src, dst, wd_format=17):
    """用已安装的 Microsoft Word 转换（17=PDF, 16=docx）。"""
    ps = f'''
$w = New-Object -ComObject Word.Application
$w.Visible = $false
try {{
  $doc = $w.Documents.Open("{src.replace(chr(92), '/')}", ConfirmConversions=$false)
  $doc.SaveAs([ref]"{dst.replace(chr(92), '/')}", [ref]{wd_format})
  $doc.Close($false)
  Write-Output "OK"
}} finally {{ $w.Quit() }}
'''
    r = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                       capture_output=True, text=True, timeout=120)
    return os.path.exists(dst)


def docx_to_pdf(src, out_dir):
    """返回 (pdf_path|None, err_msg|None)。"""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    out_pdf = os.path.join(out_dir, base + '.pdf')
    soffice = find_soffice()
    if soffice:
        try:
            r = subprocess.run(
                [soffice, '--headless', '--convert-to', 'pdf',
                 '--outdir', out_dir, src],
                capture_output=True, text=True, timeout=180)
            if os.path.exists(out_pdf):
                return out_pdf, None
        except Exception as e:
            pass
    try:
        if _word_com_convert(os.path.abspath(src), os.path.abspath(out_pdf)):
            return out_pdf, None
        return None, 'Word COM 转换失败'
    except Exception as e:
        return None, f'转换失败：{e}（本机未检测到 LibreOffice / Word）'


def doc_to_docx(src, out_dir):
    """旧版 .doc → .docx，需要 Word。"""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    out = os.path.join(out_dir, base + '.docx')
    try:
        if _word_com_convert(os.path.abspath(src), os.path.abspath(out), 16):
            return out, None
        return None, 'Word COM 转换失败'
    except Exception as e:
        return None, f'转换失败：{e}（本机未检测到 Word）'
