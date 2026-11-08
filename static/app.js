/* ============================================================
   知行 · 校园智能服务助手
   单页工作台：对话 / 工单 / 审计 / 知识库 / 学生库 / 评测 / 系统
   ============================================================ */
'use strict';

const API = '/api/v1';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const ROUTES = {
  campus: '校园事务',
  chat: '对话工作台',
  learning: '个人学习',
  workorders: '工单中心',
  handoff: '人工坐席',
  audit: '审计回放',
  knowledge: '知识库',
  lostfound: '失物招领',
  feedback: '意见反馈',
  students: '学生库',
  evaluation: '评测中心',
  system: '系统状态',
};

const ROUTE_TITLES = {
  campus: '校园事务总览',
  learning: '学习概览',
  workorders: '工单列表',
  handoff: '待认领队列',
  audit: '留痕回放',
  knowledge: '制度文档',
  lostfound: '失物招领',
  feedback: '意见反馈',
  students: '学生名册',
  evaluation: '检索评测',
  system: '运行总览',
};

const CAMPUS_NAV = [
  { section: 'home', route: 'campus', icon: 'home', label: '校园事务总览' },
  { section: 'chat', route: 'chat', icon: 'chat', label: '对话工作台' },
  { section: 'card-reissue', route: 'chat', icon: 'ticket', label: '校园卡补办' },
  { section: 'network-repair', route: 'chat', icon: 'pulse', label: '网络报修' },
  { section: 'leave', route: 'chat', icon: 'clock', label: '请假申请' },
  { section: 'workorders', route: 'workorders', icon: 'ticket', label: '工单中心' },
  { section: 'approvals', route: 'workorders', icon: 'shield', label: '审批中心', staffOnly: true },
  { section: 'handoff', route: 'handoff', icon: 'users', label: '人工坐席', staffOnly: true },
  { section: 'lost-found', route: 'lostfound', icon: 'search', label: '失物招领' },
  { section: 'feedback', route: 'feedback', icon: 'chat', label: '意见反馈' },
  { section: 'knowledge', route: 'knowledge', icon: 'book', label: '知识库' },
  { section: 'evaluation', route: 'evaluation', icon: 'chart', label: '评测中心' },
  { section: 'notifications', action: 'notifications', icon: 'bell', label: '通知中心' },
  { section: 'audit', route: 'audit', icon: 'pulse', label: '审计回放', staffOnly: true },
  { section: 'students', route: 'students', icon: 'users', label: '学生库', staffOnly: true },
  { section: 'system', route: 'system', icon: 'cpu', label: '系统状态', staffOnly: true },
];

const LEARNING_NAV = [
  { tab: 'focus', label: '学习概览 / 专注' },
  { tab: 'exam', label: '考试周' },
  { tab: 'tasks', label: '任务清单' },
  { tab: 'review', label: '复习' },
  { tab: 'mistakes', label: '错题本' },
  { tab: 'calendar', label: '日历与课程' },
  { tab: 'materials', label: '课程资料' },
  { tab: 'report', label: '学习报告' },
  { tab: 'models', label: '模型设置' },
];

const CAMPUS_PROMPTS = {
  'card-reissue': '我要补办校园卡',
  'network-repair': '我要报修网络',
  leave: '我要请假',
};

const STATUS_MAP = {
  draft: { label: '草稿', cls: 'draft' },
  awaiting_input: { label: '待补充', cls: 'awaiting_input' },
  awaiting_confirm: { label: '待确认', cls: 'awaiting_confirm' },
  awaiting_approval: { label: '待审批', cls: 'awaiting_confirm' },
  in_progress: { label: '办理中', cls: 'in_progress' },
  completed: { label: '已完成', cls: 'completed' },
  failed: { label: '未通过', cls: 'failed' },
  cancelled: { label: '已取消', cls: 'cancelled' },
  transferred_human: { label: '已转人工', cls: 'transferred_human' },
};

const EVENT_MAP = {
  message: '消息',
  intent: '意图识别',
  retrieval: '检索',
  tool_call: '工具调用',
  node_transition: '节点流转',
  confirmation: '人工确认',
  idempotency: '幂等',
  handoff: '转人工',
  auth: '登录',
  error: '异常',
  evaluation: '评测',
};

const WORKFLOW_NAME = {
  card_reissue: '校园卡补办',
  network_repair: '网络报修',
  leave_request: '请假申请',
};

const state = {
  route: 'chat',
  mode: localStorage.getItem('zhixing-mode') || 'campus',
  lastCampusSection: localStorage.getItem('zhixing-campus-section') || 'home',
  lastLearningTab: localStorage.getItem('zhixing-learning-tab') || 'focus',
  campusSection: localStorage.getItem('zhixing-campus-section') || 'home',
  learningTab: localStorage.getItem('zhixing-learning-tab') || 'focus',
  user: null,
  token: localStorage.getItem('zhixing-token') || '',
  loginMode: 'student',
  started: false,
  sessionId: null,
  session: null,
  sessions: [],
  messages: [],
  notifications: [],
  notificationUnread: 0,
  sending: false,
  trace: [],
  workorder: null,
  workorders: [],
  workorderFilter: 'all',
  workorderCounts: {},
  knowledgeDocs: [],
  knowledgeCategories: [],
  knowledgeCategory: '全部',
  knowledgeSearch: '',
  knowledgeResults: null,
  lostFoundCampus: '',
  lostFoundKind: 'lost',
  lostFoundQuery: '',
  lostFoundData: null,
  feedbackData: null,
  students: [],
  studentStats: null,
  studentFilters: { college: '', cohort: '', major: '', query: '', status: '' },
  studentOffset: 0,
  studentLimit: 50,
  studentTotal: 0,
  studentLoading: false,
  evaluation: null,
  extendedEval: { retrieval: null, generation: null, task: null },
  extendedLoading: {},
  overview: null,
  health: null,
  auditEvents: [],
  auditFilter: 'all',
  auditSessionId: '',
  theme: localStorage.getItem('zhixing-theme') || 'light',
  lastFailedText: '',
};

/* ============================================================
   基础工具
   ============================================================ */

function icon(name, cls = '') {
  return `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function truncate(text, length = 80) {
  const value = String(text ?? '').replace(/\s+/g, ' ').trim();
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

function formatTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function relativeTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diff = Date.now() - date.getTime();
  if (diff < 60 * 1000) return '刚刚';
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)} 分钟前`;
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `昨天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function formatUptime(seconds) {
  const value = Math.floor(Number(seconds) || 0);
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  if (days > 0) return `${days}天 ${hours}小时`;
  if (hours > 0) return `${hours}小时 ${minutes}分`;
  return `${minutes}分 ${value % 60}秒`;
}

function percent(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

async function api(path, options = {}) {
  const config = { headers: { 'Content-Type': 'application/json' }, ...options };
  if (state.token) {
    config.headers.Authorization = `Bearer ${state.token}`;
  }
  if (config.body && typeof config.body !== 'string') {
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(`${API}${path}`, config);
  if (response.status === 401 && !path.startsWith('/auth/login')) {
    handleUnauthorized();
  }
  if (!response.ok) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }
    const detail = payload.detail;
    let message = payload.message || (detail && detail.message) || `请求失败（${response.status}）`;
    if (Array.isArray(detail)) {
      message = detail.map((item) => item.msg).filter(Boolean).join('；') || message;
    }
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message, type = 'success') {
  const stack = $('#toast-stack');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(type === 'error' ? 'alert' : 'check')}<span>${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  setTimeout(() => {
    el.classList.add('toast-leaving');
    setTimeout(() => el.remove(), 220);
  }, 3200);
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  localStorage.setItem('zhixing-theme', state.theme);
}

/* ============================================================
   启动与路由
   ============================================================ */

document.addEventListener('DOMContentLoaded', init);

const ROLE_LABELS = {
  student: '学生',
  counselor: '辅导员',
  auditor: '审计员',
  admin: '管理员',
};

const ROLE_ROUTES = {
  student: ['campus', 'chat', 'learning', 'workorders', 'knowledge', 'evaluation', 'lostfound', 'feedback'],
  counselor: ['campus', 'chat', 'workorders', 'handoff', 'audit', 'knowledge', 'students', 'evaluation', 'lostfound', 'feedback'],
  auditor: ['campus', 'workorders', 'handoff', 'audit', 'knowledge', 'students', 'evaluation', 'lostfound', 'feedback'],
  admin: ['campus', 'chat', 'learning', 'workorders', 'handoff', 'audit', 'knowledge', 'students', 'evaluation', 'system', 'lostfound', 'feedback'],
};

function allowedRoutes() {
  return ROLE_ROUTES[state.user?.role] || ROLE_ROUTES.student;
}

function defaultRoute() {
  return allowedRoutes().includes('campus') ? 'campus' : 'workorders';
}

function canSeeCampusItem(item) {
  if (item.staffOnly && !['counselor', 'auditor', 'admin'].includes(state.user?.role)) {
    return false;
  }
  if (item.route && !allowedRoutes().includes(item.route)) return false;
  return true;
}

function renderSidebarNav() {
  const nav = $('#main-nav');
  if (!nav) return;
  const switchButton = $('#mode-toggle');
  if (switchButton) {
    switchButton.setAttribute('aria-pressed', state.mode === 'learning' ? 'true' : 'false');
    $('#mode-label').textContent = state.mode === 'learning' ? '个人学习' : '校园事务';
    $('#mode-switch').classList.toggle('is-learning', state.mode === 'learning');
  }

  if (state.mode === 'learning') {
    if (!allowedRoutes().includes('learning')) {
      nav.innerHTML = '';
      return;
    }
    nav.innerHTML = `
      <div class="nav-section-label">个人学习</div>
      <a href="#/campus/chat" class="nav-item ${state.route === 'chat' ? 'is-active' : ''}" data-nav-chat="1" data-route="chat">
        <svg class="icon"><use href="#i-chat"></use></svg><span>对话工作台</span>
      </a>
      ${LEARNING_NAV.map((item) => `
        <a href="#/learning/${escapeAttr(item.tab)}" class="nav-item ${state.learningTab === item.tab && state.route !== 'chat' ? 'is-active' : ''}"
           data-nav-learning="${escapeAttr(item.tab)}" data-route="learning">
          <svg class="icon"><use href="#i-${item.tab === 'mistakes' ? 'book' : item.tab === 'calendar' ? 'clock' : item.tab === 'models' ? 'settings' : 'spark'}"></use></svg>
          <span>${escapeHtml(item.label)}</span>
        </a>`).join('')}`;
    return;
  }

  const renderItem = (item) => {
    if (item.action === 'notifications') {
      return `<button type="button" class="nav-item" data-campus-action="notifications">
        <svg class="icon"><use href="#i-${item.icon}"></use></svg><span>${escapeHtml(item.label)}</span>
      </button>`;
    }
    const active = state.campusSection === item.section;
    return `<a href="#/campus/${escapeAttr(item.section)}" class="nav-item ${active ? 'is-active' : ''}"
      data-campus-section="${escapeAttr(item.section)}" data-route="${escapeAttr(item.route)}">
      <svg class="icon"><use href="#i-${item.icon}"></use></svg><span>${escapeHtml(item.label)}</span>
    </a>`;
  };
  nav.innerHTML = `
    <div class="nav-section-label">校园事务</div>
    ${CAMPUS_NAV.filter(canSeeCampusItem).map(renderItem).join('')}`;
}

function setActiveNavigation() {
  $$('#main-nav .nav-item').forEach((item) => {
    const active = state.mode === 'learning'
      ? (item.dataset.navChat ? state.route === 'chat' : item.dataset.navLearning === state.learningTab && state.route !== 'chat')
      : item.dataset.campusSection === state.campusSection;
    item.classList.toggle('is-active', active);
    if (active) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
}

function setHash(hash) {
  if (location.hash === hash) {
    applyLocation();
    return;
  }
  location.hash = hash;
}

async function startCampusService(section) {
  const prompt = CAMPUS_PROMPTS[section];
  if (!prompt || state.sending) return;
  state.mode = 'campus';
  state.campusSection = section;
  state.lastCampusSection = section;
  localStorage.setItem('zhixing-mode', 'campus');
  localStorage.setItem('zhixing-campus-section', section);
  renderSidebarNav();
  setActiveNavigation();

  // 服务入口不预先塞一句“我要补办…”，而是像在对话里输入后发送一样，
  // 直接启动对应工作流。当前没有进行中的工单时沿用当前会话；有旧工单时
  // 开一个干净会话，避免把新业务塞进旧工作流。
  if (!state.sessionId || state.workorder) {
    const session = await createSession({ silent: true });
    if (!session) return;
  } else {
    await navigate('chat', { push: false });
  }
  history.pushState(null, '', `#/campus/${section}`);
  await sendMessage(prompt);
}

function navigateCampusSection(section) {
  if (CAMPUS_PROMPTS[section]) {
    startCampusService(section).catch((error) => toast(error.message || '启动办理失败', 'error'));
    return;
  }
  state.mode = 'campus';
  state.campusSection = section;
  state.lastCampusSection = section;
  localStorage.setItem('zhixing-mode', 'campus');
  localStorage.setItem('zhixing-campus-section', section);
  renderSidebarNav();
  setHash(`#/campus/${section}`);
}

function applyLearningTab(tab) {
  if (typeof learningState === 'undefined') return;
  learningState.tab =
    tab === 'models' || tab === 'home' ? 'focus' : tab === 'materials' ? 'calendar' : tab;
}

async function navigateLearningSection(tab) {
  state.mode = 'learning';
  state.learningTab = tab;
  state.lastLearningTab = tab;
  localStorage.setItem('zhixing-mode', 'learning');
  localStorage.setItem('zhixing-learning-tab', tab);
  applyLearningTab(tab);
  await navigate('learning', { push: false });
  state.learningTab = tab;
  renderSidebarNav();
  updateChrome('learning');
  setActiveNavigation();
  if (tab === 'models') openVisionSettings();
  setHash(`#/learning/${tab}`);
}

function toggleAppMode() {
  if (state.mode === 'campus') {
    if (!allowedRoutes().includes('learning')) {
      toast('当前角色没有个人学习板块权限。');
      return;
    }
    navigateLearningSection(state.lastLearningTab || 'focus');
  } else {
    const target = CAMPUS_PROMPTS[state.lastCampusSection]
      ? 'home'
      : state.lastCampusSection || 'home';
    navigateCampusSection(target);
  }
}

