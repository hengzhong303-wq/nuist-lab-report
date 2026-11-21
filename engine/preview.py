# -*- coding: utf-8 -*-
"""把生成中的 docx 渲染成网页预览 HTML（A4 纸样式）。

直接读取保存后的 docx（单一事实来源），并把内嵌图片导出到会话目录供网页显示。
"""
import os
import re

from .docmodel import scan_doc


def _esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def _extract_images(doc, cache_dir):
    """把文档里的图片 rid 导出为文件，返回 rid→文件名。"""
    os.makedirs(cache_dir, exist_ok=True)
    mapping = {}
    try:
        rels = doc.part.related_parts
    except Exception:
        return mapping
    for rid, part in rels.items():
        if 'image' in str(getattr(part, 'content_type', '')):
            ext = os.path.splitext(str(part.partname))[1] or '.png'
            fn = f'img_{re.sub(r"[^0-9a-zA-Z]", "_", rid)}{ext}'
            p = os.path.join(cache_dir, fn)
            if not os.path.exists(p):
                try:
                    with open(p, 'wb') as f:
                        f.write(part.blob)
                except Exception:
                    continue
            mapping[rid] = fn
    return mapping


def _inline_field_hints(text, fields):
    """给表单/页眉文本里的字段下划线高亮（预览美化用）。"""
    return text


def render_preview(docx_path, cache_dir):
    """返回 (html, images)。images: [{'url': '/api/files/<sid>/img/xx.png', 'width_px': int}]"""
    from docx import Document
    from .docmodel import _iter_blocks, _suggest_width  # 复用迭代与宽度建议
    doc = Document(docx_path)
    img_map = _extract_images(doc, cache_dir)
    sc = scan_doc(doc)

    def w_px(path_rid):
        # 用文件真实比例估显示宽度
        return None

    html = ['<div class="doc">']
    # 页眉信息栏（南信大模板的信息在页眉里，预览中置顶展示）
    for hl in sc.get('header_lines', []):
        t = hl['text']
        cls = 'hdr-title' if '实验（实习）报告' in t or '实验报告' in t else 'hdr-line'
        html.append(f'<p class="{cls}">{_esc(t)}</p>')
    if sc.get('header_lines'):
        html.append('<div class="hdr-sep"></div>')
    for b in sc['blocks']:
        if b['kind'] == 'tbl':
            html.append('<table class="tbl">')
            for row in b['rows']:
                html.append('<tr>' + ''.join(f'<td>{_esc(c)}</td>' for c in row) + '</tr>')
            html.append('</table>')
            continue
        text = b['text']
        style = b['style'] or ''
        cls = 'p'
        if style.lower().startswith('title'):
            cls = 'doc-title'
        elif b['heading']:
            cls = 'h4'
        elif style in ('程序', 'Code', '代码'):
            cls = 'code'
        imgs_html = ''
        for rid in b['images']:
            fn = img_map.get(rid)
            if fn:
                from PIL import Image
                p = os.path.join(cache_dir, fn)
                wpx = 480
                try:
                    with Image.open(p) as im:
                        iw, ih = im.size
                    ratio = ih / max(1, iw)
                    wpx = int(_suggest_width(p) * 96)
                except Exception:
                    pass
                imgs_html += (f'<img src="img/{fn}" style="width:{wpx}px" '
                              f'class="doc-img">')
        content = _esc(text) if text.strip() else ''
        if content or imgs_html:
            data = f' data-idx="{b["idx"]}"'
            html.append(f'<{ "div" if cls=="code" else "p"} class="{cls}"{data}>'
                        f'{content}{imgs_html}</{"div" if cls=="code" else "p"}>')
    html.append('</div>')
    images = [{'url': f'img/{fn}'} for fn in img_map.values()]
    return '\n'.join(html), images


PAGE_CSS = '''
body{background:#525659;margin:0;padding:24px 0;}
.doc{background:#fff;width:820px;min-height:1060px;margin:0 auto 24px auto;
 padding:64px 72px;box-shadow:0 2px 8px rgba(0,0,0,.4);
 font-family:"宋体","SimSun",serif;font-size:15px;line-height:1.7;color:#111;}
.doc p{margin:6px 0;}
.doc-title{font-size:22px;font-weight:700;text-align:center;font-family:"黑体","SimHei";margin:18px 0;}
.h4{font-weight:700;font-family:"黑体","SimHei";font-size:16px;margin:14px 0 8px 0;}
.code{font-family:"Consolas","Courier New",monospace;font-size:13px;line-height:1.35;
 margin:2px 0;white-space:pre-wrap;background:#fafafa;border-left:3px solid #d0d0d0;padding:2px 8px;}
.doc-img{display:block;margin:8px auto;max-width:95%;border:1px solid #eee;}
.tbl{border-collapse:collapse;width:100%;margin:8px 0;}
.tbl td{border:1px solid #666;padding:4px 8px;font-size:14px;}
.hdr-title{text-align:center;font-family:"黑体","SimHei";font-size:18px;
 font-weight:700;margin:2px 0 6px 0;}
.hdr-line{font-size:12.5px;margin:3px 0;color:#222;}
.hdr-sep{border-bottom:2px solid #8a8a8a;margin:8px 0 16px 0;}
'''
