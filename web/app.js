/* 南信实验报告工坊 - 前端逻辑 */
const $ = (s) => document.querySelector(s);
const SID = localStorage.getItem('lab_sid') || (() => {
  const sid = 's' + Math.random().toString(36).slice(2, 10);
  localStorage.setItem('lab_sid', sid);
  return sid;
})();

let STATE = null;
let selectedPara = null;
let previewRev = -1;

/* ---------------- 基础 ---------------- */
function toast(msg, err) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = err ? 'err' : '';
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.hidden = true), 3200);
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.status);
  return data;
}

const post = (p, body) => api(p.includes('?') ? p : `${p}?sid=${SID}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
});

/* ---------------- 状态轮询 ---------------- */
async function poll() {
  try {
    const data = await api(`/api/state?sid=${SID}&since=${STATE ? STATE.rev : 0}`);
    if (data.unchanged) return;
    STATE = data;
    renderState();
  } catch (e) { /* 服务未启动时静默 */ }
}
setInterval(poll, 1300);
poll();

/* ---------------- 渲染 ---------------- */
function renderState() {
  const st = STATE;
  // 工具状态 chips
  const chips = [];
  chips.push(`<span class="chip-status ${st.tools.gcc ? '' : 'off'}" title="C 编译器">gcc ${st.tools.gcc ? '√' : '×'}</span>`);
  chips.push(`<span class="chip-status ${st.tools.acad ? '' : 'off'}" title="AutoCAD">CAD ${st.tools.acad ? '√' : '×'}</span>`);
  chips.push(`<span class="chip-status ${st.llm.ready ? '' : 'off'}">AI ${st.llm.ready ? st.llm.model : '未配置'}</span>`);
  $('#chip-tools').innerHTML = chips.join('');

  // 模板信息
  if (st.template_name) {
    $('#tpl-info').hidden = false;
    $('#tpl-name').textContent = st.template_name;
    const secs = st.sections.map(s => s.title).join(' / ');
    $('#tpl-meta').textContent =
      `章节：${secs || '（未识别到章节标题）'}　任务数：${st.tasks.length}`;
    $('#drop').style.display = 'none';
  }

  // 个人信息表单（避免覆盖正在输入的内容）
  for (const input of document.querySelectorAll('#profile-form input')) {
    const k = input.dataset.k;
    if (document.activeElement !== input && st.profile[k] !== undefined) {
      input.value = st.profile[k];
    }
  }
  if (document.activeElement !== $('#requirement') && st.requirement) {
    $('#requirement').value = st.requirement;
  }
  $('#run-programs').checked = st.run_programs;

  // 素材
  const thumbs = [];
  for (const name of st.uploads) {
    if (!/\.(png|jpe?g|gif|bmp)$/i.test(name)) continue;
    thumbs.push(`
      <div class="thumb">
        <img src="/api/files/${st.sid}/uploads/${encodeURIComponent(name)}">
        <div class="tname" title="${name}">${name}</div>
        <button class="tbtn" data-act="insert" data-path="${name}">插入报告</button>
      </div>`);
  }
  $('#asset-list').innerHTML = thumbs.join('') || '<span class="hint">还没有上传图片</span>';
  document.querySelectorAll('.thumb .tbtn').forEach(b =>
    b.onclick = () => insertImage(b.dataset.path));

  // 生成详情
  if (st.generated) {
    $('#gen-detail').innerHTML =
      `<b>已生成</b>（${st.template_name}）\n课程：${courseName(st.course)}\n` +
      `识别任务：${st.tasks.map(t => `（${t.no}）${t.text.slice(0, 18)}`).join('；') || '—'}\n` +
      `素材截图：${st.artifacts.length} 张（artifacts 目录）`;
  }

  // 聊天记录
  const list = $('#chat-list');
  list.innerHTML = st.chat.map(m =>
    `<div class="msg ${m.role}">${esc(m.text)}<span class="ts">${m.ts}</span></div>`
  ).join('') + renderResults(st.history.filter(h => h && h.label));
  list.scrollTop = list.scrollHeight;

  // 待批准命令
  renderPending(st.pending);

  // 预览
  if (st.generated && st.rev !== previewRev) {
    previewRev = st.rev;
    $('#preview').src = `/api/preview?sid=${SID}&t=${Date.now()}`;
  } else if (!st.generated && previewRev !== -2) {
    previewRev = -2;
    $('#preview').src = `/api/preview?sid=${SID}`;
  }
}

function courseName(c) {
  return c === 'c' ? 'C语言程序设计' : c === 'drawing' ? '工程制图（AutoCAD）' : (c || '未指定');
}

function esc(s) {
  return String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

function renderResults(history) {
  return history.filter(h => h).map(h => `
    <div class="cmd-result" style="align-self:stretch">
      <b>${esc(h.label)}</b> ${h.ok ? '✅' : '❌'} <span class="hint">(${h.duration}s)</span>
      ${h.output ? `<div style="font-family:Consolas,monospace;font-size:11px;margin-top:4px;white-space:pre-wrap;max-height:110px;overflow:auto">${esc(h.output.slice(0, 800))}</div>` : ''}
      ${h.screenshot ? `<img class="shot" src="/api/files/${STATE.sid}/artifacts/${encodeURIComponent(h.screenshot)}" data-path="${h.screenshot}" title="点击插入报告">` : ''}
      ${h.screenshot ? `<button class="tbtn" style="width:100%" data-act="insert" data-path="${h.screenshot}">插入报告</button>` : ''}
    </div>`).join('');
}

function renderPending(pending) {
  const box = $('#pending-box');
  if (!pending || !pending.length) { box.hidden = true; return; }
  box.hidden = false;
  $('#pending-list').innerHTML = pending.map(c => `
    <div class="pcmd">
      <div class="lbl">▸ ${esc(c.label)}</div>
      <div class="cmd">${esc(c.command)}</div>
      ${c.why ? `<div class="why">目的：${esc(c.why)}</div>` : ''}
      <div class="btns">
        <button class="btn primary small" data-id="${c.id}" data-ok="1">✓ 批准执行</button>
        <button class="btn danger small" data-id="${c.id}" data-ok="0">✗ 拒绝</button>
      </div>
    </div>`).join('');
  document.querySelectorAll('#pending-list button').forEach(b =>
    b.onclick = async () => {
      const r = await post('/api/agent/approve', {
        sid: SID, ids: [b.dataset.id], approve: b.dataset.ok === '1',
      });
      if (b.dataset.ok === '0') toast('已拒绝该命令');
      poll();
    });
}

/* ---------------- 事件绑定 ---------------- */
// 模板上传
const drop = $('#drop');
drop.onclick = () => $('#file-template').click();
$('#file-template').onchange = (e) => uploadTemplate(e.target.files[0]);
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
drop.ondragleave = () => drop.classList.remove('over');
drop.ondrop = (e) => {
  e.preventDefault();
  drop.classList.remove('over');
  uploadTemplate(e.dataTransfer.files[0]);
};

async function uploadTemplate(file) {
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  $('#drop-label').textContent = '上传解析中…';
  try {
    const r = await fetch(`/api/upload/template?sid=${SID}`, { method: 'POST', body: fd });
    const data = await r.json();
    if (!data.ok) throw new Error(data.error);
    toast(`模板解析成功：${Object.keys(data.fields).length} 个字段 / ${data.sections.length} 章节 / ${data.tasks.length} 任务`);
  } catch (e) {
    toast('上传失败：' + e.message, true);
  }
  $('#drop-label').innerHTML = '把模板 <b>docx</b> 拖到这里，或点击选择';
  poll();
}

// 个人信息实时保存
let profileTimer = null;
$('#profile-form').addEventListener('input', () => {
  clearTimeout(profileTimer);
  profileTimer = setTimeout(saveProfile, 600);
});
async function saveProfile() {
  const profile = {};
  document.querySelectorAll('#profile-form input').forEach(i => profile[i.dataset.k] = i.value);
  await post('/api/profile', { sid: SID, profile });
  poll();
}

// 实验要求 & 课程 & 自动运行
$('#requirement').addEventListener('change', async () => {
  await post('/api/profile', { sid: SID, profile: {}, requirement: $('#requirement').value });
});
$('#course-sel').addEventListener('change', saveGenerateOptions);
$('#run-programs').addEventListener('change', async () => {
  await post('/api/run_programs', { sid: SID, enabled: $('#run-programs').checked });
});

function saveGenerateOptions() { /* 课程在生成时提交 */ }

// 生成
$('#btn-generate').onclick = async () => {
  const btn = $('#btn-generate');
  btn.disabled = true;
  btn.textContent = '⏳ 正在生成（解析模板 → 写内容 → 运行程序 → 插图）…';
  try {
    const profile = {};
    document.querySelectorAll('#profile-form input').forEach(i => profile[i.dataset.k] = i.value);
    const r = await post('/api/generate', {
      sid: SID,
      requirement: $('#requirement').value,
      course: $('#course-sel').value || null,
      run_programs: $('#run-programs').checked,
      profile,
    });
    if (!r.ok) throw new Error(r.error);
    toast('生成完成！' + (r.images ? `共插入 ${r.images} 张图片` : ''));
  } catch (e) {
    toast('生成失败：' + e.message, true);
  }
  btn.disabled = false;
  btn.textContent = '⚡ 一键生成报告';
  poll();
};

// 素材上传
$('#btn-asset').onclick = () => $('#file-asset').click();
$('#file-asset').onchange = async (e) => {
  const fd = new FormData();
  for (const f of e.target.files) fd.append('files', f);
  await fetch(`/api/assets?sid=${SID}`, { method: 'POST', body: fd });
  e.target.value = '';
  toast('已上传');
  poll();
};

async function insertImage(path) {
  const body = { sid: SID, ops: [{ op: 'insert_image', path, resolve: true }] };
  if (selectedPara !== null) {
    body.ops[0].after_index = parseInt(selectedPara);
    body.ops[0].section = undefined;
  }
  const r = await post('/api/ops', body);
  toast(r.reply || '已插入');
  poll();
}

// 预览缩放 & 刷新
$('#zoom').onchange = () => { $('#preview').style.zoom = $('#zoom').value; };
$('#btn-refresh').onclick = () => {
  previewRev = -1;
  $('#preview').src = `/api/preview?sid=${SID}&t=${Date.now()}`;
};

// 预览点击段落 → 聊天框引用
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'select-para') {
    selectedPara = e.data.idx;
    $('#sel-hint').textContent = `已选中段落 #${e.data.idx}（可在下方说“把第${e.data.idx}段改成…”或点击截图的“插入报告”插到此处）`;
    $('#chat-input').placeholder = `例如：把第${e.data.idx}段改成……`;
  }
});

