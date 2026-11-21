# -*- coding: utf-8 -*-
"""可选的大语言模型客户端（OpenAI 兼容协议，DeepSeek/通义/Kimi/GLM 等均可）。

不配置也能用：全部功能都有基于课程知识库的离线回退。
"""
import json
import os
import re
import urllib.request
import urllib.error

DEFAULT_CONFIG = {
    'enabled': False,
    'base_url': 'https://api.deepseek.com',
    'api_key': '',
    'model': 'deepseek-chat',
    'temperature': 0.4,
}


class LLMError(Exception):
    pass


def config_path(workdir):
    return os.path.join(workdir, 'config.json')


def load_config(workdir):
    p = config_path(workdir)
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(workdir, cfg):
    os.makedirs(workdir, exist_ok=True)
    with open(config_path(workdir), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def ready(cfg):
    return bool(cfg.get('enabled') and cfg.get('api_key') and cfg.get('base_url'))


def chat(cfg, messages, timeout=90, json_mode=False, max_tokens=4000):
    """调用 OpenAI 兼容 /chat/completions，返回助手回复文本。"""
    if not ready(cfg):
        raise LLMError('未启用或未配置 LLM API')
    url = cfg['base_url'].rstrip('/') + '/chat/completions'
    payload = {
        'model': cfg.get('model') or 'deepseek-chat',
        'messages': messages,
        'temperature': float(cfg.get('temperature', 0.4)),
        'max_tokens': max_tokens,
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + cfg['api_key']})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:300]
        raise LLMError(f'HTTP {e.code}: {detail}')
    except Exception as e:
        raise LLMError(f'请求失败: {e}')
    try:
        return body['choices'][0]['message']['content']
    except Exception:
        raise LLMError('响应格式异常: ' + json.dumps(body, ensure_ascii=False)[:300])


def _strip_fence(text):
    t = text.strip()
    m = re.search(r'```[a-zA-Z]*\s*\n(.*?)```', t, re.S)
    if m:
        return m.group(1).strip()
    return t


def generate_code(cfg, task_text, lang='c', template_hint=''):
    """按任务描述生成代码。失败抛 LLMError。"""
    sys_p = ('你是南京信息工程大学的C语言课程助教。根据实验任务写一个完整、可编译、'
             '带中文提示的C程序（单个 main 或必要函数）。只输出代码本身，不要解释。'
             '风格：stdio.h 开头、4空格缩进、变量先定义。') if lang == 'c' else \
            ('你根据任务写完整可运行的Python程序，只输出代码。')
    user_p = f'实验任务：{task_text}\n'
    if template_hint:
        user_p += f'（可参考模板中已给出的程序框架：\n{template_hint}\n）'
    out = chat(cfg, [{'role': 'system', 'content': sys_p},
                     {'role': 'user', 'content': user_p}], json_mode=False)
    return _strip_fence(out)


def generate_analysis(cfg, exp_name, task_texts, style_hint=''):
    """生成"分析与讨论"段落，返回 list[str]。"""
    sys_p = ('你是南京信息工程大学学生的实验报告写作助手。请以第一人称写"分析与讨论"，'
             '结合每个任务谈：算法思路、易错点/踩坑记录、效率或健壮性思考。'
             '语气朴实、具体、有细节，不要空话套话。用 JSON 返回：{"paragraphs": ["...", "..."]}，'
             '共 6~10 段，每段 40~120 字，可包含小标题段（如"关于xxx的思考"）。')
    user_p = f'实验名称：{exp_name}\n实验任务：\n' + '\n'.join(
        f'（{i+1}）{t}' for i, t in enumerate(task_texts))
    if style_hint:
        user_p += '\n参考风格：\n' + style_hint
    out = chat(cfg, [{'role': 'system', 'content': sys_p},
                     {'role': 'user', 'content': user_p}], json_mode=True)
    data = json.loads(_strip_fence(out))
    paras = data.get('paragraphs') or []
    return [str(p) for p in paras if str(p).strip()]


def parse_intent_ops(cfg, message, context_summary):
    """把自然语言修改要求解析成操作 JSON。返回 dict：
    {'ops': [...], 'reply': '...'}
    支持的 op：
      set_field{field,value} / set_paragraph{index,text} / delete_block{index}
      append_blocks{section,blocks} / clear_section{section}
      insert_image{after_index,path,width_in} / regenerate_task{no}
      rerun_task{no} / regenerate_analysis{}
    """
    sys_p = ('你是实验报告编辑助手。把用户的修改要求转换成 JSON 操作列表。'
             '可用操作（只输出 JSON，不输出其他内容）：\n'
             '{"ops":[{"op":"set_field","field":"姓名","value":"..."},'
             '{"op":"set_paragraph","index":18,"text":"..."},'
             '{"op":"delete_block","index":18},'
             '{"op":"append_blocks","section":"analysis","blocks":'
             '[{"type":"text","text":"..."},{"type":"image","path":"xxx.png"}]},'
             '{"op":"clear_section","section":"analysis"},'
             '{"op":"insert_image","after_index":18,"path":"xxx.png"},'
             '{"op":"regenerate_task","no":1},'
             '{"op":"rerun_task","no":1},'
             '{"op":"regenerate_analysis":1}}],"reply":"给用户的一句说明"}\n'
             'section 可选值：purpose/content/steps_result/result/analysis/steps。'
             '若用户要求无法映射为操作，返回空 ops 并在 reply 里说明。')
    out = chat(cfg, [{'role': 'system', 'content': sys_p},
                     {'role': 'user', 'content':
                      f'当前报告概况：{context_summary}\n用户要求：{message}'}],
               json_mode=True)
    data = json.loads(_strip_fence(out))
    return {'ops': data.get('ops') or [], 'reply': data.get('reply') or '已按要求处理。'}


def propose_commands(cfg, goal, tools_info):
    """根据目标提出需要在用户电脑上执行的命令。返回 list[dict]。"""
    sys_p = ('你是本地实验助手。根据目标提出要在 Windows 上执行的命令来产生实验报告素材'
             '（编译/运行程序、导出文件等）。只输出 JSON：'
             '{"commands":[{"label":"名称","command":"要执行的命令行",'
             '"run_in":"工作目录相对路径","stdin":"可选的标准输入","screenshot_after":false,'
             '"why":"目的说明"}]}。禁止破坏性命令（删除、格式化、联网下载等）。')
    out = chat(cfg, [{'role': 'system', 'content': sys_p},
                     {'role': 'user', 'content':
                      f'本机可用工具：{tools_info}\n目标：{goal}'}], json_mode=True)
    data = json.loads(_strip_fence(out))
    return data.get('commands') or []