function parseLocation() {
  const raw = (location.hash || '').replace(/^#\/?/, '').trim();
  if (raw.startsWith('campus/')) {
    const section = raw.slice('campus/'.length) || 'home';
    return { mode: 'campus', section };
  }
  if (raw === 'campus') return { mode: 'campus', section: 'home' };
  if (raw === 'learning/chat') {
    return { mode: 'learning', tab: state.lastLearningTab || 'focus', chat: true };
  }
  if (raw.startsWith('learning/')) {
    const tab = raw.slice('learning/'.length) || 'focus';
    return { mode: 'learning', tab };
  }
  if (raw === 'learning') return { mode: 'learning', tab: state.lastLearningTab || 'focus' };
  if (ROUTES[raw]) {
    return { mode: raw === 'learning' ? 'learning' : 'campus', section: raw, route: raw };
  }
  return { mode: 'campus', section: 'home', route: 'campus' };
}

async function applyLocation() {
  const target = parseLocation();
  if (target.mode === 'learning' && target.chat) {
    state.mode = 'learning';
    await navigate('chat', { push: false });
    renderSidebarNav();
    setActiveNavigation();
    return;
  }
  if (target.mode === 'learning') {
    state.mode = 'learning';
    const validLearningTabs = new Set(LEARNING_NAV.map((item) => item.tab));
    state.learningTab = validLearningTabs.has(target.tab) ? target.tab : 'focus';
    const requestedTab = state.learningTab;
    state.lastLearningTab = requestedTab;
    localStorage.setItem('zhixing-learning-tab', requestedTab);
    applyLearningTab(requestedTab);
    await navigate('learning', { push: false });
    state.learningTab = requestedTab;
    renderSidebarNav();
    updateChrome('learning');
    setActiveNavigation();
    if (state.learningTab === 'models') openVisionSettings();
    return;
  }

  state.mode = 'campus';
  state.campusSection = target.section || 'home';
  state.lastCampusSection = state.campusSection;
  localStorage.setItem('zhixing-campus-section', state.campusSection);
  if (CAMPUS_PROMPTS[state.campusSection]) {
    await navigate('chat', { push: false });
    const prompt = CAMPUS_PROMPTS[state.campusSection];
    const input = $('#composer-input');
    if (input) {
      input.value = prompt;
      input.focus();
      autoResizeComposer();
    }
    toast(`已打开对话工作台：${prompt}`);
  } else if (state.campusSection === 'approvals') {
    state.workorderFilter = 'awaiting_approval';
    await navigate('workorders', { push: false });
    state.campusSection = 'approvals';
    renderSidebarNav();
    setActiveNavigation();
  } else if (state.campusSection === 'notifications') {
    await navigate('campus', { push: false });
    state.campusSection = 'notifications';
    renderSidebarNav();
    setActiveNavigation();
    $('#notifications-btn')?.click();
  } else {
    const sectionRoutes = {
      home: 'campus',
      'lost-found': 'lostfound',
      feedback: 'feedback',
    };
    const route = sectionRoutes[state.campusSection] || state.campusSection;
    await navigate(ROUTES[route] ? route : 'campus', { push: false });
  }
  renderSidebarNav();
  setActiveNavigation();
}

function renderCampusHomePage() {
  const page = $('#campus-page');
  if (!page) return;
  const user = state.user || {};
  const chatAllowed = allowedRoutes().includes('chat');
  const cards = [
    ['card-reissue', 'ticket', '校园卡补办', '挂失、余额校验、预约与回执', 'tone-teal'],
    ['network-repair', 'pulse', '网络报修', '断网、网线、端口报修与派单', 'tone-amber'],
    ['leave', 'clock', '请假申请', '辅导员审批，超过 3 天学院审批', 'tone-indigo'],
    ['lost-found', 'search', '失物招领', '按校区发布寻物/招领，关键词快速匹配', 'tone-indigo'],
    ['feedback', 'chat', '意见反馈', '教学、后勤、设施建议，可匿名提交', 'tone-amber'],
    ['workorders', 'ticket', '工单中心', '查看办理状态、回执与审批', 'tone-slate'],
    ['knowledge', 'book', '知识库', '制度原文、条款引用与检索', 'tone-indigo'],
    ['evaluation', 'chart', '评测中心', '检索、引用、拒答与任务指标', 'tone-teal'],
  ].filter(([section]) => chatAllowed || !['card-reissue', 'network-repair', 'leave'].includes(section));
  page.innerHTML = `
    <div class="page-inner campus-home">
      <div class="page-head campus-home-head">
        <div>
          <span class="eyebrow">CAMPUS SERVICES</span>
          <h1>校园事务</h1>
          <p>${escapeHtml(user.name || '同学')}，从补卡、报修、请假到工单和制度查询，都可以在这里直接进入。</p>
        </div>
        ${chatAllowed ? `<button type="button" class="primary-btn" data-campus-section="chat">${icon('chat')} 打开对话工作台</button>` : ''}
      </div>
      <div class="campus-service-grid">
        ${cards.map(([section, iconName, title, desc, tone]) => `
          <button type="button" class="campus-service-card" data-campus-section="${section}">
            <span class="cap-icon ${tone}">${icon(iconName)}</span>
            <strong>${title}</strong>
            <span>${desc}</span>
            <em>进入 ${icon('arrow')}</em>
          </button>`).join('')}
      </div>
      <div class="campus-home-note">
        ${icon('shield')} 所有办理都会保留确认、回执和审计记录；没有依据的问题不会编造答案。
      </div>
    </div>`;
}


const LOST_FOUND_CAMPUSES = ['天赐庄校区', '独墅湖校区', '阳澄湖校区', '未来校区'];

function lostFoundCardHTML(item) {
  const kindLabel = item.kind === 'found' ? '招领' : '寻物';
  return `
    <article class="lostfound-card is-${escapeAttr(item.kind)}">
      ${item.image_url ? `<img src="${item.image_url}" alt="${kindLabel}物品图" />` : `<div class="lostfound-placeholder">${icon(item.kind === 'found' ? 'search' : 'book')}</div>`}
      <div class="lostfound-card-main">
        <div class="lostfound-meta">
          <span class="lostfound-kind">${kindLabel}</span>
          <span>${escapeHtml(item.campus)}</span>
          <span>${escapeHtml(item.category || '其他')}</span>
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.description || '没有补充描述')}</p>
        <div class="lostfound-tags">
          ${item.keywords ? `<span>${escapeHtml(item.keywords)}</span>` : ''}
          ${item.place ? `<span>${escapeHtml(item.place)}</span>` : ''}
          ${item.contact ? `<span>联系：${escapeHtml(item.contact)}</span>` : ''}
        </div>
        ${item.is_mine ? `<button type="button" class="text-btn" data-lostfound-close="${escapeAttr(item.id)}">标记已解决</button>` : ''}
      </div>
    </article>`;
}

async function renderLostFoundPage() {
  const page = $('#lostfound-page');
  if (!page) return;
  page.innerHTML = '<div class="page-inner"><p class="muted-text">正在加载失物招领…</p></div>';
  try {
    const params = new URLSearchParams();
    if (state.lostFoundCampus) params.set('campus', state.lostFoundCampus);
    if (state.lostFoundKind) params.set('kind', state.lostFoundKind);
    if (state.lostFoundQuery) params.set('q', state.lostFoundQuery);
    const data = await api(`/community/lost-found?${params.toString()}`);
    state.lostFoundData = data;
    const campuses = data.campuses || LOST_FOUND_CAMPUSES;
    const items = data.items || [];
    const matches = data.matches || [];
    page.innerHTML = `
      <div class="page-inner lostfound-page">
        <div class="page-head">
          <div>
            <span class="eyebrow">LOST &amp; FOUND</span>
            <h1>失物招领</h1>
            <p>选择校区，发布寻物或招领；系统会用标题、描述和关键词自动匹配。</p>
          </div>
          <div class="section-head-actions">
            <button type="button" class="ghost-btn" data-lostfound-open="lost">${icon('search')} 我丢了东西</button>
            <button type="button" class="primary-btn" data-lostfound-open="found">${icon('plus')} 我捡到了东西</button>
          </div>
        </div>
        <div class="lostfound-toolbar">
          <div class="lostfound-tabs">
            <button type="button" class="lostfound-tab ${state.lostFoundKind === 'lost' ? 'is-active' : ''}" data-lostfound-kind="lost">寻物</button>
            <button type="button" class="lostfound-tab ${state.lostFoundKind === 'found' ? 'is-active' : ''}" data-lostfound-kind="found">招领</button>
          </div>
          <select id="lostfound-campus" class="select-input">
            <option value="">全部校区</option>
            ${campuses.map((campus) => `<option value="${escapeAttr(campus)}" ${state.lostFoundCampus === campus ? 'selected' : ''}>${escapeHtml(campus)}</option>`).join('')}
          </select>
          <input id="lostfound-search" class="text-input" value="${escapeAttr(state.lostFoundQuery)}" placeholder="搜耳机、校园卡、水杯…" />
          <button type="button" class="ghost-btn" data-lostfound-search>${icon('search')} 搜索匹配</button>
        </div>
        ${matches.length ? `
          <section class="lostfound-matches">
            <div class="section-head"><div><h3>可能匹配</h3><p class="section-sub">同校区、相反类型，按关键词和描述自动排序。</p></div></div>
            ${matches.map((match) => `
              <div class="lostfound-match">
                <span class="lostfound-match-score">${match.score} 分</span>
                <div><b>寻物</b>${escapeHtml(match.lost.title)} <small>${escapeHtml(match.lost.campus)}</small></div>
                <div><b>招领</b>${escapeHtml(match.found.title)} <small>${escapeHtml(match.found.campus)}</small></div>
                <p>${escapeHtml((match.reasons || []).join('、') || '关键词相近')}</p>
              </div>`).join('')}
          </section>` : ''}
        <div class="lostfound-grid">
          ${items.length ? items.map(lostFoundCardHTML).join('') : '<div class="learning-empty"><strong>这个筛选下还没有记录</strong><span>发布一条寻物或招领，系统会帮你匹配。</span></div>'}
        </div>
      </div>`;
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'lostfound');
  }
}

function openLostFoundForm(kind) {
  const campuses = state.lostFoundData?.campuses || LOST_FOUND_CAMPUSES;
  const isFound = kind === 'found';
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">${isFound ? 'FOUND ITEM' : 'LOST ITEM'}</span><h2>${isFound ? '发布招领' : '发布寻物'}</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body lostfound-form">
      <label class="login-field"><span>校区</span><select id="lostfound-form-campus" class="select-input">${campuses.map((campus) => `<option value="${escapeAttr(campus)}" ${state.lostFoundCampus === campus ? 'selected' : ''}>${escapeHtml(campus)}</option>`).join('')}</select></label>
      <label class="login-field"><span>物品标题</span><input id="lostfound-form-title" class="text-input" maxlength="80" placeholder="${isFound ? '例如：白色耳机充电盒' : '例如：寻找黑色水杯'}" /></label>
      <label class="login-field"><span>关键词（空格或逗号分隔）</span><input id="lostfound-form-keywords" class="text-input" maxlength="120" placeholder="耳机 白色 充电盒" /></label>
      <label class="login-field"><span>类别</span><input id="lostfound-form-category" class="text-input" maxlength="30" placeholder="电子产品 / 证件 / 生活用品" /></label>
      <label class="login-field"><span>地点</span><input id="lostfound-form-place" class="text-input" maxlength="80" placeholder="例如：图书馆三楼" /></label>
      <label class="login-field"><span>补充描述</span><textarea id="lostfound-form-description" class="learning-textarea" rows="3" placeholder="颜色、时间、外观特征"></textarea></label>
      <label class="login-field"><span>联系方式（可选）</span><input id="lostfound-form-contact" class="text-input" maxlength="80" placeholder="微信 / 手机号 / 仅站内联系" /></label>
      <label class="file-drop"><input type="file" id="lostfound-form-image" accept="image/png,image/jpeg,image/webp" /><span>${icon('upload')} 添加物品照片（可选）</span><small>不超过 2MB。</small></label>
      <div class="learning-form-row"><button type="button" class="primary-btn" data-lostfound-submit="${escapeAttr(kind)}">${isFound ? '发布招领' : '发布寻物'}</button></div>
    </div>`);
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('图片读取失败'));
    reader.readAsDataURL(file);
  });
}

async function submitLostFound(kind) {
  const campus = $('#lostfound-form-campus')?.value || '';
  const title = $('#lostfound-form-title')?.value.trim() || '';
  if (!campus || !title) {
    toast('请选择校区并填写物品标题。');
    return;
  }
  const file = $('#lostfound-form-image')?.files?.[0];
  if (file && file.size > 2 * 1024 * 1024) {
    toast('图片不能超过 2MB。');
    return;
  }
  try {
    const imageData = file ? await readFileAsDataURL(file) : '';
    await api('/community/lost-found', {
      method: 'POST',
      body: {
        kind,
        campus,
        title,
        description: $('#lostfound-form-description')?.value.trim() || '',
        category: $('#lostfound-form-category')?.value.trim() || '',
        keywords: $('#lostfound-form-keywords')?.value.trim() || '',
        place: $('#lostfound-form-place')?.value.trim() || '',
        contact: $('#lostfound-form-contact')?.value.trim() || '',
        image_data: imageData,
      },
    });
    state.lostFoundCampus = campus;
    state.lostFoundKind = kind;
    state.lostFoundQuery = title;
    closeDrawer();
    await renderLostFoundPage();
    toast('已发布，正在显示可能匹配。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function closeLostFound(itemId) {
  if (!window.confirm('标记这条记录为已解决？')) return;
  try {
    await api(`/community/lost-found/${itemId}/close`, { method: 'POST' });
    await renderLostFoundPage();
    toast('已标记为解决。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function renderFeedbackPage() {
  const page = $('#feedback-page');
  if (!page) return;
  page.innerHTML = '<div class="page-inner"><p class="muted-text">正在加载意见反馈…</p></div>';
  try {
    const data = await api('/community/feedback');
    state.feedbackData = data;
    const items = data.items || [];
    page.innerHTML = `
      <div class="page-inner feedback-page">
        <div class="page-head">
          <div><span class="eyebrow">FEEDBACK</span><h1>意见反馈</h1><p>${data.staff_view ? '辅导员 / 管理人员视图：可看到非匿名反馈的提交人。' : '对教学、后勤、设施或学生服务提出建议；可以匿名。'}</p></div>
        </div>
        <div class="feedback-layout">
          <section class="section-card feedback-form-card">
            <div class="section-head"><div><h3>提交意见</h3><p class="section-sub">学校会按类别汇总；匿名反馈不展示姓名。</p></div></div>
            <label class="login-field"><span>类别</span><select id="feedback-category" class="select-input">${['教学', '后勤', '校园设施', '学生服务', '其他'].map((value) => `<option>${value}</option>`).join('')}</select></label>
            <label class="login-field"><span>内容</span><textarea id="feedback-content" class="learning-textarea" rows="5" maxlength="2000" placeholder="描述你遇到的问题或建议"></textarea></label>
            <label class="feedback-anonymous"><input type="checkbox" id="feedback-anonymous" /> 匿名提交（辅导员端不显示姓名）</label>
            <button type="button" class="primary-btn" data-feedback-submit>${icon('send')} 提交反馈</button>
          </section>
          <section class="section-card">
            <div class="section-head"><div><h3>${data.staff_view ? '学生反馈' : '我的反馈'}</h3><span class="learning-count">${items.length} 条</span></div></div>
            <div class="feedback-list">
              ${items.length ? items.map((item) => `
                <article class="feedback-item">
                  <div class="feedback-meta"><span>${escapeHtml(item.category)}</span><small>${escapeHtml((item.created_at || '').slice(0, 16).replace('T', ' '))}</small>${item.anonymous ? '<em>匿名</em>' : ''}</div>
                  <p>${escapeHtml(item.content)}</p>
                  ${data.staff_view ? `<small>${escapeHtml(item.anonymous ? '匿名学生' : `${item.owner_name} · ${item.owner_college || ''}`)}</small>` : ''}
                </article>`).join('') : '<p class="muted-text">还没有反馈。</p>'}
            </div>
          </section>
        </div>
      </div>`;
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'feedback');
  }
}

async function submitFeedback() {
  const content = $('#feedback-content')?.value.trim() || '';
  if (content.length < 2) {
    toast('请填写反馈内容。');
    return;
  }
  try {
    await api('/community/feedback', {
      method: 'POST',
      body: {
        category: $('#feedback-category')?.value || '其他',
        content,
        anonymous: Boolean($('#feedback-anonymous')?.checked),
      },
    });
    $('#feedback-content').value = '';
    await renderFeedbackPage();
    toast('反馈已提交。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function loadNotifications() {
  try {
    const data = await api('/notifications');
    state.notifications = data.items || [];
    state.notificationUnread = data.unread || 0;
    renderNotifications();
  } catch (error) {
    state.notifications = [];
    state.notificationUnread = 0;
    renderNotifications();
  }
}

function renderNotifications() {
  const badge = $('#notification-badge');
  if (badge) {
    badge.hidden = state.notificationUnread <= 0;
    badge.textContent = state.notificationUnread > 9 ? '9+' : String(state.notificationUnread);
  }
  const list = $('#notifications-list');
  if (!list) return;
  if (!state.notifications.length) {
    list.innerHTML = '<p class="muted-text">暂无通知</p>';
    return;
  }
  list.innerHTML = state.notifications
    .map(
      (item) => `
      <button type="button" class="notification-item ${item.read ? '' : 'is-unread'}" data-notification-link="${escapeAttr(item.link || '')}" data-notification-id="${escapeAttr(item.id)}">
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.message)}</span>
        <small>${escapeHtml((item.created_at || '').slice(0, 16).replace('T', ' '))}</small>
      </button>`
    )
    .join('');
}

function toggleNotificationMenu() {
  const menu = $('#notifications-menu');
  if (!menu) return;
  menu.hidden = !menu.hidden;
}

async function markAllNotificationsRead() {
  try {
    await api('/notifications/read', { method: 'POST' });
    await loadNotifications();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function openNotification(item) {
  try {
    await api('/notifications/read?notification_id=' + encodeURIComponent(item.dataset.notificationId), { method: 'POST' });
  } catch (error) {
    // 标记已读失败不阻塞跳转
  }
  const link = item.dataset.notificationLink;
  if (link && link.startsWith('#/')) {
    location.hash = link.slice(1);
  }
  $('#notifications-menu').hidden = true;
  await loadNotifications();
}

async function init() {
  const themeParam = new URLSearchParams(location.search).get('theme');
  if (themeParam === 'dark' || themeParam === 'light') {
    state.theme = themeParam;
  }
  applyTheme();
  bindEvents();

  const user = await restoreAuth();
  if (!user) {
    showLogin();
    return;
  }
  await startApp();
}

async function restoreAuth() {
  if (!state.token) return null;
  try {
    const user = await api('/auth/me');
    state.user = user;
    return user;
  } catch (error) {
    state.token = '';
    localStorage.removeItem('zhixing-token');
    return null;
  }
}

async function startApp() {
  if (state.started) return;
  state.started = true;
  const initialHash = location.hash;
  hideLogin();
  document.body.classList.add('dual-shell');
  applyRoleUI();
  updateChrome('chat');

  try {
    const [health, sessions] = await Promise.all([api('/health'), api('/sessions')]);
    state.health = health;
    state.sessions = sessions.items || [];
    $('#model-name').textContent = health.llm_model || 'DeepSeek-V3 · Mock';
    $('#footer-version').textContent = `v${health.version} · ${health.knowledge_documents} 篇制度`;
    renderSessionList();
    refreshBadge();
    await loadNotifications();
    setInterval(loadNotifications, 60000);

    if (state.user?.role === 'auditor') {
      state.session = null;
    } else {
      const deepSession = new URLSearchParams(location.search).get('session');
      const deepMatch = state.sessions.find((item) => item.id === deepSession);
      if (deepMatch) {
        await selectSession(deepMatch.id, { silent: true });
      } else if (state.sessions.length > 0) {
        await selectSession(state.sessions[0].id, { silent: true });
      } else {
        await createSession({ silent: true });
      }
    }
  } catch (error) {
    toast(error.message, 'error');
    renderWelcome();
  }

  if (initialHash) {
    history.replaceState(null, '', initialHash);
    await applyLocation();
  } else if (state.mode === 'learning' && allowedRoutes().includes('learning')) {
    state.mode = 'learning';
    const requestedTab = state.learningTab || 'focus';
    applyLearningTab(requestedTab);
    await navigate('learning', { push: false });
    state.learningTab = requestedTab;
    history.replaceState(null, '', `#/learning/${requestedTab}`);
  } else {
    state.mode = 'campus';
    state.campusSection = 'home';
    await navigate('campus', { push: false });
    history.replaceState(null, '', '#/campus/home');
  }
}