// 聊天
$('#btn-send').onclick = sendChat;
$('#chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
async function sendChat() {
  const box = $('#chat-input');
  const msg = box.value.trim();
  if (!msg) return;
  box.value = '';
  if (msg === '把姓名改成') { $('#profile-form input[data-k=student_name]').focus(); return; }
  try {
    const r = await post('/api/chat', { sid: SID, message: msg });
    if (r.errors && r.errors.length) toast(r.errors[0], true);
  } catch (e) { toast(e.message, true); }
  poll();
}

// 快捷按钮
document.querySelectorAll('#quick-row .chip').forEach(b => {
  b.onclick = async () => {
    const q = b.dataset.q;
    if (q === '') {
      const goal = prompt('想让我做什么？（例如：打开 AutoCAD 画图并截图 / 把报告转成 PDF）');
      if (!goal) return;
      await post('/api/agent/plan', { sid: SID, goal });
      poll();
      return;
    }
    if (q === '把姓名改成') { $('#profile-form input[data-k=student_name]').focus(); return; }
    $('#chat-input').value = q;
    sendChat();
  };
});

// 清空聊天（仅界面）
$('#btn-clear-chat').onclick = () => { $('#chat-list').innerHTML = ''; };

// 新建报告（新会话）
$('#btn-new').onclick = async () => {
  if (!confirm('开启一份全新报告？\n\n当前会话的模板、个人信息、聊天记录都会保留在旧会话中，之后可以从浏览器历史找回；新报告将从空白开始。')) return;
  try {
    const r = await post('/api/new', {});
    localStorage.setItem('lab_sid', r.sid);
    location.reload();
  } catch (e) { toast('开启失败：' + e.message, true); }
};

// 下载 / 导出
$('#btn-download').onclick = () => {
  if (STATE && !STATE.generated) {
    toast('还没有生成报告，请先点左侧「⚡ 一键生成报告」', true);
    return;
  }
  window.open(`/api/download?sid=${SID}`, '_blank');
};
$('#btn-pdf').onclick = async () => {
  if (STATE && !STATE.generated) {
    toast('还没有生成报告，请先生成', true);
    return;
  }
  toast('正在导出 PDF…');
  try {
    const r = await post('/api/export', { sid: SID, format: 'pdf' });
    if (r.ok) window.open(r.url, '_blank');
    else toast(r.error, true);
  } catch (e) { toast(e.message, true); }
};

// AI 设置
$('#btn-settings').onclick = async () => {
  const st = STATE || await api(`/api/state?sid=${SID}`);
  $('#cfg-enabled').checked = st.llm.enabled;
  $('#modal').dataset.ready = st.llm.ready;
  $('#modal-mask').hidden = false;
};
$('#btn-modal-cancel').onclick = () => ($('#modal-mask').hidden = true);
$('#modal-mask').addEventListener('click', (e) => {
  if (e.target.id === 'modal-mask') $('#modal-mask').hidden = true;
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#modal-mask').hidden) $('#modal-mask').hidden = true;
});
$('#btn-modal-save').onclick = async () => {
  await post('/api/settings', {
    enabled: $('#cfg-enabled').checked,
    base_url: $('#cfg-url').value.trim() || undefined,
    api_key: $('#cfg-key').value.trim() || undefined,
    model: $('#cfg-model').value.trim() || undefined,
  });
  $('#modal-mask').hidden = true;
  toast('已保存 AI 设置');
  poll();
};
