# -*- coding: utf-8 -*-
"""生成两份与南信大真实模板结构一致的示例空模板（用于演示与测试）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm


def set_cn(run, name='宋体', size=12, bold=False):
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    r = run._element.rPr
    from docx.oxml.ns import qn
    rFonts = r.rFonts if r.rFonts is not None else r.get_or_add_rFonts()
    rFonts.set(qn('w:eastAsia'), name)


def make_c_template(out):
    """仿「学号 姓名 实验报告-N xxx.docx」C语言空模板。"""
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(4.3)
    # 页眉三行
    hdr = sec.header.paragraphs[0]
    hdr.text = ''
    set_cn(hdr.add_run('南京信息工程大学   实验（实习）报告'), '黑体', 14, True)
    hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h2 = sec.header.add_paragraph()
    set_cn(h2.add_run('实验（实习）名称     数组及其应用     实验（实习）日期 05.13 '
                      '得分     指导教师   XXX     '), '宋体', 10.5)
    h3 = sec.header.add_paragraph()
    set_cn(h3.add_run('学院              专业               年级      班次      '
                      '姓名         学号              '), '宋体', 10.5)

    def h4(text):
        p = doc.add_heading(text, level=4)
        for r in p.runs:
            set_cn(r, '黑体', 14)
        return p

    def normal(text):
        p = doc.add_paragraph()
        set_cn(p.add_run(text), '宋体', 12)
        return p

    def code(text):
        p = doc.add_paragraph()
        try:
            p.style = doc.styles['程序']
        except KeyError:
            from docx.enum.style import WD_STYLE_TYPE
            st = doc.styles.add_style('程序', WD_STYLE_TYPE.PARAGRAPH)
            st.font.name = 'Consolas'
            st.font.size = Pt(10.5)
            p.style = st
        set_cn(p.add_run(text), '宋体', 10.5)
        return p

    h4('1．实验目的')
    normal('（1）巩固C语言数组的概念及基本操作。')
    normal('（2）会利用数组实现基本的算法。')
    normal('（3）掌握数组作为函数参数的方法。')
    h4('2．实验内容')
    normal('（1）运行下面的C程序，根据运行结果，可以说明什么？')
    code('#include <stdio.h>\nint  main( )\n{ \n\t  int num[5]={1,2,3,4,5};\n'
         '\t  int i;\n\t  for(i=0;i<=5;i++)\n\t     printf("%d ",num[i]);\n'
         '\t  printf("\\n");\n\t  return 0;\n}')
    normal('（2）为一个冒泡排序程序设计测试用例，并测试之。')
    normal('（3）设计一个程序，返回一个3×5的二维数组各元素的地址，'
           '并由此说明二维数组中各元素是按什么顺序存储的。')
    h4('3．实验步骤和实验结果')
    doc.add_paragraph()
    doc.add_paragraph()
    h4('4．分析与讨论')
    doc.add_paragraph()
    doc.save(out)
    return out


def make_drawing_template(out):
    """仿「实验2.docx」工程制图空模板。"""
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2.5)
    sec.left_margin = Cm(3.0)
    title = doc.add_heading('南京信息工程大学 实验报告', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in title.runs:
        set_cn(r, '黑体', 22, True)

    def form(text):
        p = doc.add_paragraph()
        p.style = doc.styles['Heading 5']
        set_cn(p.add_run(text), '宋体', 12)
        return p

    form('实验名称                                日期            得分            ')
    form('                学院                  专业                            班次')
    form('学号                          姓名                     指导老师            ')

    def h4(text):
        p = doc.add_heading(text, level=4)
        for r in p.runs:
            set_cn(r, '黑体', 14)
        return p

    def normal(text):
        p = doc.add_paragraph()
        set_cn(p.add_run(text), '宋体', 12)
        return p

    h4('一、实验目的')
    normal('1、熟悉AutoCAD的基本操作；')
    normal('2、掌握图层的设置与使用；')
    normal('3、应用AutoCAD绘制简单二维图形并标注尺寸。')
    h4('二、实验内容')
    normal('根据图一所示尺寸准确绘制出图形，并完成尺寸标注。')
    h4('三、实验步骤')
    doc.add_paragraph()
    h4('四、实验结果')
    doc.add_paragraph()
    doc.save(out)
    return out


if __name__ == '__main__':
    out_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'samples')
    os.makedirs(out_dir, exist_ok=True)
    p1 = make_c_template(os.path.join(out_dir, '示例模板-C语言-数组及其应用.docx'))
    p2 = make_drawing_template(os.path.join(out_dir, '示例模板-工程制图.docx'))
    print('生成完成：', p1)
    print('生成完成：', p2)
