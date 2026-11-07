/* 人工坐席：待认领队列、认领、办结 */

const handoffState = { items: [], approvals: [], loading: false };

async function renderHandoffPage() {
  const page = $('#handoff-page');
  if (!page) return;
  page.innerHTML = '<div class="page-inner"><div class="section-card"><p class="muted-text">加载待认领队列…</p></div></div>';
  try {
    const [data, approvals] = await Promise.all([
      api('/handoff/queue'),
      api('/approvals/queue'),
    ]);
    handoffState.items = data.items || [];
    handoffState.approvals = approvals.items || [];
    page.innerHTML = handoffPageHTML();
  } catch (error) {
    page.innerHTML = `<div class="page-inner"><div class="section-card">${emptyState('alert', '队列加载失败', escapeHtml(error.message))}</div></div>`;
  }
}

function handoffPageHTML() {
  const items = handoffState.items;
  return `
    <div class="page-inner">
      <div class="page-head">
        <div>
          <span class="eyebrow">HUMAN HANDOFF</span>
          <h1>人工坐席</h1>
          <p>只显示你有权限查看的转人工工单；认领后可以看到会话上下文并办结。</p>
        </div>
        <div class="head-actions"><span class="learning-count">${items.length} 待处理 · ${handoffState.approvals.length} 待审批</span></div>
      </div>
      <div class="section-card">
        <div class="section-head"><div><h3>待审批</h3><p class="section-sub">请假等需要工作人员批准的流程。</p></div><span class="learning-count">${handoffState.approvals.length} 项</span></div>
        <div class="handoff-grid">
          ${handoffState.approvals.length
            ? handoffState.approvals.map((item) => approvalCardHTML(item)).join('')
            : '<p class="muted-text">暂无待审批事项。</p>'}
        </div>
      </div>
      <div class="section-head"><div><h3>转人工待处理</h3><p class="section-sub">认领后可查看会话上下文并办结。</p></div></div>
      <div class="handoff-grid">
        ${items.length
          ? items.map((item) => handoffCardHTML(item)).join('')
          : `<div class="section-card">${emptyState('check', '暂无待认领工单', '所有转人工工单都已处理，或当前没有权限范围内的工单。')}</div>`}
      </div>
    </div>`;
}

function handoffCardHTML(item) {
  return `
    <article class="section-card handoff-card">
      <div class="section-head">
        <div>
          <h3>${escapeHtml(WORKFLOW_NAME[item.workflow_type] || item.workflow_type)}</h3>
          <p class="section-sub">${escapeHtml(item.session_title || '未命名会话')} · ${escapeHtml(item.student_id || '—')} · ${escapeHtml(item.campus || '—')}</p>
        </div>
        <span class="status-pill status-transferred_human">待处理</span>
      </div>
      <div class="handoff-context">
        <span>转人工原因</span>
        <p>${escapeHtml(item.reason || '—')}</p>
        <span>最近消息</span>
        <p>${escapeHtml(item.last_message || '—')}</p>
      </div>
      <div class="handoff-meta">
        <span>创建人：${escapeHtml(item.owner_id || '—')}</span>
        <span>学院：${escapeHtml(item.owner_college || '—')}</span>
        <span>${item.assignee_id ? `已认领：${escapeHtml(item.assignee_id)}` : '未认领'}</span>
      </div>
      <div class="handoff-actions">
        ${!item.assignee_id ? `<button type="button" class="primary-btn" data-handoff-action="claim" data-id="${escapeAttr(item.id)}">认领</button>` : ''}
        <button type="button" class="ghost-btn" data-handoff-action="resolve" data-id="${escapeAttr(item.id)}">办结</button>
        ${item.session_id ? `<button type="button" class="ghost-btn" data-handoff-action="open-session" data-session="${escapeAttr(item.session_id)}">查看会话</button>` : ''}
      </div>
    </article>`;
}

function approvalCardHTML(item) {
  return `
    <article class="section-card handoff-card">
      <div class="section-head">
        <div><h3>${escapeHtml(WORKFLOW_NAME[item.workflow_type] || item.workflow_type)}</h3>
        <p class="section-sub">${escapeHtml(item.student_id || '—')} · ${escapeHtml(item.campus || '—')} · ${escapeHtml(item.approval_role || '')}</p></div>
        <span class="status-pill status-awaiting_confirm">待审批</span>
      </div>
      <div class="handoff-context"><span>申请摘要</span><p>${escapeHtml(item.summary || '待审批')}</p></div>
      <div class="handoff-actions">
        <button type="button" class="primary-btn" data-handoff-action="approve" data-id="${escapeAttr(item.id)}">通过</button>
        <button type="button" class="ghost-btn profile-logout" data-handoff-action="reject" data-id="${escapeAttr(item.id)}">驳回</button>
      </div>
    </article>`;
}

async function decideApproval(id, approved) {
  const note = window.prompt(approved ? '审批意见（可选）' : '驳回原因', approved ? '同意' : '请补充材料');
  if (note === null) return;
  try {
    await api(`/approvals/${id}/${approved ? 'approve' : 'reject'}`, {
      method: 'POST',
      body: { note },
    });
    toast(approved ? '已通过审批。' : '已驳回。');
    await renderHandoffPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function claimHandoff(id) {
  try {
    await api(`/handoff/${id}/claim`, { method: 'POST' });
    toast('已认领，后续由你处理。');
    await renderHandoffPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function openResolveHandoff(id) {
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">HANDOFF</span><h2>办结工单</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <p class="learning-hint">写清处理结果，学生会在工单结果里看到这条记录。</p>
      <textarea id="handoff-note" class="learning-textarea" rows="5" placeholder="例如：已联系网络中心，安排明天上午上门；学生已确认。"></textarea>
      <div class="learning-form-row">
        <button type="button" class="primary-btn" data-handoff-action="submit-resolve" data-id="${escapeAttr(id)}">确认办结</button>
      </div>
    </div>`);
}

async function resolveHandoff(id, button) {
  const note = $('#handoff-note')?.value.trim() || '';
  if (!note) {
    toast('请填写处理结果。');
    return;
  }
  if (button) button.disabled = true;
  try {
    await api(`/handoff/${id}/resolve`, {
      method: 'POST',
      body: { note, result: 'completed' },
    });
    closeDrawer();
    toast('工单已办结。');
    await renderHandoffPage();
  } catch (error) {
    toast(error.message, 'error');
    if (button) button.disabled = false;
  }
}

async function handleHandoffClick(event) {
  const action = event.target.closest('[data-handoff-action]');
  if (!action) return;
  const kind = action.dataset.handoffAction;
  if (kind === 'approve') {
    await decideApproval(action.dataset.id, true);
  } else if (kind === 'reject') {
    await decideApproval(action.dataset.id, false);
  } else if (kind === 'claim') {
    await claimHandoff(action.dataset.id);
  } else if (kind === 'resolve') {
    openResolveHandoff(action.dataset.id);
  } else if (kind === 'submit-resolve') {
    await resolveHandoff(action.dataset.id, action);
  } else if (kind === 'open-session') {
    await selectSession(action.dataset.session);
    location.hash = '#/chat';
  }
}

document.addEventListener('click', handleHandoffClick);