function applyRoleUI() {
  const allowed = allowedRoutes();
  renderSidebarNav();
  const chatAllowed = allowed.includes('chat');
  const newChat = $('#new-chat-btn');
  if (newChat) newChat.hidden = !chatAllowed;
  const sessionBlock = $('.session-block');
  if (sessionBlock) sessionBlock.hidden = !chatAllowed;
  const name = state.user?.name || '未登录';
  const role = ROLE_LABELS[state.user?.role] || '—';
  const roleDetail =
    state.user?.role === 'student' && state.user?.class_name
      ? `${role} · ${state.user.class_name}`
      : role;
  $('#user-name').textContent = name;
  $('#user-role').textContent = roleDetail;
  $('#user-avatar').textContent = name.slice(0, 1);
  document.body.classList.toggle('role-auditor', state.user?.role === 'auditor');
}

function showLogin(message = '') {
  document.body.classList.add('login-locked');
  const screen = $('#login-screen');
  if (screen) screen.hidden = false;
  const error = $('#login-error');
  if (error) {
    error.textContent = message;
    error.hidden = !message;
  }
  setTimeout(() => {
    const target =
      state.loginMode === 'student' ? $('#login-student-id') : $('#login-username');
    target?.focus();
  }, 80);
}

function setLoginMode(mode) {
  state.loginMode = mode === 'staff' ? 'staff' : 'student';
  $$('[data-login-mode]').forEach((button) => {
    button.classList.toggle('is-active', button.dataset.loginMode === state.loginMode);
  });
  const studentFields = $('#student-fields');
  const staffFields = $('#staff-fields');
  if (studentFields) studentFields.hidden = state.loginMode !== 'student';
  if (staffFields) staffFields.hidden = state.loginMode !== 'staff';
  const error = $('#login-error');
  if (error) error.hidden = true;
}

function hideLogin() {
  document.body.classList.remove('login-locked');
  const screen = $('#login-screen');
  if (screen) screen.hidden = true;
}

function handleUnauthorized() {
  state.token = '';
  state.user = null;
  state.started = false;
  localStorage.removeItem('zhixing-token');
  clearLoginFields();
  showLogin('登录已过期，请重新登录');
}

async function handleLogin(event) {
  event.preventDefault();
  const password = $('#login-password')?.value || '';
  const studentId = $('#login-student-id')?.value.trim() || '';
  const studentName = $('#login-name')?.value.trim() || '';
  const username = $('#login-username')?.value.trim() || '';
  const isStudent = state.loginMode === 'student';
  if (!password || (isStudent ? !studentId || !studentName : !username)) {
    showLogin(isStudent ? '请输入学号、姓名和密码' : '请输入账号和密码');
    return;
  }
  const button = $('#login-submit');
  if (button) {
    button.disabled = true;
    button.textContent = '登录中…';
  }
  try {
    const body = isStudent
      ? { student_id: studentId, name: studentName, password }
      : { username, password };
    const data = await api('/auth/login', {
      method: 'POST',
      body,
    });
    state.token = data.token;
    state.user = data.user;
    if (typeof resetLearningState === 'function') resetLearningState();
    state.started = false;
    localStorage.setItem('zhixing-token', data.token);
    const passwordInput = $('#login-password');
    if (passwordInput) passwordInput.value = '';
    await startApp();
    toast(`已登录：${data.user.name}`);
  } catch (error) {
    showLogin(error.message || '登录失败');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = '登录';
    }
  }
}

function clearLoginFields() {
  ['#login-student-id', '#login-name', '#login-username', '#login-password'].forEach((selector) => {
    const input = $(selector);
    if (input) input.value = '';
  });
}

function logout() {
  const previousRole = state.user?.role;
  state.token = '';
  state.user = null;
  state.started = false;
  state.session = null;
  state.sessionId = null;
  state.sessions = [];
  if (typeof resetLearningState === 'function') resetLearningState();
  localStorage.removeItem('zhixing-token');
  history.replaceState(null, '', location.pathname);
  setLoginMode(previousRole === 'student' ? 'student' : 'staff');
  clearLoginFields();
  showLogin();
}

function toggleProfileMenu(force) {
  const menu = $('#profile-menu');
  const container = $('#sidebar-user');
  if (!menu || !container) return;
  const open = typeof force === 'boolean' ? force : menu.hidden;
  menu.hidden = !open;
  container.classList.toggle('is-open', open);
  $('#profile-trigger')?.setAttribute('aria-expanded', String(open));
}

function closeProfileMenu() {
  toggleProfileMenu(false);
}

function switchAccount() {
  closeDrawer();
  closeProfileMenu();
  logout();
}

function openProfileDrawer() {
  const user = state.user;
  if (!user) return;
  closeProfileMenu();
  const isStudent = user.role === 'student';
  const rows = isStudent
    ? [
        ['学号', user.student_id || '—'],
        ['姓名', user.name],
        ['学院', user.college || '—'],
        ['专业', user.major || '—'],
        ['班级', user.class_name || '—'],
        ['届别', user.cohort || '—'],
        ['手机号', user.phone_masked || '—'],
        ['状态', user.status === 'active' ? '在籍' : user.status || '—'],
      ]
    : [
        ['账号', user.username],
        ['姓名', user.name],
        ['角色', ROLE_LABELS[user.role] || user.role],
        ['学院', user.college || '全校'],
      ];
  openDrawer(`
    <div class="drawer-head">
      <div>
        <span class="eyebrow">PROFILE</span>
        <h2>个人资料</h2>
      </div>
      <button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button>
    </div>
    <div class="drawer-body">
      <div class="profile-account">
        <span class="user-avatar">${escapeHtml(user.name.slice(0, 1))}</span>
        <div>
          <h3>${escapeHtml(user.name)}</h3>
          <p>${escapeHtml(ROLE_LABELS[user.role] || user.role)}${isStudent && user.class_name ? ` · ${escapeHtml(user.class_name)}` : ''}</p>
        </div>
      </div>
      <div class="detail-list">
        ${rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')}
      </div>
      <div class="profile-actions">
        <button type="button" class="ghost-btn" data-profile-action="switch">切换账户</button>
        <button type="button" class="ghost-btn profile-logout" data-profile-action="logout">退出登录</button>
      </div>
      <p class="login-note">${isStudent ? '学生初始密码为学号后六位，请勿转告他人。' : '工作人员账号仅用于本地课程演示。'}</p>
    </div>`);
}

function parseRoute() {
  const target = parseLocation();
  return target.mode === 'learning' ? 'learning' : target.route || 'campus';
}

async function navigate(route, { push = true } = {}) {
  if (!ROUTES[route]) route = 'campus';
  if (state.user && !allowedRoutes().includes(route)) route = defaultRoute();
  if (route === 'learning') {
    state.mode = 'learning';
    if (typeof learningState !== 'undefined' && learningState.tab) {
      state.learningTab = learningState.tab;
    }
  } else if (route === 'campus') {
    state.mode = 'campus';
    state.campusSection = 'home';
  } else if (route === 'chat') {
    if (state.mode === 'campus' && !CAMPUS_PROMPTS[state.campusSection]) {
      state.campusSection = 'chat';
    }
  } else {
    state.mode = 'campus';
    const sectionMap = {
      workorders: 'workorders',
      handoff: 'handoff',
      audit: 'audit',
      knowledge: 'knowledge',
      'lost-found': 'lostfound',
      feedback: 'feedback',
      students: 'students',
      evaluation: 'evaluation',
      system: 'system',
    };
    if (sectionMap[route]) {
      state.campusSection = sectionMap[route];
    }
  }
  state.route = route;
  document.body.classList.toggle('mode-learning', state.mode === 'learning');
  document.body.classList.toggle('mode-campus', state.mode === 'campus');
  renderSidebarNav();
  $$('.view').forEach((view) => view.classList.toggle('is-active', view.id === `view-${route}`));
  document.body.classList.toggle('pages-mode', route !== 'chat');
  updateChrome(route);
  setActiveNavigation();
  closeMobile();
  if (push && location.hash !== `#/${route}`) {
    location.hash = `#/${route}`;
  }

  if (route === 'campus') renderCampusHomePage();
  if (route === 'learning') await renderLearningPage();
  if (route === 'workorders') await renderWorkordersPage();
  if (route === 'handoff') await renderHandoffPage();
  if (route === 'audit') await renderAuditPage();
  if (route === 'knowledge') await renderKnowledgePage();
  if (route === 'lostfound') await renderLostFoundPage();
  if (route === 'feedback') await renderFeedbackPage();
  if (route === 'students') await renderStudentsPage();
  if (route === 'evaluation') await renderEvaluationPage();
  if (route === 'system') await renderSystemPage();
  if (route === 'chat') {
    toggleWelcome();
    scrollToBottom(false);
  }
  setActiveNavigation();
}

function updateChrome(route) {
  const section = ROUTES[route] || ROUTES.chat;
  $('#crumb-section').textContent = section;
  let title = ROUTE_TITLES[route] || state.session?.title || '新的对话';
  if (route === 'learning') {
    const activeLearning = LEARNING_NAV.find((item) => item.tab === state.learningTab);
    title = activeLearning?.label || ROUTE_TITLES.learning;
  }
  if (route === 'chat' && state.session?.title) title = state.session.title;
  $('#crumb-title').textContent = title;
  document.title = `知行 · ${section}`;
}

function bindEvents() {
  $('#login-form')?.addEventListener('submit', handleLogin);
  $$('[data-login-mode]').forEach((button) => {
    button.addEventListener('click', () => setLoginMode(button.dataset.loginMode));
  });
  $('#profile-trigger')?.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleProfileMenu();
  });
  $('#notifications-btn')?.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleNotificationMenu();
  });
  $('#notifications-read-all')?.addEventListener('click', (event) => {
    event.stopPropagation();
    markAllNotificationsRead();
  });

  $('#mode-toggle')?.addEventListener('click', toggleAppMode);
  $('#new-chat-btn').addEventListener('click', () => createSession());
  $('#theme-toggle').addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme();
  });
  $('#send-btn').addEventListener('click', () => {
    const value = $('#composer-input').value.trim();
    if (value) sendMessage(value);
  });
  $('#composer-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      const value = event.target.value.trim();
      if (value) sendMessage(value);
    }
  });
  $('#composer-input').addEventListener('input', autoResizeComposer);
  $('#inspector-toggle').addEventListener('click', () => $('#inspector').classList.add('is-open'));
  $('#inspector-close').addEventListener('click', () => $('#inspector').classList.remove('is-open'));
  $('#mobile-menu').addEventListener('click', () => {
    $('#sidebar').classList.add('is-open');
    $('#mobile-overlay').classList.add('is-open');
  });
  $('#mobile-overlay').addEventListener('click', closeMobile);

  window.addEventListener('hashchange', () => {
    applyLocation();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeDrawer();
      $('#inspector').classList.remove('is-open');
      closeMobile();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
      event.preventDefault();
      createSession();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (state.route !== 'chat') navigate('chat');
      $('#composer-input').focus();
    }
    if (event.key === 'Enter' && event.target.id === 'knowledge-search') {
      event.preventDefault();
      runKnowledgeSearch(event.target.value.trim());
    }
    if (event.key === 'Enter' && event.target.id === 'student-search') {
      event.preventDefault();
      readStudentFilters();
      renderStudentsPage();
    }
    if (event.key === 'Enter' && event.target.id === 'lostfound-search') {
      event.preventDefault();
      state.lostFoundQuery = event.target.value.trim();
      renderLostFoundPage();
    }
  });

  document.addEventListener('click', handleDocumentClick);
  document.addEventListener('change', handleDocumentChange);
}

function closeMobile() {
  $('#sidebar').classList.remove('is-open');
  $('#mobile-overlay').classList.remove('is-open');
}

