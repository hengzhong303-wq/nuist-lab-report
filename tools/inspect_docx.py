# -*- coding: utf-8 -*-
"""解析 docx 的结构：段落顺序/样式/字体/对齐、表格、图片，导出内嵌图片。"""
import sys, os, zipfile
from docx import Document
from docx.document import Document as _Doc
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from docx.shared import Pt

def iter_blocks(parent):
    parent_elm = parent.element.body if isinstance(parent, _Doc) else parent._element
    for child in parent_elm.iterchildren():
        if child.tag == qn('w:p'):
            yield ('p', Paragraph(child, parent))
        elif child.tag == qn('w:tbl'):
            yield ('t', Table(child, parent))

def east_font(run):
    rPr = run._element.rPr
    if rPr is None: return ''
    rf = rPr.find(qn('w:rFonts'))
    if rf is None: return ''
    return rf.get(qn('w:eastAsia')) or rf.get(qn('w:ascii')) or ''

def dump(path, out_img_dir):
    os.makedirs(out_img_dir, exist_ok=True)
    doc = Document(path)
    print(f'=== FILE: {path} ===')
    for i, sec in enumerate(doc.sections):
        print(f'[SECTION {i}] page={sec.page_width}x{sec.page_height} '
              f'margins T{sec.top_margin} B{sec.bottom_margin} L{sec.left_margin} R{sec.right_margin}')
        # header text
        hdr = sec.header
        if hdr is not None:
            for p in hdr.paragraphs:
                if p.text.strip():
                    print(f'  [HEADER] "{p.text}"')
    img_count = 0
    p_idx = 0; t_idx = 0
    for kind, block in iter_blocks(doc):
        if kind == 'p':
            p = block
            p_idx += 1
            txt = p.text
            runs_info = []
            for r in p.runs:
                if r.text:
                    sz = r.font.size.pt if r.font.size else None
                    runs_info.append(f'"{r.text[:30]}"(f={east_font(r)},sz={sz},b={r.font.bold})')
            imgs = []
            for blip in p._element.iter(qn('a:blip')):
                rid = blip.get(qn('r:embed'))
                if rid:
                    imgs.append(rid)
            style = p.style.name if p.style is not None else '?'
            align = p.alignment
            line = f'[P{p_idx:03d}] style={style} align={align}'
            if runs_info: line += ' runs=' + ' | '.join(runs_info[:4])
            if imgs: line += f' IMAGES={imgs}'
            if txt.strip() or imgs or runs_info:
                print(line + f' TEXT="{txt}"')
            for rid in imgs:
                try:
                    part = doc.part.related_parts[rid]
                    ext = os.path.splitext(part.partname)[1] or '.png'
                    img_count += 1
                    fn = os.path.join(out_img_dir, f'p{p_idx:03d}_{img_count:02d}{ext}')
                    with open(fn, 'wb') as f:
                        f.write(part.blob)
                    print(f'    -> saved {fn} ({len(part.blob)} bytes)')
                except Exception as e:
                    print(f'    -> img {rid} error {e}')
        else:
            t = block
            t_idx += 1
            print(f'[TABLE {t_idx:02d}] rows={len(t.rows)} cols={len(t.columns)} style={t.style.name if t.style else "?"}')
            for ri, row in enumerate(t.rows):
                cells = []
                seen = set()
                for c in row.cells:
                    key = id(c._element)
                    marker = '' if key not in seen else '(merged)'
                    seen.add(key)
                    cells.append(f'{c.text!r}{marker}')
                print(f'   row{ri}: ' + ' | '.join(cells))
    print(f'=== END ({p_idx} paragraphs, {t_idx} tables, {img_count} images) ===\n')

if __name__ == '__main__':
    if len(sys.argv) >= 4:  # docx imgdir outfile -> write UTF-8 file
        _out = open(sys.argv[3], 'w', encoding='utf-8')
        _stdout = sys.stdout
        sys.stdout = _out
        try:
            dump(sys.argv[1], sys.argv[2])
        finally:
            sys.stdout = _stdout
            _out.close()
    else:
        dump(sys.argv[1], sys.argv[2])
