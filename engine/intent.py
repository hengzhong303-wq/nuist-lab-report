# -*- coding: utf-8 -*-
"""把用户的自然语言修改要求解析成文档操作（离线规则；LLM 增强在 llm.parse_intent_ops）。

返回 (ops, reply)。ops 为 dict 列表，由 server.apply_ops 执行。
"""
import re

FIELD_WORDS = {
    '姓名': 'student_name', '学号': 'sid', '学院': 'college',
    '专业': 'major', '年级': 'grade', '班次': 'class', '班级': 'class',
    '指导教师': 'teacher', '指导老师': 'teacher', '老师': 'teacher',
    '实验名称': 'exp_name', '实验日期': 'date', '日期': 'date',
}
SECTION_WORDS = {
    '分析与讨论': 'analysis', '分析讨论': 'analysis', '分析': 'analysis',
    '心得': 'analysis', '心得体会': 'analysis', '讨论': 'analysis',
    '实验目的': 'purpose', '目的': 'purpose',
    '实验内容': 'content', '内容': 'content',
    '实验步骤': 'steps_result', '步骤': 'steps_result',
    '实验步骤和实验结果': 'steps_result', '实验步骤与结果': 'steps_result',
    '步骤和实验结果': 'steps_result',
    '实验结果': 'result', '结果': 'result',
}


def parse(message):
    """返回 (ops, reply, need_llm)。"""
    ops = []
    notes = []
    m = message.strip()

    # 1) 字段修改：把姓名改成张三 / 学号：2026xxx
    for match in re.finditer(
            r'(?:把|将)?\s*(姓名|学号|学院|专业|年级|班次|班级|指导教师|指导老师|实验名称|实验日期)\s*'
            r'(?:改成|改为|设为|设置为|填为|换成|换成|改为|是|为|:|：)\s*(\S.*)', m):
        key = FIELD_WORDS.get(match.group(1))
        val = match.group(2).strip().strip('。；;')
        if key and val:
            ops.append({'op': 'set_field', 'field': key, 'value': val})
            notes.append(f'{match.group(1)} → {val}')

    # 2) 插入图片/截图：插入图片 xxx.png / 把 xxx.png 插到结果里
    for match in re.finditer(r'(?:插入|添加|加入)(?:一张)?(?:图片|截图|照片)\s*[:：]?\s*([\w\u4e00-\u9fa5\-\. ]+\.(?:png|jpg|jpeg|gif|bmp))?', m, re.I):
        name = (match.group(1) or '').strip()
        ops.append({'op': 'insert_image', 'path': name, 'resolve': True})
        notes.append(f'插入图片 {name or "(请指明文件)"}')

    # 3) 重新生成第N题 / 换一种思路
    for match in re.finditer(r'第\s*（?(\d+)）?\s*题', m):
        no = match.group(1)
        if re.search(r'重新生成|重写|换一种|换个思路|换思路|改代码|重新写', m):
            ops.append({'op': 'regenerate_task', 'no': no})
            notes.append(f'重新生成第（{no}）题')
        elif re.search(r'重新运行|再运行|重新截图|编译运行|跑一下|运行一下', m):
            ops.append({'op': 'rerun_task', 'no': no})
            notes.append(f'重新运行第（{no}）题')

    # 4) 修改指定段落
    for match in re.finditer(r'把第\s*(\d+)\s*段\s*(?:改成|改为|换成)\s*(.+)', m):
        ops.append({'op': 'set_paragraph', 'index': int(match.group(1)),
                    'text': match.group(2).strip()})
        notes.append(f'修改第 {match.group(1)} 段')

    # 5) 删除段落 / 删除第N题
    for match in re.finditer(r'删除第\s*(\d+)\s*段', m):
        ops.append({'op': 'delete_block', 'index': int(match.group(1))})
        notes.append(f'删除第 {match.group(1)} 段')

    # 6) 重写/清空章节
    sec_key = None
    for word, key in SECTION_WORDS.items():
        if word in m and re.search(r'重写|清空|重新生成|重新写|换一段', m):
            sec_key = key
            break
    if sec_key == 'analysis':
        ops.append({'op': 'regenerate_analysis'})
        notes.append('重写分析与讨论')
    elif sec_key in ('steps_result', 'result', 'steps'):
        ops.append({'op': 'clear_section', 'section': sec_key})
        notes.append(f'已清空章节 {sec_key}')

    # 7) 在分析里补充内容
    for match in re.finditer(r'(?:在分析(?:与讨论)?里?(?:面|中)?)?(加上|添加|补充|追加)\s*[:：]?\s*(.{4,})', m):
        text = match.group(2).strip().strip('。')
        if text and not any(o['op'] in ('regenerate_analysis',) for o in ops):
            ops.append({'op': 'append_blocks', 'section': 'analysis',
                        'blocks': [{'type': 'text', 'text': text}]})
            notes.append(f'分析中补充：{text[:20]}…')

    # 8) 重写某一段分析（把分析第2段改成…）
    for match in re.finditer(r'分析(?:与讨论)?第\s*(\d+)\s*段\s*(?:改成|改为|换成)\s*(.+)', m):
        ops.append({'op': 'set_analysis_para', 'index': int(match.group(1)),
                    'text': match.group(2).strip()})
        notes.append(f'修改分析第 {match.group(1)} 段')

    if not ops:
        return [], '', True
    reply = '好的：' + '；'.join(notes) + '。'
    return ops, reply, False


HELP_TEXT = (
    '我可以帮你这样改报告：\n'
    '• 「把姓名改成张三」「学号：2026xxxx」「指导教师改成潘老师」——填写信息\n'
    '• 「第2题重新生成代码」「第3题换一种思路」——重新生成某题\n'
    '• 「第1题重新运行」——重新编译运行并更新结果截图\n'
    '• 「插入图片 result.png」——把上传的图片插入报告（随后会问插到哪里）\n'
    '• 「重写分析与讨论」「在分析里补充：……」——修改心得部分\n'
    '• 「把第12段改成……」「删除第15段」——精确修改段落（段落编号见预览中点击段落）\n'
    '• 也可以直接说需求，比如「帮我再截一张 AutoCAD 的图」——我会请求执行权限'
)