function autoResizeComposer() {
  const input = $('#composer-input');
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

function focusComposer() {
  const input = $('#composer-input');
  input.focus();
  autoResizeComposer();
}

/* ============================================================
   会话
   ============================================================ */

async function loadSessions() {
  try {
    const data = await api('/sessions');
    state.sessions = data.items || [];
    const current = state.sessions.find((item) => item.id === state.sessionId);
    if (current && state.session) {
      state.session.title = current.title;
      state.session.updated_at = current.updated_at;
    }
    renderSessionList();
    updateChrome(state.route);
  } catch (error) {
    /* 会话列表刷新失败不阻塞对话 */
  }
}

function renderSessionList() {
  const list = $('#session-list');
  if (!state.sessions.length) {
    list.innerHTML = '<div class="session-empty">还没有对话记录</div>';
  } else {
    list.innerHTML = state.sessions
      .map((session) => {
        const active = session.id === state.sessionId ? ' is-active' : '';
        const preview = session.last_message_preview || '';
        return `
          <div class="session-item${active}" data-session-id="${escapeAttr(session.id)}" role="button" tabindex="0">
            <span class="session-title">${escapeHtml(session.title || '新的对话')}</span>
            <span class="session-preview">${escapeHtml(truncate(preview, 34)) || '暂无消息'}</span>
            <span class="session-time">${escapeHtml(relativeTime(session.updated_at))}</span>
            <button class="session-delete" type="button" data-delete-session="${escapeAttr(session.id)}" aria-label="删除会话">
              ${icon('close')}
            </button>
          </div>`;
      })
      .join('');
  }
  $('#session-count').textContent = String(state.sessions.length);
}

async function createSession({ silent = false } = {}) {
  try {
    const session = await api('/sessions', { method: 'POST', body: {} });
    state.sessionId = session.id;
    state.session = session;
    state.messages = [];
    state.trace = [];
    state.workorder = null;
    state.lastFailedText = '';
    await loadSessions();
    await navigate('chat');
    renderMessages();
    renderInspector();
    updateChrome('chat');
    if (!silent) {
      focusComposer();
      toast('已新建对话');
    }
    return session;
  } catch (error) {
    toast(error.message, 'error');
    return null;
  }
}

async function selectSession(sessionId, { silent = false } = {}) {
  try {
    const session = await api(`/sessions/${sessionId}`);
    state.sessionId = sessionId;
    state.session = session;
    state.messages = session.messages || [];
    state.workorder = null;
    if (new URLSearchParams(location.search).has('session')) {
      const url = new URL(location.href);
      url.searchParams.set('session', sessionId);
      history.replaceState(null, '', url);
    }
    const lastAssistant = [...state.messages].reverse().find(
      (message) => message.role === 'assistant' && (message.trace || []).length > 0
    );
    state.trace = lastAssistant?.trace || [];

    if (session.current_workflow_id) {
      try {
        state.workorder = await api(`/workorders/${session.current_workflow_id}`);
      } catch (error) {
        state.workorder = null;
      }
    }
    if (state.route !== 'chat') await navigate('chat', { push: true });
    renderMessages();
    renderInspector();
    updateChrome('chat');
    renderSessionList();
    if (!silent) closeMobile();
    scrollToBottom(true);
    setTimeout(() => scrollToBottom(true), 120);
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteSession(sessionId) {
  if (!window.confirm('删除这个会话及其消息记录？此操作不可撤销。')) return;
  try {
    await api(`/sessions/${sessionId}`, { method: 'DELETE' });
    state.sessions = state.sessions.filter((session) => session.id !== sessionId);
    if (state.sessionId === sessionId) {
      if (state.sessions.length > 0) {
        await selectSession(state.sessions[0].id, { silent: true });
      } else {
        await createSession({ silent: true });
      }
    }
    renderSessionList();
    await refreshBadge();
    toast('会话已删除');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function refreshBadge() {
  try {
    const data = await api('/workorders');
    state.workorderCounts = data.counts || {};
    const active =
      (data.counts?.awaiting_confirm || 0) +
      (data.counts?.awaiting_approval || 0) +
      (data.counts?.awaiting_input || 0) +
      (data.counts?.in_progress || 0);
    const badge = $('#nav-workorder-badge');
    badge.hidden = active <= 0;
    badge.textContent = String(active);
  } catch (error) {
    /* 忽略角标刷新失败 */
  }
}

/* ============================================================
   对话与消息渲染
   ============================================================ */

function renderWelcome() {
  const welcome = $('#welcome');
  if (welcome && !welcome.innerHTML.trim()) {
    welcome.hidden = true;
  }
}

function toggleWelcome() {
  const welcome = $('#welcome');
  const hasMessages = state.messages.length > 0;
  welcome.classList.toggle('is-hidden', hasMessages);
}

function renderMessages() {
  const container = $('#messages');
  container.innerHTML = '';
  state.messages.forEach((message) => container.appendChild(buildMessageEl(message)));
  toggleWelcome();
  hydrateLatestWorkorder();
  scrollToBottom(true);
}

function appendMessage(message) {
  const container = $('#messages');
  const el = buildMessageEl(message);
  container.appendChild(el);
  state.messages.push(message);
  toggleWelcome();
  scrollToBottom(true);
  return el;
}

function buildMessageEl(message) {
  const isUser = message.role === 'user';
  const article = document.createElement('article');
  article.className = `message ${isUser ? 'user' : 'assistant'}`;
  article.dataset.msgId = message.id || '';

  if (isUser) {
    article.innerHTML = `
      <div class="avatar user-avatar">你</div>
      <div class="msg-body">
        <div class="bubble"><div class="md">${renderMarkdown(message.content)}</div></div>
        <div class="msg-time">${escapeHtml(formatTime(message.timestamp))}</div>
      </div>`;
    return article;
  }

  const agent = agentMeta(message);
  const confidence = Number.isFinite(Number(message.confidence))
    ? `<span class="confidence">置信度 ${Number(message.confidence).toFixed(2)}</span>`
    : '';
  article.innerHTML = `
    <div class="avatar assistant-avatar">${icon('bot')}</div>
    <div class="msg-body">
      <div class="msg-head">
        <span class="agent-tag ${agent.cls}">${icon(agent.icon)}${agent.label}</span>
        ${confidence}
        <span class="msg-time">${escapeHtml(formatTime(message.timestamp))}</span>
      </div>
      <div class="bubble">
        <div class="md">${renderMarkdown(message.content)}</div>
        ${citationsHTML(message.citations)}
        ${toolCallsHTML(message.tool_calls)}
        ${actionsHTML(message)}
        ${navigationActionsHTML(message)}
      </div>
    </div>`;
  return article;
}

function agentMeta(message) {
  const intent = message.metadata?.intent || '';
  if (intent === 'workflow') return { label: '办事流程', cls: 'workflow', icon: 'ticket' };
  if (intent === 'human_handoff') return { label: '转人工', cls: 'handoff', icon: 'user' };
  if (intent === 'clarify') return { label: '澄清', cls: 'clarify', icon: 'chat' };
  return { label: '知识问答', cls: 'qa', icon: 'search' };
}

function renderMarkdown(text) {
  let safe = escapeHtml(text || '');
  safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
  safe = safe.replace(/\[(\d+)\]/g, '<button type="button" class="cite-mark" data-cite="$1" title="定位引用 $1">$1</button>');

  const lines = safe.split('\n');
  let html = '';
  let inList = false;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      html += '<div class="spacer"></div>';
      continue;
    }
    if (/^[-•]\s+/.test(line)) {
      if (!inList) {
        html += '<ul>';
        inList = true;
      }
      html += `<li>${line.replace(/^[-•]\s+/, '')}</li>`;
    } else {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      html += `<p>${line}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}

function citationsHTML(citations) {
  if (!Array.isArray(citations) || citations.length === 0) return '';
  const cards = citations
    .map((citation, index) => {
      const score = Math.min(1, Math.max(0, Number(citation.score) || 0));
      return `
        <div class="citation-card" data-cite="${index + 1}">
          <div class="citation-top">
            <span class="citation-index">${index + 1}</span>
            <div class="citation-title">
              《${escapeHtml(citation.doc_title)}》
              <span class="citation-chapter">${escapeHtml(citation.chapter || '')}</span>
            </div>
            <span class="citation-score">${Math.round(score * 100)}%</span>
          </div>
          <p class="citation-snippet">${escapeHtml(citation.content_snippet)}</p>
          <div class="citation-foot">
            <span>${escapeHtml(citation.doc_number || citation.category || '')}</span>
            <div class="citation-bar"><span style="width:${Math.round(score * 100)}%"></span></div>
            <button type="button" class="doc-link" data-doc="${escapeAttr(citation.doc_id)}">查看原文</button>
          </div>
        </div>`;
    })
    .join('');
  return `
    <details class="citations" open>
      <summary>${icon('book')} 引用来源 · ${citations.length} 条</summary>
      <div class="citation-list">${cards}</div>
    </details>`;
}

function toolCallsHTML(calls) {
  if (!Array.isArray(calls) || calls.length === 0) return '';
  const rows = calls
    .map(
      (call) => `
      <div class="tool-row">
        <span class="tool-status ${call.success ? '' : 'failed'}"></span>
        <span class="tool-name">${escapeHtml(call.tool_name)}</span>
        <span>${call.success ? '成功' : '失败'}</span>
        <span class="tool-latency">${Number(call.latency_ms) || 0}ms</span>
      </div>`
    )
    .join('');
  return `
    <details class="toolcalls">
      <summary>${icon('cpu')} 工具调用 · ${calls.length} 次</summary>
      <div class="tool-list">${rows}</div>
    </details>`;
}

function actionsHTML(message) {
  let actions = message.metadata?.suggested_actions || [];
  if (!Array.isArray(actions) || actions.length === 0) return '';
  if (message.metadata?.requires_confirmation) {
    // 确认/取消由工单卡片承载，避免同一动作出现两套按钮
    actions = actions.filter((action) => !['确认提交', '取消'].includes(action));
  }
  if (!actions.length) return '';
  return `<div class="action-chips">${actions
    .map((action) => `<button type="button" class="action-chip" data-action="${escapeAttr(action)}">${escapeHtml(action)}</button>`)
    .join('')}</div>`;
}

function navigationActionsHTML(message) {
  if (!message || message.role !== 'assistant') return '';
  let content = String(message.content || '');
  const messageIndex = state.messages.findIndex((item) => item.id && item.id === message.id);
  if (messageIndex >= 0) {
    const lastUser = [...state.messages.slice(0, messageIndex)]
      .reverse()
      .find((item) => item.role === 'user');
    if (lastUser) content += ` ${lastUser.content || ''}`;
  }
  const intents = [
    { pattern: /(补办|补卡|校园卡)/, mode: 'campus', section: 'card-reissue', label: '打开校园卡补办' },
    { pattern: /(网络|报修|维修)/, mode: 'campus', section: 'network-repair', label: '打开网络报修' },
    { pattern: /(请假|销假)/, mode: 'campus', section: 'leave', label: '打开请假申请' },
    { pattern: /(工单|办理进度|回执)/, mode: 'campus', section: 'workorders', label: '打开工单中心' },
    { pattern: /(知识库|制度|政策|条款)/, mode: 'campus', section: 'knowledge', label: '打开知识库' },
    { pattern: /(评测|指标|召回)/, mode: 'campus', section: 'evaluation', label: '打开评测中心' },
    { pattern: /(错题|错题本)/, mode: 'learning', section: 'mistakes', label: '打开错题本' },
    { pattern: /(专注|番茄)/, mode: 'learning', section: 'focus', label: '打开专注' },
    { pattern: /(任务|清单)/, mode: 'learning', section: 'tasks', label: '打开任务清单' },
    { pattern: /(日历|课程表)/, mode: 'learning', section: 'calendar', label: '打开日历与课程' },
  ];
  const found = intents.filter((item) => item.pattern.test(content)).slice(0, 2);
  if (!found.length) return '';
  return `<div class="navigation-chips">${found.map((item) => `
    <button type="button" class="navigation-chip" data-nav-mode="${item.mode}" data-nav-section="${item.section}">
      ${escapeHtml(item.label)} ${icon('arrow')}
    </button>`).join('')}</div>`;
}

async function hydrateLatestWorkorder() {
  const last = [...state.messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.metadata?.workorder_id);
  if (!last) return;
  const article = $$('.message').find((node) => node.dataset.msgId === last.id);
  if (!article || article.querySelector('.workorder-card')) return;
  let order = state.workorder;
  if (!order || order.id !== last.metadata.workorder_id) {
    try {
      order = await api(`/workorders/${last.metadata.workorder_id}`);
    } catch (error) {
      return;
    }
  }
  const bubble = article.querySelector('.bubble');
  if (!bubble) return;
  bubble.insertAdjacentHTML(
    'beforeend',
    workorderHTML(order, Boolean(last.metadata?.requires_confirmation))
  );
  scrollToBottom(true);
}

function scrollToBottom(force = false) {
  const scroll = $('#chat-scroll');
  if (!scroll) return;
  const distance = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight;
  if (force || distance < 180) {
    scroll.scrollTo({ top: scroll.scrollHeight, behavior: 'auto' });
  }
}

function showTyping() {
  const container = $('#messages');
  const el = document.createElement('article');
  el.className = 'message assistant';
  el.innerHTML = `
    <div class="avatar assistant-avatar">${icon('bot')}</div>
    <div class="msg-body">
      <div class="msg-head">
        <span class="agent-tag qa">${icon('spark')}Agent 处理中</span>
      </div>
      <div class="bubble typing-bubble">
        <span class="typing-dots"><i></i><i></i><i></i></span>
        <span class="typing-text">正在识别意图…</span>
      </div>
    </div>`;
  container.appendChild(el);
  scrollToBottom(true);
  const phases = [
    [0, '正在识别意图…'],
    [1200, '混合检索校内制度…'],
    [3200, '生成回答并校验引用…'],
  ];
  const timers = phases.map(([delay, text]) =>
    setTimeout(() => {
      const node = el.querySelector('.typing-text');
      if (node) node.textContent = text;
    }, delay)
  );
  return {
    remove() {
      timers.forEach(clearTimeout);
      el.remove();
    },
  };
}

async function sendMessage(rawText, { retry = false } = {}) {
  const text = String(rawText || '').trim();
  if (!text || state.sending) return;
  if (!state.sessionId) {
    const session = await createSession({ silent: true });
    if (!session) return;
  }

  state.sending = true;
  $('#send-btn').disabled = true;
  state.lastFailedText = text;

  if (!retry) {
    const userMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
      citations: [],
      tool_calls: [],
      metadata: {},
      trace: [],
    };
    appendMessage(userMessage);
    $('#composer-input').value = '';
    autoResizeComposer();
  }

  const typing = showTyping();
  renderInspectorRunning();

  try {
    const response = await api('/chat/send', {
      method: 'POST',
      body: { session_id: state.sessionId, message: text },
    });
    typing.remove();
    state.trace = response.trace || [];
    state.workorder = response.workorder || null;
    const el = appendMessage(response.message);
    if (response.workorder) {
      const bubble = el.querySelector('.bubble');
      bubble.insertAdjacentHTML(
        'beforeend',
        workorderHTML(response.workorder, response.requires_confirmation)
      );
    }
    renderInspector();
    await loadSessions();
    await refreshBadge();
    updateChrome(state.route);
    scrollToBottom(true);
    setTimeout(() => scrollToBottom(true), 120);
  } catch (error) {
    typing.remove();
    renderInspector();
    showSendError(error, text);
  } finally {
    state.sending = false;
    $('#send-btn').disabled = false;
    focusComposer();
  }
}

function showSendError(error, text) {
  const container = $('#messages');
  const el = document.createElement('article');
  el.className = 'message assistant';
  el.innerHTML = `
    <div class="avatar assistant-avatar">${icon('alert')}</div>
    <div class="msg-body">
      <div class="msg-head"><span class="agent-tag handoff">${icon('alert')}请求失败</span></div>
      <div class="bubble">
        <div class="md"><p>${escapeHtml(error.message || '网络异常，请稍后重试')}</p></div>
        <div class="action-chips">
          <button type="button" class="action-chip" data-retry-send="${escapeAttr(text)}">重新发送</button>
        </div>
      </div>
    </div>`;
  container.appendChild(el);
  scrollToBottom(true);
  toast(error.message || '请求失败', 'error');
}

/* ============================================================
   工单卡片与确认
   ============================================================ */

function workorderHTML(order, requiresConfirm = false) {
  if (!order) return '';
  const status = STATUS_MAP[order.status] || { label: order.status, cls: 'draft' };
  const inputs = order.user_inputs || {};
  const profile = inputs.student_profile || {};
  const result = order.result || {};
  const canConfirm = requiresConfirm || order.status === 'awaiting_confirm';
  const timeline = workorderTimelineHTML(order);
  const receipt = order.receipt_number
    ? `<div class="wo-receipt">
         <span>回执编号</span>
         <strong>${escapeHtml(order.receipt_number)}</strong>
         <button type="button" class="copy-btn" data-copy="${escapeAttr(order.receipt_number)}" title="复制回执">${icon('copy')}</button>
       </div>`
    : '';

  return `
    <div class="workorder-card" data-workorder-id="${escapeAttr(order.id)}">
      <div class="wo-head">
        <div>
          <span class="wo-label">${escapeHtml(order.workflow_type || 'WORK ORDER')}</span>
          <strong class="wo-title">${escapeHtml(WORKFLOW_NAME[order.workflow_type] || '办事工单')}</strong>
        </div>
        <span class="status-pill status-${escapeAttr(status.cls)}">${escapeHtml(status.label)}</span>
      </div>
      ${receipt}
      <div class="wo-grid">
        <div><span>学号</span><b>${escapeHtml(inputs.student_id || '待补充')}</b></div>
        <div><span>校区</span><b>${escapeHtml(inputs.campus || '待补充')}</b></div>
        <div><span>预约时段</span><b>${escapeHtml(result.slot_id || '确认后生成')}</b></div>
        <div><span>工本费</span><b>${escapeHtml(result.fee != null ? `${result.fee} 元` : '20 元')}</b></div>
      </div>
      ${profile.name ? `<div class="wo-note">${icon('user')} ${profile.source === 'roster' ? '学生库' : '学籍'}：${escapeHtml(profile.name)}${profile.major ? ` · ${escapeHtml(profile.major)}` : ''}${profile.class_name ? ` · ${escapeHtml(profile.class_name)}` : ''}</div>` : ''}
      ${result.location ? `<div class="wo-note">${icon('library')} 取卡地点：${escapeHtml(result.location)}</div>` : ''}
      ${profile.source === 'roster' && profile.simulated_card_state ? `<div class="wo-note">${icon('alert')} 一卡通挂失/余额为模拟数据，学籍信息来自学生库</div>` : ''}
      ${order.error_message ? `<div class="wo-note danger">${icon('alert')} ${escapeHtml(order.error_message)}</div>` : ''}
      <div class="wo-actions">
        ${canConfirm ? `
          <button type="button" class="primary-btn" data-confirm-action="confirm">确认提交</button>
          <button type="button" class="ghost-btn" data-confirm-action="cancel">取消</button>` : ''}
        <button type="button" class="ghost-btn" data-open-workorder="${escapeAttr(order.id)}">${icon('external')} 查看工单</button>
      </div>
      ${timeline}
    </div>`;
}

function workorderTimelineHTML(order) {
  const history = order.node_history || [];
  if (!history.length) return '';
  const steps = history
    .slice(-10)
    .map((record) => {
      const failed = record.status === 'failed';
      const note = record.error || (record.outputs?.summary ? truncate(record.outputs.summary, 46) : '');
      return `
        <li class="wo-step ${failed ? 'failed' : ''}">
          <span class="wo-step-dot"></span>
          <div class="wo-step-body">
            <div class="wo-step-title">
              <span>${escapeHtml(record.node_name || record.node_id)}</span>
              <em>${Number(record.duration_ms) || 0}ms</em>
            </div>
            ${note ? `<div class="wo-step-note">${escapeHtml(note)}</div>` : ''}
          </div>
        </li>`;
    })
    .join('');
  return `
    <details class="wo-timeline">
      <summary>节点轨迹 · ${history.length} 步</summary>
      <ol class="wo-steps">${steps}</ol>
    </details>`;
}

async function handleConfirm(action, button) {
  if (!state.sessionId) {
    toast('当前没有可确认的会话', 'error');
    return;
  }
  const card = button.closest('.workorder-card');
  if (card) {
    card.querySelectorAll('button').forEach((item) => {
      item.disabled = true;
    });
  }
  try {
    const response = await api(`/chat/sessions/${state.sessionId}/confirm`, {
      method: 'POST',
      body: { action },
    });
    state.trace = response.trace || [];
    state.workorder = response.workorder || null;
    const el = appendMessage(response.message);
    if (response.workorder) {
      el.querySelector('.bubble').insertAdjacentHTML(
        'beforeend',
        workorderHTML(response.workorder, response.requires_confirmation)
      );
    }
    renderInspector();
    await loadSessions();
    await refreshBadge();
    scrollToBottom(true);
    setTimeout(() => scrollToBottom(true), 120);
    toast(action === 'confirm' ? '已确认并提交工单' : '已取消本次办理');
  } catch (error) {
    toast(error.message, 'error');
    if (card) {
      card.querySelectorAll('button').forEach((item) => {
        item.disabled = false;
      });
    }
  }
}

async function handleAction(label) {
  if (!label) return;
  if (label === '确认提交') {
    const button = $(`[data-confirm-action="confirm"]`);
    if (button) await handleConfirm('confirm', button);
    else await sendMessage(label);
    return;
  }
  if (label === '取消') {
    const button = $(`[data-confirm-action="cancel"]`);
    if (button) await handleConfirm('cancel', button);
    return;
  }
  if (label === '查看工单') {
    await navigate('workorders');
    return;
  }
  if (label === '换个问法') {
    focusComposer();
    return;
  }
  if (label === '再办一张') {
    await sendMessage('我要补办校园卡');
    return;
  }
  await sendMessage(label);
}

/* ============================================================
   轨迹面板
   ============================================================ */

function renderInspector() {
  const body = $('#inspector-body');
  if (!state.trace.length && !state.workorder) {
    body.innerHTML = `
      <div class="inspector-empty">
        <span class="empty-orb">${icon('pulse')}</span>
        <p>本轮对话的意图识别、混合检索、工具调用与引用校验步骤会显示在这里。</p>
      </div>`;
    return;
  }

  let html = '';
  if (state.trace.length) {
    html += `<div class="trace-summary">${icon('pulse')} 本轮 <strong>${state.trace.length}</strong> 个执行步骤</div>`;
    html += state.trace.map(traceStepHTML).join('');
  }
  if (state.workorder) {
    html += miniOrderHTML(state.workorder);
  }
  body.innerHTML = html;
}

function renderInspectorRunning() {
  const body = $('#inspector-body');
  body.innerHTML = `
    <div class="trace-summary">${icon('pulse')} Agent 正在执行…</div>
    ${['意图识别', '混合检索', '生成与校验']
      .map(
        (title) => `
        <div class="trace-block running">
          <span class="trace-dot"></span>
          <div class="trace-title">${title}<span class="trace-latency">running</span></div>
          <p class="trace-detail">等待模型与工具返回…</p>
        </div>`
      )
      .join('')}`;
}

function traceStepHTML(step) {
  const status = step.status || 'success';
  const latency = step.latency_ms != null ? `${step.latency_ms}ms` : '';
  const dataKeys = step.data && Object.keys(step.data).length > 0;
  return `
    <div class="trace-block ${escapeAttr(status)}">
      <span class="trace-dot"></span>
      <div class="trace-title">
        <span class="trace-type">${escapeHtml(step.type || '')}</span>
        ${escapeHtml(step.title || '')}
        <span class="trace-latency">${escapeHtml(latency)}</span>
      </div>
      ${step.detail ? `<p class="trace-detail">${escapeHtml(step.detail)}</p>` : ''}
      ${dataKeys ? `
        <details class="trace-data">
          <summary>查看数据</summary>
          <pre>${escapeHtml(JSON.stringify(step.data, null, 2))}</pre>
        </details>` : ''}
    </div>`;
}

function miniOrderHTML(order) {
  const status = STATUS_MAP[order.status] || { label: order.status, cls: 'draft' };
  return `
    <div class="inspector-section">
      <h3>当前工单</h3>
      <div class="mini-order">
        <div class="mini-row"><span>状态</span><b><span class="status-pill status-${escapeAttr(status.cls)}">${escapeHtml(status.label)}</span></b></div>
        <div class="mini-row"><span>回执</span><b>${escapeHtml(order.receipt_number || '待生成')}</b></div>
        <div class="mini-row"><span>学号</span><b>${escapeHtml(order.user_inputs?.student_id || '—')}</b></div>
        <div class="mini-row"><span>校区</span><b>${escapeHtml(order.user_inputs?.campus || '—')}</b></div>
        <div class="mini-row"><span>节点</span><b>${escapeHtml(order.current_node || '—')}</b></div>
      </div>
    </div>`;
}

/* ============================================================
   页面：工单中心
   ============================================================ */

async function renderWorkordersPage() {
  const page = $('#workorders-page');
  page.innerHTML = loadingPage('正在加载工单…');
  try {
    const data = await api('/workorders');
    state.workorders = data.items || [];
    state.workorderCounts = data.counts || {};
    const counts = state.workorderCounts;
    const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
    const awaiting = (counts.awaiting_confirm || 0) + (counts.awaiting_input || 0);
    const completed = counts.completed || 0;
    const transferred = counts.transferred_human || 0;
    const failed = counts.failed || 0;

    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">WORK ORDERS</span>
            <h1>工单中心</h1>
            <p>每张工单都记录了完整的节点流转、工具调用与回执编号，可随时回放办事过程。</p>
          </div>
          <div class="head-actions">
            <button type="button" class="ghost-btn" data-refresh-workorders>${icon('refresh')} 刷新</button>
          </div>
        </div>

        <div class="stat-grid">
          ${statCard('全部工单', total, '含草稿与已结束', 'ticket')}
          ${statCard('已完成', completed, '已生成回执', 'check')}
          ${statCard('待跟进', awaiting, '待补充 / 待确认', 'clock')}
          ${statCard('异常与转人工', failed + transferred, '失败、取消、转人工', 'alert')}
        </div>

        <div class="toolbar">
          ${workorderFilterChip('all', '全部', total)}
          ${workorderFilterChip('awaiting', '待确认', awaiting)}
          ${workorderFilterChip('completed', '已完成', completed)}
          ${workorderFilterChip('failed', '未通过', failed)}
          ${workorderFilterChip('transferred', '转人工', transferred)}
        </div>
        <div class="table-card" id="workorder-table-wrap"></div>
      </div>`;
    renderWorkorderTable();
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'workorders');
  }
}

function statCard(label, value, foot, iconName) {
  const iconMap = {
    ticket: 'ticket',
    check: 'check',
    clock: 'clock',
    alert: 'alert',
    book: 'book',
    chart: 'chart',
    pulse: 'pulse',
    cpu: 'cpu',
  };
  return `
    <div class="stat-card">
      <div class="stat-top">
        <span class="stat-label">${escapeHtml(label)}</span>
        <span class="stat-icon">${icon(iconMap[iconName] || 'pulse')}</span>
      </div>
      <strong class="stat-value">${escapeHtml(value)}</strong>
      <div class="stat-foot">${escapeHtml(foot)}</div>
    </div>`;
}

function workorderFilterChip(key, label, count) {
  const active = state.workorderFilter === key ? ' is-active' : '';
  return `<button type="button" class="filter-chip${active}" data-wo-filter="${key}">
    ${escapeHtml(label)}<span class="count">${count}</span>
  </button>`;
}

function workorderMatchesFilter(order) {
  const filter = state.workorderFilter;
  if (filter === 'all') return true;
  if (filter === 'awaiting') {
    return ['awaiting_confirm', 'awaiting_input', 'in_progress', 'draft'].includes(order.status);
  }
  if (filter === 'failed') return ['failed', 'cancelled'].includes(order.status);
  return order.status === filter;
}

function renderWorkorderTable() {
  const wrap = $('#workorder-table-wrap');
  if (!wrap) return;
  const rows = state.workorders.filter(workorderMatchesFilter);
  if (!rows.length) {
    wrap.innerHTML = emptyState('ticket', '暂无工单', '发起一次“我要补办校园卡”，这里就会出现完整办理记录。');
    return;
  }
  wrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>回执 / 工单</th>
          <th>流程</th>
          <th>状态</th>
          <th>学号 / 校区</th>
          <th>更新时间</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((order) => {
            const status = STATUS_MAP[order.status] || { label: order.status, cls: 'draft' };
            return `
              <tr data-workorder-row="${escapeAttr(order.id)}">
                <td>
                  <div class="cell-title">
                    <strong class="mono">${escapeHtml(order.receipt_number || order.id)}</strong>
                    <span>${escapeHtml(order.id)}</span>
                  </div>
                </td>
                <td>${escapeHtml(WORKFLOW_NAME[order.workflow_type] || order.workflow_type)}</td>
                <td><span class="status-pill status-${escapeAttr(status.cls)}">${escapeHtml(status.label)}</span></td>
                <td>${escapeHtml(order.user_inputs?.student_id || '—')}<br /><span class="cell-sub">${escapeHtml(order.user_inputs?.campus || '—')}</span></td>
                <td class="mono">${escapeHtml(formatDateTime(order.updated_at))}</td>
                <td class="table-actions">${icon('chevron')}</td>
              </tr>`;
          })
          .join('')}
      </tbody>
    </table>`;
}

async function withdrawLeave(workorderId) {
  if (!window.confirm('撤回后本次请假申请会取消，需要重新提交。确认撤回？')) return;
  try {
    await api(`/approvals/${workorderId}/withdraw`, { method: 'POST' });
    toast('请假申请已撤回。');
    closeDrawer();
    await renderWorkordersPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function returnFromLeave(workorderId) {
  if (!window.confirm('确认已返校并销假？销假后不能撤销。')) return;
  try {
    await api(`/approvals/${workorderId}/return`, { method: 'POST' });
    toast('销假完成，欢迎返校。');
    closeDrawer();
    await renderWorkordersPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function openWorkorderDrawer(workorderId) {
  try {
    const [order, audit] = await Promise.all([
      api(`/workorders/${workorderId}`),
      api(`/workorders/${workorderId}/audit`).catch(() => ({ items: [] })),
    ]);
    const status = STATUS_MAP[order.status] || { label: order.status, cls: 'draft' };
    const inputs = order.user_inputs || {};
    const result = order.result || {};
    const steps = (order.node_history || [])
      .map(
        (record) => `
        <li class="wo-step ${record.status === 'failed' ? 'failed' : ''}">
          <span class="wo-step-dot"></span>
          <div class="wo-step-body">
            <div class="wo-step-title">
              <span>${escapeHtml(record.node_name)} <span class="node-type">${escapeHtml(record.node_type)}</span></span>
              <em>${Number(record.duration_ms) || 0}ms</em>
            </div>
            ${record.error ? `<div class="wo-step-note">${escapeHtml(record.error)}</div>` : ''}
          </div>
        </li>`
      )
      .join('');
    const auditRows = (audit.items || [])
      .slice(-24)
      .map(
        (event) => `
        <li class="drawer-audit-row">
          <span class="mono">${escapeHtml(formatDateTime(event.timestamp))}</span>
          <span class="event-chip">${escapeHtml(EVENT_MAP[event.event_type] || event.event_type)}</span>
          <span>${escapeHtml(auditSummary(event))}</span>
        </li>`
      )
      .join('');

    openDrawer(`
      <div class="drawer-head">
        <div>
          <span class="eyebrow">${escapeHtml(order.workflow_type)}</span>
          <h2>${escapeHtml(WORKFLOW_NAME[order.workflow_type] || '办事工单')}</h2>
          <div class="drawer-meta">
            <span class="status-pill status-${escapeAttr(status.cls)}">${escapeHtml(status.label)}</span>
            <span class="mono">${escapeHtml(order.receipt_number || order.id)}</span>
          </div>
        </div>
        <button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button>
      </div>

      <div class="detail-grid">
        ${detailItem('学号', inputs.student_id || '—')}
        ${detailItem('校区', inputs.campus || '—')}
        ${detailItem('预约时段', result.slot_id || '—')}
        ${detailItem('工本费', result.fee != null ? `${result.fee} 元` : '20 元')}
        ${detailItem('取卡地点', result.location || '—')}
        ${detailItem('创建时间', formatDateTime(order.created_at))}
      </div>

      ${order.error_message ? `<div class="notice-box danger">${icon('alert')} ${escapeHtml(order.error_message)}</div>` : ''}
      ${order.workflow_type === 'leave_request' && order.status === 'awaiting_approval'
        ? `<div class="drawer-section"><button type="button" class="ghost-btn profile-logout" data-withdraw-leave="${escapeAttr(order.id)}">撤回请假申请</button></div>`
        : ''}
      ${order.workflow_type === 'leave_request' && order.status === 'completed' && !result.returned_at
        ? `<div class="drawer-section"><button type="button" class="primary-btn" data-return-leave="${escapeAttr(order.id)}">返校销假</button></div>`
        : ''}
      ${order.receipt_number ? `
        <div class="drawer-section">
          <button type="button" class="primary-btn" data-copy="${escapeAttr(order.receipt_number)}">${icon('copy')} 复制回执编号</button>
        </div>` : ''}

      <div class="drawer-section">
        <h3>节点轨迹</h3>
        ${steps ? `<ol class="wo-steps drawer-steps">${steps}</ol>` : '<p class="muted-text">暂无节点记录</p>'}
      </div>

      <div class="drawer-section">
        <h3>审计留痕</h3>
        ${auditRows ? `<ul class="drawer-audit">${auditRows}</ul>` : '<p class="muted-text">暂无审计记录</p>'}
      </div>
    `);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function detailItem(label, value) {
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`;
}

/* ============================================================
   页面：审计回放
   ============================================================ */

async function renderAuditPage() {
  const page = $('#audit-page');
  page.innerHTML = loadingPage('正在读取审计日志…');
  try {
    const [recent, sessions] = await Promise.all([
      api('/audit/recent?limit=120'),
      api('/sessions'),
    ]);
    state.auditEvents = recent.items || [];
    state.sessions = sessions.items || [];
    if (state.auditSessionId && !state.sessions.some((item) => item.id === state.auditSessionId)) {
      state.auditSessionId = '';
    }
    const toolCalls = state.auditEvents.filter((event) => event.event_type === 'tool_call').length;
    const handoffs = state.auditEvents.filter((event) => event.event_type === 'handoff').length;

    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">AUDIT TRAIL</span>
            <h1>审计回放</h1>
            <p>用户消息、意图、检索、工具调用、节点流转与确认动作全部落盘，可按会话或事件类型回放。</p>
          </div>
          <div class="head-actions">
            <button type="button" class="ghost-btn" data-refresh-audit>${icon('refresh')} 刷新</button>
          </div>
        </div>

        <div class="stat-grid">
          ${statCard('审计事件', state.auditEvents.length, '最近 120 条', 'pulse')}
          ${statCard('工具调用', toolCalls, '含重试与失败', 'cpu')}
          ${statCard('转人工', handoffs, '保留上下文', 'user')}
          ${statCard('会话总数', state.sessions.length, '按更新时间排序', 'chat')}
        </div>

        <div class="audit-layout">
          <div class="section-card">
            <div class="section-head">
              <div>
                <h3>事件时间线</h3>
                <p class="section-sub">选择会话可拉取该会话的完整链路</p>
              </div>
              <div class="audit-filters">
                <select class="select-input" id="audit-type-filter">
                  ${auditTypeOptions()}
                </select>
                <select class="select-input" id="audit-session-select">
                  <option value="">全部会话</option>
                  ${state.sessions
                    .map(
                      (session) =>
                        `<option value="${escapeAttr(session.id)}" ${state.auditSessionId === session.id ? 'selected' : ''}>${escapeHtml(session.title)}</option>`
                    )
                    .join('')}
                </select>
              </div>
            </div>
            <div class="event-list" id="audit-event-list"></div>
          </div>

          <aside class="audit-side">
            <div class="section-card">
              <h3>事件类型分布</h3>
              <p class="section-sub">当前视图内的事件计数</p>
              <div class="event-legend">
                ${Object.entries(EVENT_MAP)
                  .map(([key, label]) => {
                    const count = state.auditEvents.filter((event) => event.event_type === key).length;
                    return `<div class="legend-row"><span>${escapeHtml(label)}</span><b>${count}</b></div>`;
                  })
                  .join('')}
              </div>
            </div>
            <div class="section-card">
              <h3>回放说明</h3>
              <p class="section-sub">审计日志为追加写入的 JSONL，重启后仍可查询。选中某条事件可展开原始负载。</p>
              <div class="notice-box">
                ${icon('shield')} 敏感字段未脱敏仅用于本地演示，生产环境需接入数据脱敏与内容审核。
              </div>
            </div>
          </aside>
        </div>
      </div>`;
    renderAuditEvents();
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'audit');
  }
}

function auditTypeOptions() {
  const options = [['all', '全部事件'], ...Object.entries(EVENT_MAP)];
  return options
    .map(
      ([value, label]) =>
        `<option value="${value}" ${state.auditFilter === value ? 'selected' : ''}>${escapeHtml(label)}</option>`
    )
    .join('');
}

function renderAuditEvents() {
  const list = $('#audit-event-list');
  if (!list) return;
  const events = state.auditEvents.filter(
    (event) => state.auditFilter === 'all' || event.event_type === state.auditFilter
  );
  if (!events.length) {
    list.innerHTML = emptyState('pulse', '暂无审计事件', '发起一次对话或办理后，这里会记录完整链路。');
    return;
  }
  list.innerHTML = events
    .map(
      (event) => `
      <details class="event-item">
        <summary>
          <span class="mono event-time">${escapeHtml(formatTime(event.timestamp))}</span>
          <span class="event-chip">${escapeHtml(EVENT_MAP[event.event_type] || event.event_type)}</span>
          <span class="event-summary">${escapeHtml(auditSummary(event))}</span>
          <span class="event-chevron">${icon('chevron')}</span>
        </summary>
        <div class="event-detail">
          <div class="event-meta">
            <span>会话 <b class="mono">${escapeHtml(event.session_id || '—')}</b></span>
            <span>工单 <b class="mono">${escapeHtml(event.workorder_id || '—')}</b></span>
            <span>${escapeHtml(formatDateTime(event.timestamp))}</span>
          </div>
          <pre>${escapeHtml(JSON.stringify(event.payload, null, 2))}</pre>
        </div>
      </details>`
    )
    .join('');
}

function auditSummary(event) {
  const payload = event.payload || {};
  switch (event.event_type) {
    case 'message':
      return `${payload.role === 'user' ? '用户' : '助手'}：${truncate(payload.content, 76)}`;
    case 'intent':
      return `意图 ${payload.intent} · 置信度 ${Number(payload.confidence || 0).toFixed(2)}`;
    case 'retrieval':
      return `检索「${truncate(payload.query, 36)}」 · Top-1 ${Number(payload.top_score || 0).toFixed(2)}`;
    case 'tool_call':
      return `${payload.tool} · ${payload.success ? '成功' : '失败'} · ${payload.latency_ms || 0}ms`;
    case 'node_transition':
      return `${payload.node_name || payload.event || '节点'} · ${payload.outcome || payload.event || ''}`;
    case 'confirmation':
      return `${payload.action === 'confirm' ? '确认提交' : '取消办理'} · ${payload.source || ''}`;
    case 'idempotency':
      return `幂等命中 · ${payload.receipt || payload.idempotency_key || ''}`;
    case 'handoff':
      return `转人工 · ${payload.reason || ''}`;
    case 'evaluation':
      return `评测完成 · Recall@5 ${payload.recall_at_5}`;
    default:
      return truncate(JSON.stringify(payload), 80);
  }
}

/* ============================================================
   页面：知识库
   ============================================================ */

async function renderKnowledgePage() {
  const page = $('#knowledge-page');
  page.innerHTML = loadingPage('正在加载知识库…');
  try {
    if (!state.knowledgeDocs.length) {
      const data = await api('/knowledge/documents');
      state.knowledgeDocs = data.items || [];
      state.knowledgeCategories = data.categories || [];
    }
    const total = state.knowledgeDocs.length;
    const categories = [{ name: '全部', count: total }, ...state.knowledgeCategories];
    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">KNOWLEDGE BASE</span>
            <h1>制度知识库</h1>
            <p>四类校内制度文档，按章节切分为 500–800 字分块；标题、文号、部门写入元数据，供检索与引用溯源。</p>
          </div>
          <div class="head-actions">
            <button type="button" class="ghost-btn" data-refresh-knowledge>${icon('refresh')} 刷新</button>
          </div>
        </div>

        <div class="toolbar">
          <div class="search-field">
            ${icon('search')}
            <input id="knowledge-search" type="search" placeholder="检索制度原文，例如“补办卡工本费”" value="${escapeAttr(state.knowledgeSearch)}" />
          </div>
          ${categories
            .map(
              (category) => `
              <button type="button" class="filter-chip ${state.knowledgeCategory === category.name ? 'is-active' : ''}" data-knowledge-category="${escapeAttr(category.name)}">
                ${escapeHtml(category.name)}<span class="count">${category.count}</span>
              </button>`
            )
            .join('')}
        </div>

        <div id="knowledge-content"></div>
      </div>`;
    updateKnowledgeContent();
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'knowledge');
  }
}

function updateKnowledgeContent() {
  const container = $('#knowledge-content');
  if (!container) return;
  if (state.knowledgeResults) {
    const results = state.knowledgeResults.results || [];
    container.innerHTML = `
      <div class="search-head">
        <span>检索「${escapeHtml(state.knowledgeResults.query)}」</span>
        <span class="mono">归一化：${escapeHtml(state.knowledgeResults.normalized_query)}</span>
        <span class="mono">${results.length} 条 · ${state.knowledgeResults.latency_ms}ms</span>
        <button type="button" class="ghost-btn" data-clear-knowledge-search>清除检索</button>
      </div>
      <div class="search-results">
        ${results.length ? results.map(searchResultHTML).join('') : emptyState('search', '没有召回结果', '换一个说法，或降低关键词的具体程度。')}
      </div>`;
    return;
  }
  const docs = state.knowledgeDocs.filter(
    (doc) => state.knowledgeCategory === '全部' || doc.category === state.knowledgeCategory
  );
  container.innerHTML = docs.length
    ? `<div class="doc-grid">${docs.map(docCardHTML).join('')}</div>`
    : emptyState('book', '暂无文档', '该分类下还没有制度文档。');
}

function docCardHTML(doc) {
  return `
    <button type="button" class="doc-card" data-doc-card="${escapeAttr(doc.id)}">
      <div class="doc-card-top">
        <span class="category-badge cat-${escapeAttr(doc.category)}">${escapeHtml(doc.category)}</span>
        <span class="doc-number">${escapeHtml(doc.doc_number || '')}</span>
      </div>
      <h3>《${escapeHtml(doc.title)}》</h3>
      <p class="doc-summary">${escapeHtml(doc.summary)}</p>
      <div class="doc-meta">
        <span>${icon('book')} ${doc.section_count} 章</span>
        <span>${icon('cpu')} ${doc.chunk_count} 块</span>
        <span>${icon('pulse')} ${doc.char_count} 字</span>
      </div>
    </button>`;
}

function searchResultHTML(result, index) {
  const score = Math.min(1, Math.max(0, Number(result.score) || 0));
  return `
    <div class="search-result">
      <div class="sr-head">
        <span class="sr-rank">${String(index + 1).padStart(2, '0')}</span>
        <div>
          <div class="sr-title">《${escapeHtml(result.doc_title)}》</div>
          <div class="sr-chapter">${escapeHtml(result.chapter)} · ${escapeHtml(result.doc_number || result.category)}</div>
        </div>
        <span class="sr-score">${Math.round(score * 100)}%</span>
        <button type="button" class="doc-link" data-doc="${escapeAttr(result.doc_id)}">查看原文</button>
      </div>
      <p class="sr-content">${escapeHtml(truncate(result.content, 160))}</p>
      <div class="metric-row">
        <span class="metric-chip">vector ${Number(result.vector_score || 0).toFixed(2)}</span>
        <span class="metric-chip">bm25 ${Number(result.keyword_score || 0).toFixed(2)}</span>
        <span class="metric-chip">coverage ${Number(result.coverage || 0).toFixed(2)}</span>
        <span class="metric-chip">fusion ${Number(result.fusion_score || 0).toFixed(4)}</span>
      </div>
    </div>`;
}

async function runKnowledgeSearch(query) {
  state.knowledgeSearch = query;
  if (!query) {
    state.knowledgeResults = null;
    updateKnowledgeContent();
    return;
  }
  try {
    const data = await api(`/knowledge/search?q=${encodeURIComponent(query)}&top_k=8`);
    state.knowledgeResults = data;
    updateKnowledgeContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function openDocDrawer(docId) {
  try {
    const doc = await api(`/knowledge/documents/${docId}`);
    const sections = (doc.sections || [])
      .map(
        (section) => `
        <div class="doc-section">
          <h3>${escapeHtml(section.heading)}</h3>
          ${(section.paragraphs || []).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
        </div>`
      )
      .join('');
    openDrawer(`
      <div class="drawer-head">
        <div>
          <span class="eyebrow">${escapeHtml(doc.category)} · ${escapeHtml(doc.doc_number || '')}</span>
          <h2>《${escapeHtml(doc.title)}》</h2>
          <div class="drawer-meta">
            <span>${escapeHtml(doc.department)}</span>
            <span class="mono">${escapeHtml(doc.published_at)}</span>
          </div>
        </div>
        <button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button>
      </div>
      <div class="drawer-section">
        <p>${escapeHtml(doc.summary)}</p>
        <div class="tag-row">${(doc.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>
      </div>
      ${sections}
    `);
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ============================================================
   页面：评测中心
   ============================================================ */

async function renderEvaluationPage() {
  const page = $('#evaluation-page');
  if (!state.evaluation) {
    try {
      state.evaluation = await api('/evaluation/latest');
    } catch (error) {
      state.evaluation = null;
    }
  }
  const report = state.evaluation;
  if (!report) {
    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">EVALUATION</span>
            <h1>评测中心</h1>
            <p>用内置的 25 条检索冒烟集计算 Recall@5、MRR@5 与时延，对应项目说明书中的知识库检索验证项。</p>
          </div>
        </div>
        <div class="section-card">
          ${emptyState('chart', '还没有评测结果', '运行一次离线评测，查看四类知识库的召回表现。')}
          <div class="empty-actions">
            <button type="button" class="primary-btn" data-run-evaluation>${icon('chart')} 运行评测</button>
          </div>
        </div>
        ${extendedEvaluationHTML()}
      </div>`;
    return;
  }

  const recallTarget = 0.85;
  const mrrTarget = 0.7;
  const categories = Object.entries(report.by_category || {});
  const details = report.details || [];

  page.innerHTML = `
    <div class="page-inner">
      <div class="page-head">
        <div>
          <span class="eyebrow">EVALUATION</span>
          <h1>评测中心</h1>
          <p>检索冒烟集覆盖规章、教务、学工、图书馆四类文档；指标口径与项目说明书一致。</p>
        </div>
        <div class="head-actions">
          <button type="button" class="primary-btn" data-run-evaluation>${icon('refresh')} 重新运行</button>
        </div>
      </div>

      <div class="kpi-grid">
        ${kpiCard('Recall@5', percent(report.recall_at_5), `目标 ≥ ${percent(recallTarget, 0)}`, report.recall_at_5 >= recallTarget)}
        ${kpiCard('MRR@5', percent(report.mrr_at_5), `目标 ≥ ${percent(mrrTarget, 0)}`, report.mrr_at_5 >= mrrTarget)}
        ${kpiCard('平均检索时延', `${report.avg_latency_ms.toFixed(1)}<small>ms</small>`, `P95 ${report.p95_latency_ms.toFixed(1)} ms`, true)}
        ${kpiCard('评测集规模', String(report.dataset_size), '条查询', true)}
      </div>

      <div class="grid-2">
        <div class="section-card">
          <div class="section-head">
            <div>
              <h3>分类召回表现</h3>
              <p class="section-sub">Recall@5 / MRR@5 · 运行 ID ${escapeHtml(report.run_id)}</p>
            </div>
          </div>
          <div class="bar-chart">
            ${categories
              .map(
                ([name, item]) => `
                <div class="bar-item">
                  <span class="bar-label">${escapeHtml(name)}</span>
                  <div class="bar-track"><div class="bar-fill" style="width:${Math.round((item.recall_at_5 || 0) * 100)}%"></div></div>
                  <span class="bar-value">${percent(item.recall_at_5)}</span>
                </div>`
              )
              .join('')}
          </div>
          <div class="eval-note">
            ${icon('shield')} 评测为确定性检索指标：命中标准文档进入 Top-5 记为正确；低置信度问题会触发改写后重排。
          </div>
        </div>

        <div class="section-card">
          <h3>评测说明</h3>
          <p class="section-sub">与项目材料的对应关系</p>
          <div class="eval-points">
            <div><b>Recall@5 ≥ 0.85</b><span>标准答案所在文档进入前 5 的比例</span></div>
            <div><b>MRR@5 ≥ 0.70</b><span>首个相关文档排名倒数的均值</span></div>
            <div><b>引用支持率 ≥ 90%</b><span>由回答 Agent 的引用校验环节保证</span></div>
            <div><b>P95 时延 ≤ 8s</b><span>本地 Mock 模型下稳定低于目标</span></div>
          </div>
          <div class="notice-box">
            ${icon('alert')} 当前为离线检索评测，不调用真实大模型；答案正确率与人工盲测需在接入真实模型后补充。
          </div>
        </div>
      </div>

      <div class="section-card eval-details">
        <div class="section-head">
          <div>
            <h3>逐题结果</h3>
            <p class="section-sub">标准文档、Top-5 召回与排名</p>
          </div>
        </div>
        <div class="table-scroll">
          <table class="result-table">
            <thead>
              <tr><th>查询</th><th>类别</th><th>标准文档</th><th>Top 文档</th><th>排名</th><th>时延</th></tr>
            </thead>
            <tbody>
              ${details
                .map(
                  (item) => `
                  <tr>
                    <td>${escapeHtml(item.query)}</td>
                    <td>${escapeHtml(item.category)}</td>
                    <td class="mono">${escapeHtml(item.expected_doc_id)}</td>
                    <td class="mono">${escapeHtml([...new Set(item.retrieved_doc_ids || [])].slice(0, 2).join(', ') || '—')}</td>
                    <td><span class="hit-badge ${item.hit ? 'ok' : 'miss'}">${item.hit ? '✓' : '×'}</span> ${item.rank ? `#${item.rank}` : '—'}</td>
                    <td class="mono">${item.latency_ms}ms</td>
                  </tr>`
                )
                .join('')}
            </tbody>
          </table>
        </div>
      </div>

      ${extendedEvaluationHTML()}
    </div>`;
}

function extendedEvaluationHTML() {
  const results = state.extendedEval || {};
  const retrieval = results.retrieval;
  const generation = results.generation;
  const task = results.task;
  return `
    <div class="section-card eval-details">
      <div class="section-head">
        <div>
          <h3>扩展评测：300 条 silver + 20 条任务</h3>
          <p class="section-sub">检索、引用/拒答、办事任务三层分开报告；数字带样本量，不把检索命中说成答案正确率。</p>
        </div>
        <span class="badge-soft">silver</span>
      </div>
      <div class="toolbar">
        <button type="button" class="primary-btn" data-run-extended="retrieval" ${state.extendedLoading.retrieval ? 'disabled' : ''}>${icon('search')} 运行检索 300</button>
        <button type="button" class="ghost-btn" data-run-extended="generation" ${state.extendedLoading.generation ? 'disabled' : ''}>${icon('shield')} 运行引用/拒答</button>
        <button type="button" class="ghost-btn" data-run-extended="task" ${state.extendedLoading.task ? 'disabled' : ''}>${icon('ticket')} 运行任务 20</button>
      </div>
      <div class="notice-box">
        ${icon('alert')} 这是 silver 集：240 条同义改写 + 60 条越界，不是人工金标；MockLLM 下生成指标只做回归，不代表真实模型能力。
      </div>
      <div class="grid-3">
        <div class="mini-eval-panel">
          <span class="eyebrow">RETRIEVAL · 300</span>
          ${retrieval
            ? `<div class="mini-eval-row"><b>${percent(retrieval.recall_at_5)}</b><span>Recall@5 · 95% CI ${percent(retrieval.recall_at_5_ci[0])}–${percent(retrieval.recall_at_5_ci[1])}</span></div>
               <div class="mini-eval-row"><b>${percent(retrieval.mrr_at_5)}</b><span>MRR@5 · nDCG ${percent(retrieval.ndcg_at_5)}</span></div>
               <div class="mini-eval-row"><b>${percent(retrieval.hard_negative_fpr)}</b><span>Hard-negative FPR · 越界误答 ${percent(retrieval.negative_answer_rate)}</span></div>
               <div class="mini-eval-row muted">n=${retrieval.answerable_n} 可答 + ${retrieval.unanswerable_n} 越界</div>`
            : '<p class="section-sub">尚未运行。</p>'}
        </div>
        <div class="mini-eval-panel">
          <span class="eyebrow">CITATION · 120</span>
          ${generation
            ? `<div class="mini-eval-row"><b>${percent(generation.citation_presence_rate)}</b><span>引用存在率 · 文档命中 ${percent(generation.citation_gold_hit_rate)}</span></div>
               <div class="mini-eval-row"><b>${percent(generation.refusal_accuracy)}</b><span>拒答准确率 · 误答 ${percent(generation.false_answer_rate)}</span></div>
               <div class="mini-eval-row"><b>${percent(generation.false_refusal_rate)}</b><span>该答未答率 · 平均引用 ${generation.avg_citations}</span></div>
               <div class="mini-eval-row muted">${generation.mode} · n=${generation.answerable_n}+${generation.unanswerable_n}</div>`
            : '<p class="section-sub">尚未运行。</p>'}
        </div>
        <div class="mini-eval-panel">
          <span class="eyebrow">TASK · 20</span>
          ${task
            ? `<div class="mini-eval-row"><b>${percent(task.success_rate)}</b><span>任务成功率 · 95% CI ${percent(task.success_rate_ci[0])}–${percent(task.success_rate_ci[1])}</span></div>
               <div class="mini-eval-row"><b>${task.avg_turns}</b><span>平均轮次 · 转人工 ${percent(task.handoff_rate)}</span></div>
               <div class="mini-eval-row"><b>${task.duplicate_new_orders}</b><span>重复提交新增工单 · ${task.passed}/${task.n}</span></div>
               <div class="mini-eval-row muted">独立临时数据目录 · Mock 业务系统</div>`
            : '<p class="section-sub">尚未运行。</p>'}
        </div>
      </div>
    </div>`;
}

async function runExtendedEvaluation(suite, button) {
  if (state.extendedLoading[suite]) return;
  state.extendedLoading[suite] = true;
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span> 运行中…`;
  }
  try {
    const data = await api(`/evaluation/extended/run?suite=${suite}&split=test`, {
      method: 'POST',
    });
    state.extendedEval[suite] = data;
    toast('扩展评测完成');
    await renderEvaluationPage();
  } catch (error) {
    toast(error.message, 'error');
    if (button) {
      button.disabled = false;
      button.innerHTML = '重试';
    }
  } finally {
    state.extendedLoading[suite] = false;
  }
}

function kpiCard(label, value, goal, ok) {
  return `
    <div class="kpi-card">
      <div class="kpi-top">
        <span>${escapeHtml(label)}</span>
        <span class="kpi-badge ${ok ? '' : 'warn'}">${ok ? '达标' : '待优化'}</span>
      </div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-goal">${escapeHtml(goal)}</div>
    </div>`;
}

async function runEvaluation(button) {
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span> 评测运行中…`;
  }
  try {
    const report = await api('/evaluation/run', { method: 'POST' });
    state.evaluation = report;
    await renderEvaluationPage();
    toast('评测完成');
  } catch (error) {
    toast(error.message, 'error');
    if (button) {
      button.disabled = false;
      button.innerHTML = `${icon('chart')} 运行评测`;
    }
  }
}

/* ============================================================
   页面：学生库
   ============================================================ */

const STUDENT_STATUS = {
  active: { label: '在籍', cls: 'completed' },
  missing_id: { label: '待补学号', cls: 'failed' },
  retained: { label: '保留资格', cls: 'transferred_human' },
  retaking: { label: '复读', cls: 'draft' },
  not_arrived: { label: '未报到', cls: 'failed' },
};

async function renderStudentsPage() {
  const page = $('#students-page');
  if (!page) return;
  if (state.studentLoading) return;
  state.studentLoading = true;
  page.innerHTML = loadingPage('正在读取学生库…');
  try {
    const stats = await api('/students/stats');
    state.studentStats = stats;
    const filters = state.studentFilters;
    const params = new URLSearchParams({
      limit: String(state.studentLimit),
      offset: String(state.studentOffset),
    });
    if (filters.college) params.set('college', filters.college);
    if (filters.cohort) params.set('cohort', filters.cohort);
    if (filters.major) params.set('major', filters.major);
    if (filters.status) params.set('status', filters.status);
    if (filters.query) params.set('q', filters.query);
    const list = await api(`/students?${params.toString()}`);
    state.students = list.items || [];
    state.studentTotal = list.total || 0;

    const latest = stats.latest_batch || {};
    const batchText = latest.batch_id
      ? `${latest.batch_id} · ${formatDateTime(latest.imported_at)} · ${latest.inserted + latest.updated} 条`
      : '尚未导入';
    const start = state.studentTotal ? state.studentOffset + 1 : 0;
    const end = Math.min(state.studentOffset + state.studentLimit, state.studentTotal);
    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">STUDENT REGISTRY</span>
            <h1>学生库</h1>
            <p>按“学院 + 届”持久化的学生名册；补办流程会读取这里的姓名、专业与班级，手机号默认脱敏。</p>
          </div>
          <div class="head-actions">
            <button type="button" class="ghost-btn" data-refresh-students>${icon('refresh')} 刷新</button>
          </div>
        </div>

        <div class="overview-grid">
          ${miniStat('学生总数', stats.total)}
          ${miniStat('学院数', stats.colleges)}
          ${miniStat('届数', stats.cohorts)}
          ${miniStat('班级数', stats.classes)}
          ${miniStat('专业数', stats.majors)}
          ${miniStat('需关注', stats.issues)}
        </div>

        <div class="toolbar student-toolbar">
          <div class="search-field">
            ${icon('search')}
            <input id="student-search" type="search" placeholder="搜学号 / 姓名 / 班级" value="${escapeAttr(filters.query)}" />
          </div>
          <select class="select-input" id="student-college-filter" aria-label="按学院筛选">
            <option value="">全部学院</option>
            ${(stats.by_college || []).map((item) => `<option value="${escapeAttr(item.name)}" ${filters.college === item.name ? 'selected' : ''}>${escapeHtml(item.name)} (${item.count})</option>`).join('')}
          </select>
          <select class="select-input" id="student-cohort-filter" aria-label="按届筛选">
            <option value="">全部届别</option>
            ${(stats.by_cohort || []).map((item) => `<option value="${escapeAttr(item.name)}" ${filters.cohort === item.name ? 'selected' : ''}>${escapeHtml(item.name)} 届 (${item.count})</option>`).join('')}
          </select>
          <select class="select-input" id="student-major-filter" aria-label="按专业筛选">
            <option value="">全部专业</option>
            ${(stats.by_major || []).map((item) => `<option value="${escapeAttr(item.name)}" ${filters.major === item.name ? 'selected' : ''}>${escapeHtml(item.name)} (${item.count})</option>`).join('')}
          </select>
          <select class="select-input" id="student-status-filter" aria-label="按状态筛选">
            <option value="">全部状态</option>
            ${(stats.by_status || []).map((item) => `<option value="${escapeAttr(item.name)}" ${filters.status === item.name ? 'selected' : ''}>${escapeHtml(item.label || item.name)} (${item.count})</option>`).join('')}
          </select>
          <button type="button" class="primary-btn" data-student-search>${icon('search')} 查询</button>
        </div>

        <div class="section-card">
          <div class="section-head">
            <div>
              <h3>学生名册</h3>
              <p class="section-sub">当前显示第 ${start}–${end} 条，共 ${state.studentTotal} 条 · 最近导入：${escapeHtml(batchText)}</p>
            </div>
            <span class="badge-soft">${state.studentTotal} 条</span>
          </div>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>学号</th><th>姓名</th><th>学院 / 专业</th><th>班级</th><th>届</th><th>状态</th><th>手机号</th></tr></thead>
              <tbody>
                ${state.students.map(studentRowHTML).join('') || `<tr><td colspan="7">${emptyState('users', '没有匹配的学生', '换一个筛选条件，或导入新的学院/届。')}</td></tr>`}
              </tbody>
            </table>
          </div>
          <div class="student-pager">
            <span>共 ${state.studentTotal} 条</span>
            <div>
              <button type="button" class="ghost-btn" data-student-page="prev" ${state.studentOffset <= 0 ? 'disabled' : ''}>上一页</button>
              <button type="button" class="ghost-btn" data-student-page="next" ${end >= state.studentTotal ? 'disabled' : ''}>下一页</button>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div class="section-card">
            <h3>继续导入其他学院 / 届</h3>
            <p class="section-sub">同一套命令，换文件、届别和学院即可；按“学院 + 届 + 学号”更新，不会重复。</p>
            <pre class="json-block">python scripts/import_students.py --file path/to/students.xlsx --cohort 2026 --college 商学院</pre>
            <div class="notice-box">${icon('shield')} 支持 xlsx / csv；原始手机号只保存在 registry/students.db，页面与 API 只返回脱敏值。</div>
          </div>
          <div class="section-card">
            <h3>数据来源</h3>
            <p class="section-sub">最近一次导入批次</p>
            <div class="detail-list">
              <div><span>批次</span><b>${escapeHtml(latest.batch_id || '—')}</b></div>
              <div><span>学院 / 届</span><b>${escapeHtml(latest.college || '—')} / ${escapeHtml(latest.cohort || '—')}</b></div>
              <div><span>新增 / 更新</span><b>${latest.inserted ?? 0} / ${latest.updated ?? 0}</b></div>
              <div><span>跳过 / 需关注</span><b>${latest.skipped ?? 0} / ${latest.issues ?? 0}</b></div>
              <div><span>原始文件</span><b>${escapeHtml(latest.source_file || '—')}</b></div>
            </div>
          </div>
        </div>
      </div>`;
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'students');
  } finally {
    state.studentLoading = false;
  }
}

function studentRowHTML(student) {
  const status = STUDENT_STATUS[student.status] || { label: student.status, cls: 'draft' };
  return `
    <tr>
      <td class="mono">${escapeHtml(student.student_id || '待补')}</td>
      <td>${escapeHtml(student.name)}</td>
      <td>${escapeHtml(student.college)}<br /><span class="cell-sub">${escapeHtml(student.major || '—')}</span></td>
      <td>${escapeHtml(student.class_name || '—')}</td>
      <td>${escapeHtml(student.cohort || '—')}</td>
      <td><span class="status-pill status-${escapeAttr(status.cls)}">${escapeHtml(status.label)}</span></td>
      <td class="mono">${escapeHtml(student.phone_masked || '—')}</td>
    </tr>`;
}

function readStudentFilters() {
  state.studentFilters = {
    college: $('#student-college-filter')?.value || '',
    cohort: $('#student-cohort-filter')?.value || '',
    major: $('#student-major-filter')?.value || '',
    status: $('#student-status-filter')?.value || '',
    query: $('#student-search')?.value.trim() || '',
  };
  state.studentOffset = 0;
}

/* ============================================================
   页面：系统状态
   ============================================================ */

async function renderSystemPage() {
  const page = $('#system-page');
  page.innerHTML = loadingPage('正在读取系统状态…');
  try {
    const data = await api('/system/overview');
    state.overview = data;
    const health = data.health || {};
    const workflow = data.workflow || {};
    const nodes = workflow.nodes || [];
    const tools = data.tools || [];
    const students = data.students || [];
    const registry = data.student_registry || {};
    const integration = data.integration || {};
    page.innerHTML = `
      <div class="page-inner">
        <div class="page-head">
          <div>
            <span class="eyebrow">SYSTEM</span>
            <h1>系统状态</h1>
            <p>双 Agent、工具注册表、工作流定义与模拟业务数据的运行总览。</p>
          </div>
          <div class="head-actions">
            <button type="button" class="ghost-btn" data-refresh-system>${icon('refresh')} 刷新</button>
          </div>
        </div>

        <div class="overview-grid">
          ${miniStat('运行时长', formatUptime(health.uptime_seconds))}
          ${miniStat('知识文档', health.knowledge_documents)}
          ${miniStat('知识分块', health.knowledge_chunks)}
          ${miniStat('会话数', health.sessions)}
          ${miniStat('工单数', health.workorders)}
          ${miniStat('审计事件', data.audit_count)}
          ${miniStat('工具数', tools.length)}
          ${miniStat('模型', (health.llm_model || 'Mock').replace(' · Mock', ''))}
          ${miniStat('接口模式', (integration.mode || 'mock').toUpperCase())}
        </div>

        <div class="grid-2">
          <div class="section-card">
            <div class="section-head">
              <div>
                <h3>工具注册表</h3>
                <p class="section-sub">MCP 风格的校园业务工具，由注册表统一超时与兜底</p>
              </div>
              <span class="badge-soft">${tools.length} 个</span>
            </div>
            <div class="tool-grid">
              ${tools
                .map(
                  (tool) => `
                  <div class="tool-card">
                    <code>${escapeHtml(tool.name)}</code>
                    <p>${escapeHtml(tool.description)}</p>
                    <span class="tool-tag">${escapeHtml(tool.category)} · ${tool.timeout_seconds}s</span>
                  </div>`
                )
                .join('')}
            </div>
          </div>

          <div class="section-card">
            <div class="section-head">
              <div>
                <h3>校园卡补办工作流</h3>
                <p class="section-sub">${escapeHtml(workflow.name || '')} · ${nodes.length} 个节点 · ${(workflow.edges || []).length} 条边</p>
              </div>
            </div>
            <div class="workflow-map">
              ${nodes
                .map(
                  (node, index) => `
                  <div class="node-chip">
                    <span class="node-index">${String(index + 1).padStart(2, '0')}</span>
                    <span>${escapeHtml(node.name)}</span>
                    <span class="node-type">${escapeHtml(node.node_type)}</span>
                  </div>
                  ${node.description ? `<div class="node-desc">${escapeHtml(node.description)}</div>` : ''}`
                )
                .join('')}
            </div>
          </div>
        </div>

        <div class="section-card system-block">
          <div class="section-head">
            <div>
              <h3>学生库</h3>
              <p class="section-sub">按“学院 + 届”持久化，独立于可重置的演示数据；补办流程会读取这里的学籍信息</p>
            </div>
            <a class="ghost-btn" href="#/students">${icon('users')} 打开学生库</a>
          </div>
          <div class="overview-grid">
            ${miniStat('学生总数', registry.total ?? 0)}
            ${miniStat('学院数', registry.colleges ?? 0)}
            ${miniStat('届数', registry.cohorts ?? 0)}
            ${miniStat('班级数', registry.classes ?? 0)}
            ${miniStat('需关注', registry.issues ?? 0)}
            ${miniStat('最近导入', registry.latest_batch?.batch_id ? '有' : '无')}
          </div>
        </div>

        <div class="section-card system-block">
          <div class="section-head">
            <div>
              <h3>演示样例数据</h3>
              <p class="section-sub">20 个内置演示样例，包含挂失、欠费与故障注入学号 2025000999；真实名册在「学生库」单独维护</p>
            </div>
            <span class="badge-soft">${students.length} 条</span>
          </div>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>学号</th><th>姓名</th><th>学院</th><th>校区</th><th>校园卡</th><th>余额</th></tr></thead>
              <tbody>
                ${students
                  .map(
                    (student) => `
                    <tr>
                      <td class="mono">${escapeHtml(student.student_id)}</td>
                      <td>${escapeHtml(student.name)}</td>
                      <td>${escapeHtml(student.college)}</td>
                      <td>${escapeHtml(student.campus)}</td>
                      <td>${student.card_lost ? '<span class="status-pill status-failed">已挂失</span>' : '<span class="status-pill status-completed">正常</span>'}</td>
                      <td class="mono ${student.balance < 0 ? 'text-danger' : ''}">${student.balance.toFixed(2)}</td>
                    </tr>`
                  )
                  .join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-2 system-block">
          <div class="section-card">
            <h3>检索参数</h3>
            <p class="section-sub">阈值与分块配置（config.py）</p>
            <pre class="json-block">${escapeHtml(JSON.stringify(data.retrieval, null, 2))}</pre>
          </div>
          <div class="section-card">
            <h3>最近审计</h3>
            <p class="section-sub">最新 10 条事件</p>
            <div class="mini-audit">
              ${(data.recent_audit || [])
                .slice(0, 10)
                .map(
                  (event) => `
                  <div class="mini-audit-row">
                    <span class="mono">${escapeHtml(formatTime(event.timestamp))}</span>
                    <span class="event-chip">${escapeHtml(EVENT_MAP[event.event_type] || event.event_type)}</span>
                    <span>${escapeHtml(auditSummary(event))}</span>
                  </div>`
                )
                .join('')}
            </div>
          </div>
        </div>
      </div>`;
  } catch (error) {
    page.innerHTML = errorPage(error.message, 'system');
  }
}

function miniStat(label, value) {
  return `<div class="mini-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

/* ============================================================
   通用页面片段
   ============================================================ */

function loadingPage(text) {
  return `
    <div class="page-inner">
      <div class="loading-block">
        <span class="eyebrow">${escapeHtml(text)}</span>
        <div class="skeleton" style="width:46%"></div>
        <div class="skeleton" style="width:72%"></div>
        <div class="skeleton" style="width:58%"></div>
        <div class="skeleton" style="width:84%;height:120px"></div>
      </div>
    </div>`;
}

function errorPage(message, route) {
  return `
    <div class="page-inner">
      <div class="empty-state">
        <span class="empty-icon">${icon('alert')}</span>
        <h3>加载失败</h3>
        <p>${escapeHtml(message || '网络异常，请稍后重试')}</p>
        <button type="button" class="primary-btn" data-page-retry="${escapeAttr(route)}">重新加载</button>
      </div>
    </div>`;
}

function emptyState(iconName, title, description) {
  return `
    <div class="empty-state">
      <span class="empty-icon">${icon(iconName)}</span>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(description)}</p>
    </div>`;
}

/* ============================================================
   抽屉与剪贴板
   ============================================================ */

function openDrawer(html) {
  $('#drawer-root').innerHTML = `
    <div class="drawer">
      <div class="drawer-backdrop" data-close-drawer></div>
      <aside class="drawer-panel" role="dialog" aria-modal="true">${html}</aside>
    </div>`;
}

function closeDrawer() {
  $('#drawer-root').innerHTML = '';
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('已复制到剪贴板');
  } catch (error) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      toast('已复制到剪贴板');
    } catch (fallbackError) {
      toast('复制失败，请手动选择', 'error');
    }
    textarea.remove();
  }
}

/* ============================================================
   事件委托
   ============================================================ */

async function handleDocumentClick(event) {
  const target = event.target;

  const lostFoundOpen = target.closest('[data-lostfound-open]');
  if (lostFoundOpen) {
    event.preventDefault();
    openLostFoundForm(lostFoundOpen.dataset.lostfoundOpen);
    return;
  }
  const lostFoundKind = target.closest('[data-lostfound-kind]');
  if (lostFoundKind) {
    event.preventDefault();
    state.lostFoundKind = lostFoundKind.dataset.lostfoundKind;
    await renderLostFoundPage();
    return;
  }
  const lostFoundSearch = target.closest('[data-lostfound-search]');
  if (lostFoundSearch) {
    event.preventDefault();
    state.lostFoundQuery = $('#lostfound-search')?.value.trim() || '';
    await renderLostFoundPage();
    return;
  }
  const lostFoundClose = target.closest('[data-lostfound-close]');
  if (lostFoundClose) {
    event.preventDefault();
    await closeLostFound(lostFoundClose.dataset.lostfoundClose);
    return;
  }
  const lostFoundSubmit = target.closest('[data-lostfound-submit]');
  if (lostFoundSubmit) {
    event.preventDefault();
    await submitLostFound(lostFoundSubmit.dataset.lostfoundSubmit);
    return;
  }
  const feedbackSubmit = target.closest('[data-feedback-submit]');
  if (feedbackSubmit) {
    event.preventDefault();
    await submitFeedback();
    return;
  }

  const navChip = target.closest('[data-nav-mode][data-nav-section]');
  if (navChip) {
    event.preventDefault();
    if (navChip.dataset.navMode === 'learning') {
      navigateLearningSection(navChip.dataset.navSection);
    } else {
      navigateCampusSection(navChip.dataset.navSection);
    }
    return;
  }

  const campusAction = target.closest('[data-campus-action="notifications"]');
  if (campusAction) {
    event.preventDefault();
    await navigate('campus', { push: false });
    $('#notifications-btn')?.click();
    return;
  }

  const campusSection = target.closest('[data-campus-section]');
  if (campusSection) {
    event.preventDefault();
    navigateCampusSection(campusSection.dataset.campusSection);
    return;
  }

  const learningNav = target.closest('[data-nav-learning]');
  if (learningNav) {
    event.preventDefault();
    navigateLearningSection(learningNav.dataset.navLearning);
    return;
  }

  const chatNav = target.closest('[data-nav-chat]');
  if (chatNav) {
    event.preventDefault();
    await navigate('chat', { push: false });
    setHash(state.mode === 'learning' ? '#/learning/chat' : '#/campus/chat');
    return;
  }

  const navAction = target.closest('[data-nav-action]');
  if (navAction) {
    event.preventDefault();
    navigateCampusSection(navAction.dataset.navSection);
    return;
  }

  if (!target.closest('#sidebar-user')) {
    closeProfileMenu();
  }
  if (!target.closest('#notification-wrap')) {
    const menu = $('#notifications-menu');
    if (menu) menu.hidden = true;
  }
  const notification = target.closest('.notification-item');
  if (notification) {
    await openNotification(notification);
    return;
  }

  const profileAction = target.closest('[data-profile-action]');
  if (profileAction) {
    const action = profileAction.dataset.profileAction;
    if (action === 'view') openProfileDrawer();
    if (action === 'switch') switchAccount();
    if (action === 'logout') {
      closeDrawer();
      closeProfileMenu();
      logout();
    }
    return;
  }

  const returnLeave = target.closest('[data-return-leave]');
  if (returnLeave) {
    await returnFromLeave(returnLeave.dataset.returnLeave);
    return;
  }

  const withdraw = target.closest('[data-withdraw-leave]');
  if (withdraw) {
    await withdrawLeave(withdraw.dataset.withdrawLeave);
    return;
  }

  const sessionDelete = target.closest('[data-delete-session]');
  if (sessionDelete) {
    event.stopPropagation();
    await deleteSession(sessionDelete.dataset.deleteSession);
    return;
  }

  const sessionItem = target.closest('[data-session-id]');
  if (sessionItem && !target.closest('[data-delete-session]')) {
    await selectSession(sessionItem.dataset.sessionId);
    return;
  }

  const suggest = target.closest('[data-suggest]');
  if (suggest) {
    await sendMessage(suggest.dataset.suggest);
    return;
  }

  const cite = target.closest('.cite-mark');
  if (cite) {
    const article = cite.closest('.message');
    const index = cite.dataset.cite;
    const details = article?.querySelector('.citations');
    if (details) details.open = true;
    const card = article?.querySelector(`.citation-card[data-cite="${index}"]`);
    if (card) {
      card.classList.add('is-flash');
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => card.classList.remove('is-flash'), 1400);
    }
    return;
  }

  const action = target.closest('.action-chip');
  if (action) {
    await handleAction(action.dataset.action);
    return;
  }

  const confirmButton = target.closest('[data-confirm-action]');
  if (confirmButton) {
    await handleConfirm(confirmButton.dataset.confirmAction, confirmButton);
    return;
  }

  const copyButton = target.closest('[data-copy]');
  if (copyButton) {
    await copyText(copyButton.dataset.copy);
    return;
  }

  const docButton = target.closest('[data-doc]');
  if (docButton) {
    await openDocDrawer(docButton.dataset.doc);
    return;
  }

  const docCard = target.closest('[data-doc-card]');
  if (docCard) {
    await openDocDrawer(docCard.dataset.docCard);
    return;
  }

  const openWorkorder = target.closest('[data-open-workorder]');
  if (openWorkorder) {
    await openWorkorderDrawer(openWorkorder.dataset.openWorkorder);
    return;
  }

  const workorderRow = target.closest('[data-workorder-row]');
  if (workorderRow) {
    await openWorkorderDrawer(workorderRow.dataset.workorderRow);
    return;
  }

  const workorderFilter = target.closest('[data-wo-filter]');
  if (workorderFilter) {
    state.workorderFilter = workorderFilter.dataset.woFilter;
    $$('[data-wo-filter]').forEach((chip) =>
      chip.classList.toggle('is-active', chip.dataset.woFilter === state.workorderFilter)
    );
    renderWorkorderTable();
    return;
  }

  const knowledgeCategory = target.closest('[data-knowledge-category]');
  if (knowledgeCategory) {
    state.knowledgeCategory = knowledgeCategory.dataset.knowledgeCategory;
    state.knowledgeResults = null;
    state.knowledgeSearch = '';
    const input = $('#knowledge-search');
    if (input) input.value = '';
    $$('[data-knowledge-category]').forEach((chip) =>
      chip.classList.toggle('is-active', chip.dataset.knowledgeCategory === state.knowledgeCategory)
    );
    updateKnowledgeContent();
    return;
  }

  const clearSearch = target.closest('[data-clear-knowledge-search]');
  if (clearSearch) {
    state.knowledgeResults = null;
    state.knowledgeSearch = '';
    const input = $('#knowledge-search');
    if (input) input.value = '';
    updateKnowledgeContent();
    return;
  }

  const runEval = target.closest('[data-run-evaluation]');
  if (runEval) {
    await runEvaluation(runEval);
    return;
  }

  const runExtended = target.closest('[data-run-extended]');
  if (runExtended) {
    await runExtendedEvaluation(runExtended.dataset.runExtended, runExtended);
    return;
  }

  const pageRetry = target.closest('[data-page-retry]');
  if (pageRetry) {
    await navigate(pageRetry.dataset.pageRetry);
    return;
  }

  const refreshWorkorders = target.closest('[data-refresh-workorders]');
  if (refreshWorkorders) {
    await renderWorkordersPage();
    return;
  }

  const refreshAudit = target.closest('[data-refresh-audit]');
  if (refreshAudit) {
    await renderAuditPage();
    return;
  }

  const refreshKnowledge = target.closest('[data-refresh-knowledge]');
  if (refreshKnowledge) {
    state.knowledgeDocs = [];
    state.knowledgeResults = null;
    await renderKnowledgePage();
    return;
  }

  if (target.closest('[data-refresh-students]')) {
    await renderStudentsPage();
    return;
  }

  if (target.closest('[data-student-search]')) {
    readStudentFilters();
    await renderStudentsPage();
    return;
  }

  const studentPage = target.closest('[data-student-page]');
  if (studentPage) {
    const direction = studentPage.dataset.studentPage;
    state.studentOffset = Math.max(
      0,
      state.studentOffset + (direction === 'next' ? state.studentLimit : -state.studentLimit)
    );
    await renderStudentsPage();
    return;
  }

  const refreshSystem = target.closest('[data-refresh-system]');
  if (refreshSystem) {
    await renderSystemPage();
    return;
  }

  const retrySend = target.closest('[data-retry-send]');
  if (retrySend) {
    retrySend.closest('.message')?.remove();
    await sendMessage(retrySend.dataset.retrySend, { retry: true });
    return;
  }

  if (target.closest('[data-close-drawer]')) {
    closeDrawer();
  }
}

async function handleDocumentChange(event) {
  if (event.target.id === 'lostfound-campus') {
    state.lostFoundCampus = event.target.value;
    await renderLostFoundPage();
    return;
  }
  if (
    ['student-college-filter', 'student-cohort-filter', 'student-major-filter', 'student-status-filter'].includes(
      event.target.id
    )
  ) {
    readStudentFilters();
    await renderStudentsPage();
    return;
  }
  if (event.target.id === 'audit-type-filter') {
    state.auditFilter = event.target.value;
    renderAuditEvents();
    return;
  }
  if (event.target.id === 'audit-session-select') {
    const sessionId = event.target.value;
    state.auditSessionId = sessionId;
    if (!sessionId) {
      const data = await api('/audit/recent?limit=120');
      state.auditEvents = data.items || [];
      renderAuditEvents();
      return;
    }
    try {
      const data = await api(`/sessions/${sessionId}/audit?limit=300`);
      state.auditEvents = data.items || [];
      renderAuditEvents();
      toast(`已加载该会话的 ${state.auditEvents.length} 条审计事件`);
    } catch (error) {
      toast(error.message, 'error');
    }
  }
}
