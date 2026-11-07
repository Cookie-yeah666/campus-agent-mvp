/* 学习空间：专注计时、AI 任务清单、错题本、日历与课程表 */

const learningState = {
  tab: 'focus',
  overview: null,
  tasks: [],
  libraries: [],
  activeLibraryId: '',
  questions: [],
  trashQuestions: [],
  reviewQuestions: [],
  reviewSummary: null,
  report: null,
  parsed: [],
  parseMode: 'rule',
  assignmentDrafts: [],
  assignmentImage: '',
  imageData: '',
  timer: null,
  timerHandle: null,
  calendar: null,
  calendarYear: new Date().getFullYear(),
  calendarMonth: new Date().getMonth() + 1,
  calendarMode: 'courses',
  calendarView: 'month',
  calendarWeek: null,
  weekStartDate: '',
  calendarSettings: null,
  semesterStart: '',
  pomodoro: null,
  pomodoroDone: 0,
  recognitionTokens: 16384,
  courses: [],
  examRoom: null,
  reminded: new Set(),
  reminderHandle: null,
};

const CALENDAR_SETTINGS_KEY = 'zhixing-calendar-settings';

function defaultCalendarSettings() {
  return {
    view: 'month',
    weekStart: 'monday',
    showWeekends: true,
    showTime: true,
    showGrid: true,
    showOffWeek: false,
    cellHeight: 126,
    radius: 12,
    opacity: 1,
    textColor: '#26364a',
    borderColor: '#d7e0e8',
  };
}

function loadCalendarSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(CALENDAR_SETTINGS_KEY) || '{}');
    return { ...defaultCalendarSettings(), ...saved };
  } catch (error) {
    return defaultCalendarSettings();
  }
}

function todayISO() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function startOfWeekISO(iso, weekStart = 'monday') {
  const target = new Date(`${iso}T00:00:00`);
  const day = target.getDay(); // 0=Sun
  const offset = weekStart === 'sunday' ? day : (day + 6) % 7;
  target.setDate(target.getDate() - offset);
  return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
}

function addDaysISO(iso, days) {
  const target = new Date(`${iso}T00:00:00`);
  target.setDate(target.getDate() + days);
  return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
}

const POMODORO_KEY = 'zhixing-pomodoro-settings';
const POMODORO_STATS_KEY = 'zhixing-pomodoro-stats';

function defaultPomodoro() {
  return {
    focusMin: 25,
    shortMin: 5,
    longMin: 15,
    roundsBeforeLong: 4,
    round: 1,
    done: 0,
    mode: 'focus',
    autoNext: false,
    sound: true,
  };
}

function loadPomodoro() {
  try {
    const saved = JSON.parse(localStorage.getItem(POMODORO_KEY) || '{}');
    const settings = { ...defaultPomodoro(), ...saved };
    const stats = JSON.parse(localStorage.getItem(POMODORO_STATS_KEY) || '{}');
    if (stats.date === todayISO()) {
      settings.done = Number(stats.done) || 0;
    }
    return settings;
  } catch (error) {
    return defaultPomodoro();
  }
}

function savePomodoro() {
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  localStorage.setItem(
    POMODORO_KEY,
    JSON.stringify({
      focusMin: pomodoro.focusMin,
      shortMin: pomodoro.shortMin,
      longMin: pomodoro.longMin,
      roundsBeforeLong: pomodoro.roundsBeforeLong,
      autoNext: pomodoro.autoNext,
      sound: pomodoro.sound,
    })
  );
  localStorage.setItem(
    POMODORO_STATS_KEY,
    JSON.stringify({ date: todayISO(), done: pomodoro.done || 0 })
  );
}

learningState.calendarSettings = loadCalendarSettings();
learningState.calendarView = learningState.calendarSettings.view;
learningState.weekStartDate = startOfWeekISO(todayISO(), learningState.calendarSettings.weekStart);
learningState.pomodoro = loadPomodoro();
learningState.pomodoroDone = learningState.pomodoro.done || 0;
try {
  const savedTokens = Number(localStorage.getItem('zhixing-recognition-tokens') || 0);
  learningState.recognitionTokens = savedTokens >= 512 ? Math.min(32768, savedTokens) : 16384;
} catch (error) {
  learningState.recognitionTokens = 16384;
}

const PRIORITY_LABEL = {
  high: '高优先级',
  medium: '中优先级',
  low: '低优先级',
  none: '无优先级',
};

const PRIORITY_CLASS = {
  high: 'priority-high',
  medium: 'priority-medium',
  low: 'priority-low',
  none: 'priority-none',
};

const MODEL_PRESETS = {
  deepseek: {
    label: 'DeepSeek',
    provider: 'deepseek',
    model: 'deepseek-flash',
    base: 'https://api.deepseek.com',
    official: 'https://platform.deepseek.com',
    note: '高数拍题、错题解析',
  },
  qwen: {
    label: 'Qwen-VL',
    provider: 'qwen',
    model: 'qwen-vl-max',
    base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    official: 'https://bailian.console.aliyun.com',
    note: '复杂公式、题图识别',
  },
  custom: {
    label: '自定义',
    provider: 'custom',
    model: '',
    base: '',
    official: '',
    note: '',
  },
};

function resetLearningState() {
  stopLearningTimer();
  if (learningState.reminderHandle) clearInterval(learningState.reminderHandle);
  learningState.tab = 'focus';
  learningState.overview = null;
  learningState.tasks = [];
  learningState.libraries = [];
  learningState.activeLibraryId = '';
  learningState.questions = [];
  learningState.parsed = [];
  learningState.imageData = '';
  learningState.calendar = null;
  learningState.calendarWeek = null;
  learningState.weekStartDate = startOfWeekISO(
    todayISO(),
    (learningState.calendarSettings || defaultCalendarSettings()).weekStart
  );
  learningState.courses = [];
  learningState.reminded = new Set();
  learningState.reminderHandle = null;
}

function learningPageShell() {
  const user = state.user || {};
  const overview = learningState.overview || {};
  const vision =
    overview.vision_mode === 'http'
      ? '真实视觉模型'
      : overview.vision_mode === 'untested'
        ? '配置待测试'
        : '未配置视觉模型';
  return `
    <div class="page-inner learning-page">
      <div class="page-head learning-head">
        <div>
          <span class="eyebrow">LEARNING SPACE</span>
          <h1>学习空间</h1>
          <p>${escapeHtml(overview.greeting || '把今天要做的事拆小，然后专注完成一件。')}</p>
        </div>
        <div class="head-actions">
          <span class="learning-mode-badge ${overview.vision_mode === 'http' ? 'is-live' : ''}">
            ${icon('shield')} ${vision}
          </span>
          <button type="button" class="ghost-btn" data-learning-action="vision-settings">${icon('settings')} 模型设置</button>
        </div>
      </div>

      <div class="learning-tabs" role="tablist">
        ${[
          ['focus', '专注'],
          ['exam', '考试周'],
          ['tasks', '任务清单'],
          ['review', '复习'],
          ['report', '报告'],
          ['mistakes', '错题本'],
          ['calendar', '日历 / 课程'],
        ]
          .map(
            ([key, label]) =>
              `<button type="button" class="learning-tab ${learningState.tab === key ? 'is-active' : ''}" data-learning-tab="${key}">${label}</button>`
          )
          .join('')}
      </div>

      <div id="learning-content"></div>
    </div>`;
}

async function renderLearningPage() {
  const page = $('#learning-page');
  if (!page) return;
  stopLearningTimer();
  // 任务/课程变更后重新拉日历，避免日历仍显示旧数据。
  learningState.calendar = null;
  learningState.calendarWeek = null;
  try {
    const [overview, tasks, libraries, courses, examRoom] = await Promise.all([
      api('/learning/overview'),
      api('/learning/tasks?on_date=' + new Date().toISOString().slice(0, 10)),
      api('/learning/libraries'),
      api('/learning/courses'),
      api('/learning/exam-room'),
    ]);
    learningState.overview = overview;
    learningState.tasks = tasks.items || overview.tasks || [];
    learningState.libraries = libraries.items || [];
    learningState.courses = courses.items || [];
    learningState.examRoom = examRoom;
    // Review queue is optional during first paint; failure should not block the page.
    try {
      const review = await api('/learning/review');
      learningState.reviewQuestions = review.items || [];
      learningState.reviewSummary = review.summary || null;
    } catch (error) {
      learningState.reviewQuestions = [];
    }
    try {
      learningState.report = await api('/learning/report?days=7');
    } catch (error) {
      learningState.report = null;
    }
    if (!learningState.activeLibraryId && learningState.libraries.length) {
      learningState.activeLibraryId = learningState.libraries[0].id;
      await loadQuestions();
    }
    page.innerHTML = learningPageShell();
    renderLearningContent();
    if (overview.active_focus) {
      startLearningTimer(overview.active_focus, true);
      renderLearningContent();
    }
    startLearningReminders();
  } catch (error) {
    page.innerHTML = `<div class="page-inner"><div class="section-card">${emptyState('alert', '学习空间加载失败', escapeHtml(error.message))}</div></div>`;
  }
}

function renderLearningContent() {
  const content = $('#learning-content');
  if (!content) return;
  if (learningState.tab === 'focus') content.innerHTML = learningFocusHTML();
  if (learningState.tab === 'exam') content.innerHTML = learningExamHTML();
  if (learningState.tab === 'tasks') content.innerHTML = learningTasksHTML();
  if (learningState.tab === 'review') content.innerHTML = learningReviewHTML();
  if (learningState.tab === 'report') content.innerHTML = learningReportHTML();
  if (learningState.tab === 'mistakes') content.innerHTML = learningMistakesHTML();
  if (learningState.tab === 'calendar') {
    content.innerHTML = learningCalendarHTML();
    if (learningState.calendarView === 'week') {
      if (!learningState.calendarWeek) loadLearningWeek();
    } else if (!learningState.calendar) {
      loadLearningCalendar();
    }
  }
  if (learningState.timer) updateLearningTimerUI();
}

function taskRowHTML(task, compact = false) {
  const done = task.status === 'completed';
  return `
    <div class="learning-task ${done ? 'is-done' : ''}" data-task-row="${escapeAttr(task.id)}">
      <button type="button" class="task-check ${done ? 'is-checked' : ''}" data-learning-action="toggle-task" data-task-id="${escapeAttr(task.id)}" data-task-status="${done ? 'pending' : 'completed'}" aria-label="完成任务">
        ${done ? '✓' : ''}
      </button>
      <div class="task-main">
        <strong>${escapeHtml(task.title)}</strong>
        <span>${task.duration_min} 分钟 · 截止 ${escapeHtml(task.due_date || '')}${task.actual_min ? ` · 已投入 ${task.actual_min} 分钟` : ''}</span>
      </div>
      <span class="priority-pill ${PRIORITY_CLASS[task.priority] || ''}">${escapeHtml(task.priority_label || PRIORITY_LABEL[task.priority] || '无优先级')}</span>
      ${compact ? '' : `<button type="button" class="icon-btn task-play" data-learning-action="start-task" data-task-id="${escapeAttr(task.id)}" data-duration="${task.duration_min}" title="开始专注">${icon('play')}</button>`}
      ${compact ? '' : `<button type="button" class="text-btn task-delete" data-learning-action="delete-task" data-task-id="${escapeAttr(task.id)}" title="删除任务">删除</button>`}
    </div>`;
}

function pomodoroDuration(pomodoro, mode) {
  if (mode === 'short') return Number(pomodoro.shortMin) || 5;
  if (mode === 'long') return Number(pomodoro.longMin) || 15;
  return Number(pomodoro.focusMin) || 25;
}

function pomodoroModeLabel(mode) {
  return mode === 'short' ? '短休息' : mode === 'long' ? '长休息' : '专注';
}

function formatClock(milliseconds) {
  const total = Math.max(0, Math.round(milliseconds / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function timerElapsedMs(timer) {
  if (!timer) return 0;
  return (timer.accumulatedMs || 0) + (timer.paused ? 0 : Date.now() - timer.startedAt);
}

function learningFocusHTML() {
  const overview = learningState.overview || {};
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  const tasks = learningState.tasks.filter((task) => task.status !== 'completed');
  const active = learningState.timer;
  const mode = active?.mode || pomodoro.mode || 'focus';
  const planned = active?.plannedMin || pomodoroDuration(pomodoro, mode);
  const elapsed = timerElapsedMs(active);
  const progress = active ? Math.min(100, (elapsed / (planned * 60000)) * 100) : 0;
  const taskOptions = tasks
    .map(
      (task) =>
        `<option value="${escapeAttr(task.id)}" ${active?.taskId === task.id ? 'selected' : ''}>${escapeHtml(task.title)}</option>`
    )
    .join('');
  const recent = (overview.recent_focus || [])
    .slice(0, 4)
    .map(
      (item) =>
        `<div class="learning-history-row"><span>${escapeHtml((item.started_at || '').slice(0, 16).replace('T', ' '))}</span><b>${item.actual_min || 0} 分钟</b></div>`
    )
    .join('');
  const isBreak = mode === 'short' || mode === 'long';
  return `
    <div class="learning-grid learning-grid-focus">
      <div class="section-card timer-card">
        <div class="pomodoro-modes">
          ${[
            ['focus', `专注 ${pomodoro.focusMin}`],
            ['short', `短休 ${pomodoro.shortMin}`],
            ['long', `长休 ${pomodoro.longMin}`],
          ].map(([key, label]) => `<button type="button" class="${mode === key ? 'is-active' : ''}" data-learning-action="pomodoro-mode" data-mode="${key}" ${active ? 'disabled' : ''}>${label}</button>`).join('')}
        </div>
        <div class="timer-ring" id="focus-ring" style="--progress:${progress}">
          <div class="timer-inner">
            <span class="eyebrow">${isBreak ? 'BREAK' : 'FOCUS'}</span>
            <strong id="focus-clock">${active ? '--:--' : formatClock(planned * 60000)}</strong>
            <span id="focus-state">${active ? (active.paused ? '已暂停' : `${pomodoroModeLabel(mode)}中`) : '准备开始'}</span>
          </div>
        </div>
        <div class="pomodoro-round">
          <span>第 ${pomodoro.round} / ${pomodoro.roundsBeforeLong} 个番茄</span>
          <span>今日完成 ${pomodoro.done || 0} 个 · ${overview.today_focus_min || 0} 分钟</span>
        </div>
        <div class="timer-controls">
          ${isBreak || active
            ? ''
            : `<select id="focus-task-select" class="select-input">
                <option value="">不绑定任务，自由专注</option>
                ${taskOptions}
              </select>
              <select id="focus-plan-select" class="select-input">
                ${[...new Set([pomodoro.focusMin, 25, 45, 60, ...tasks.map((task) => task.duration_min)])].map((min) => `<option value="${min}" ${planned === min ? 'selected' : ''}>${min} 分钟</option>`).join('')}
              </select>`}
          ${
            active
              ? `
                <button type="button" class="primary-btn" data-learning-action="${active.paused ? 'resume-pomodoro' : 'pause-pomodoro'}">${active.paused ? '继续' : '暂停'}</button>
                <button type="button" class="ghost-btn" data-learning-action="skip-pomodoro">跳过</button>
                <button type="button" class="ghost-btn" data-learning-action="stop-pomodoro">结束</button>
              `
              : `<button type="button" class="primary-btn" data-learning-action="start-pomodoro">${icon('play')} 开始${isBreak ? '休息' : '专注'}</button>`
          }
        </div>
        <p class="learning-hint">${active ? (isBreak ? '休息也是番茄循环的一部分，起来走两步。' : '暂停时不计入专注时长；结束时会按实际计时记录。') : '完成一个番茄后休息；每 4 个番茄进入长休息。'}</p>
        <div class="settings-block pomodoro-settings">
          <button type="button" class="settings-toggle" data-learning-action="toggle-settings" data-target="pomodoro-settings-panel">${icon('settings')} 番茄设置</button>
          <div id="pomodoro-settings-panel" class="pomodoro-settings-panel" hidden>
          <div class="pomodoro-settings-grid">
            <label>专注 <input type="number" min="1" max="180" value="${pomodoro.focusMin}" data-pomodoro-setting="focusMin" /> 分钟</label>
            <label>短休 <input type="number" min="1" max="60" value="${pomodoro.shortMin}" data-pomodoro-setting="shortMin" /> 分钟</label>
            <label>长休 <input type="number" min="1" max="60" value="${pomodoro.longMin}" data-pomodoro-setting="longMin" /> 分钟</label>
            <label>每几轮长休 <input type="number" min="2" max="8" value="${pomodoro.roundsBeforeLong}" data-pomodoro-setting="roundsBeforeLong" /></label>
            <label><input type="checkbox" data-pomodoro-setting="autoNext" ${pomodoro.autoNext ? 'checked' : ''} /> 自动进入下一段</label>
            <label><input type="checkbox" data-pomodoro-setting="sound" ${pomodoro.sound ? 'checked' : ''} /> 完成提示音</label>
          </div>
          </div>
        </div>
      </div>

      <div class="section-card">
        <div class="section-head">
          <div><h3>今日任务</h3><p class="section-sub">点右侧播放键，直接进入这个任务的专注。</p></div>
          <span class="learning-count">${tasks.length} 项</span>
        </div>
        <div class="learning-task-list">
          ${tasks.length ? tasks.map((task) => taskRowHTML(task)).join('') : learningEmpty('今天还没有任务', '去「任务清单」把今天要做的事写下来。')}
        </div>
      </div>
    </div>

    <div class="section-card learning-history">
      <div class="section-head"><div><h3>今日专注</h3><p class="section-sub">${overview.today_focus_min || 0} 分钟已记录 · ${pomodoro.done || 0} 个番茄</p></div></div>
      ${recent || '<p class="muted-text">还没有完成的专注记录。</p>'}
    </div>`;
}

function learningExamHTML() {
  const room = learningState.examRoom || { exams: [], tasks: [], today_tasks: [], knowledge_points: [] };
  const next = room.next_exam;
  const courses = learningState.courses || [];
  return `
    <div class="learning-grid learning-grid-exam">
      <div class="section-card exam-hero ${next ? `urgency-${next.urgency}` : ''}">
        ${next
          ? `
          <span class="eyebrow">EXAM COUNTDOWN</span>
          <div class="exam-countdown">
            <strong>${next.days_left}</strong><span>天</span>
          </div>
          <h3>${escapeHtml(next.course_name)}</h3>
          <p>${escapeHtml(next.exam_date)} ${escapeHtml(next.start_time || '')} · ${escapeHtml(next.location || '地点待定')}</p>
          <div class="learning-form-row">
            <button type="button" class="primary-btn" data-learning-action="plan-exam" data-exam-id="${escapeAttr(next.id)}">${icon('spark')} 生成 / 重排复习计划</button>
          </div>
          <p class="learning-hint">计划会从今天排到考前一天，按错题数量分配到每天；最多先排 14 天。</p>`
          : `<span class="eyebrow">EXAM COUNTDOWN</span><h3>还没有考试</h3><p class="muted-text">添加考试日期后，系统会倒推每日复习任务。</p>`}
      </div>
      <div class="section-card">
        <div class="section-head"><div><h3>今日复习</h3><p class="section-sub">点右侧播放键，直接进入复习专注。</p></div><span class="learning-count">${room.today_tasks?.length || 0} 项</span></div>
        <div class="learning-task-list">
          ${(room.today_tasks || []).length
            ? room.today_tasks.map((task) => taskRowHTML(task)).join('')
            : learningEmpty('今天没有考试复习任务', '先添加考试，再生成复习计划。')}
        </div>
        <div class="exam-stats">
          <span>错题 ${room.wrong_question_count || 0} 道</span>
          <span>知识点 ${room.knowledge_points?.length || 0} 个</span>
        </div>
        ${room.knowledge_points?.length ? `<div class="exam-points">${room.knowledge_points.map((point) => `<span>${escapeHtml(point)}</span>`).join('')}</div>` : ''}
      </div>
    </div>

    <div class="section-card">
      <div class="section-head"><div><h3>我的考试</h3><p class="section-sub">按日期排序；已结束的考试可以删除。</p></div><span class="learning-count">${room.exams?.length || 0} 场</span></div>
      <div class="exam-list">
        ${(room.exams || []).length
          ? room.exams
              .map(
                (exam) => `
          <div class="exam-row urgency-${exam.urgency}">
            <span class="exam-days">${exam.days_left >= 0 ? `D-${exam.days_left}` : '已结束'}</span>
            <div><strong>${escapeHtml(exam.course_name)}</strong><span>${escapeHtml(exam.exam_date)} ${escapeHtml(exam.start_time || '')} · ${escapeHtml(exam.location || '地点待定')}</span>${exam.note ? `<em>${escapeHtml(exam.note)}</em>` : ''}</div>
            <button type="button" class="ghost-btn" data-learning-action="plan-exam" data-exam-id="${escapeAttr(exam.id)}">生成计划</button>
            <button type="button" class="icon-btn" data-learning-action="delete-exam" data-exam-id="${escapeAttr(exam.id)}" title="删除考试">${icon('close')}</button>
          </div>`
              )
              .join('')
          : learningEmpty('还没有考试', '添加高数、英语等考试日期。')}
      </div>
      <details class="course-form" ${(room.exams || []).length ? '' : 'open'}>
        <summary>+ 添加考试</summary>
        <div class="learning-form-row">
          <input id="exam-course" class="text-input" list="exam-course-list" placeholder="课程名，如 高等数学" />
          <datalist id="exam-course-list">${courses.map((course) => `<option value="${escapeAttr(course.name)}"></option>`).join('')}</datalist>
          <input id="exam-date" class="text-input" type="date" value="${new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)}" />
        </div>
        <div class="learning-form-row">
          <input id="exam-time" class="text-input" placeholder="时间，如 09:00-11:30" />
          <input id="exam-location" class="text-input" placeholder="地点" />
          <input id="exam-note" class="text-input" placeholder="备注（可选）" />
        </div>
        <button type="button" class="primary-btn" data-learning-action="add-exam">保存考试</button>
      </details>
    </div>`;
}

function learningTasksHTML() {
  const pending = learningState.tasks.filter((task) => task.status !== 'completed');
  return `
    <div class="learning-grid learning-grid-tasks">
      <div class="section-card">
        <div class="section-head"><div><h3>把计划拆成清单</h3><p class="section-sub">多个任务用逗号、分号或换行分开，例如“今天复习高数 2 小时，重点看极限，背单词 30 分钟，明天交英语作业”；“重点看…”会并入上一条。</p></div></div>
        <textarea id="plan-input" class="learning-textarea" rows="5" placeholder="今天要做什么？写清楚任务、大概时长、截止时间，越具体越好。"></textarea>
        <div class="learning-form-row">
          <button type="button" class="primary-btn" data-learning-action="parse-plan">${icon('spark')} 智能拆解</button>
          <button type="button" class="ghost-btn" data-learning-action="assignment-import">${icon('upload')} 从作业图片/文字导入</button>
          <label class="model-toggle" title="需要先在「模型设置」中配置并测试模型">
            <input id="plan-use-model" type="checkbox" />
            <span>用模型提炼</span>
          </label>
          <span class="muted-text">解析后可以改优先级和日期，再导入；模型开关关闭时只用本地规则。</span>
        </div>
        <div id="parsed-preview" class="parsed-preview"></div>
      </div>

      <div class="section-card">
        <div class="section-head"><div><h3>当前清单</h3><p class="section-sub">优先级、截止日期、实际投入都会保留；完成或未完成都可以删除。</p></div><div class="section-head-actions"><span class="learning-count">${pending.length} 待完成</span><button type="button" class="ghost-btn" data-learning-action="create-task">新建任务</button></div></div>
        <div class="learning-task-list">
          ${learningState.tasks.length ? learningState.tasks.map((task) => editableTaskRowHTML(task)).join('') : learningEmpty('清单还是空的', '左边写今天的计划，系统会按逗号、时间词拆成多条。')}
        </div>
      </div>
    </div>`;
}

function editableTaskRowHTML(task) {
  const done = task.status === 'completed';
  return `
    <div class="learning-task editable ${done ? 'is-done' : ''}" data-task-row="${escapeAttr(task.id)}">
      <button type="button" class="task-check ${done ? 'is-checked' : ''}" data-learning-action="toggle-task" data-task-id="${escapeAttr(task.id)}" data-task-status="${done ? 'pending' : 'completed'}">${done ? '✓' : ''}</button>
      <div class="task-main">
        <strong>${escapeHtml(task.title)}</strong>
        <span>${escapeHtml(task.detail || '')}</span>
        <span>${task.duration_min} 分钟 · 截止 ${escapeHtml(task.due_date || '')}${task.actual_min ? ` · 已投入 ${task.actual_min} 分钟` : ''}</span>
      </div>
      <select class="select-input task-priority-select" data-task-priority="${escapeAttr(task.id)}">
        ${['high', 'medium', 'low', 'none'].map((key) => `<option value="${key}" ${task.priority === key ? 'selected' : ''}>${PRIORITY_LABEL[key]}</option>`).join('')}
      </select>
      <button type="button" class="icon-btn task-play" data-learning-action="start-task" data-task-id="${escapeAttr(task.id)}" data-duration="${task.duration_min}" title="开始专注">${icon('play')}</button>
      <button type="button" class="text-btn task-delete" data-learning-action="delete-task" data-task-id="${escapeAttr(task.id)}" title="删除任务">删除</button>
    </div>`;
}

function learningReportHTML() {
  const report = learningState.report;
  if (!report) {
    return '<div class="section-card"><p class="muted-text">学习报告还在加载，稍后再试。</p></div>';
  }
  const maxPoint = Math.max(1, ...(report.top_knowledge_points || []).map((item) => item.count));
  return `
    <div class="section-card">
      <div class="section-head"><div><h3>最近 ${report.days} 天学习报告</h3><p class="section-sub">${escapeHtml(report.start)} 至 ${escapeHtml(report.end)} · 只给学生本人看</p></div></div>
      <div class="kpi-grid report-kpis">
        ${kpiCard('专注', `${report.focus_minutes}<small>分钟</small>`, `${report.focus_sessions} 次 · ${report.focus_days} 天`, true)}
        ${kpiCard('完成任务', String(report.tasks?.completed || 0), `待办 ${report.tasks?.pending || 0} 项`, true)}
        ${kpiCard('到期复习', String(report.review?.due || 0), `错题 ${report.review?.total || 0} 道`, (report.review?.due || 0) === 0)}
        ${kpiCard('错题总数', String(report.question_count || 0), `已复习 ${report.review?.reviewed || 0} 道`, true)}
      </div>
    </div>
    <div class="section-card">
      <div class="section-head"><div><h3>知识点分布</h3><p class="section-sub">按错题知识点计数，不是掌握度。</p></div></div>
      ${report.top_knowledge_points?.length
        ? `<div class="report-bars">${report.top_knowledge_points.map((item) => `<div class="report-bar"><span>${escapeHtml(item.name)}</span><div><i style="width:${Math.round((item.count / maxPoint) * 100)}%"></i></div><b>${item.count}</b></div>`).join('')}</div>`
        : '<p class="muted-text">录入并标注错题知识点后，这里会出现分布。</p>'}
    </div>`;
}

function learningReviewHTML() {
  const items = learningState.reviewQuestions || [];
  const summary = learningState.reviewSummary || {};
  return `
    <div class="section-card">
      <div class="section-head">
        <div><h3>今日复习</h3><p class="section-sub">按间隔重复排队：答对后 3/7/14/30 天再见；答错明天再来。</p></div>
        <span class="learning-count">${summary.due || 0} 题到期</span>
      </div>
      <div class="exam-stats">
        <span>到期 ${summary.due || 0}</span>
        <span>错题总数 ${summary.total || 0}</span>
        <span>已复习 ${summary.reviewed || 0}</span>
      </div>
      <div class="question-grid">
        ${items.length
          ? items.map((question) => `
            <article class="question-card">
              ${question.image_url ? `<img src="${question.image_url}" alt="题目图" />` : ''}
              <span class="eyebrow">DUE ${escapeHtml(question.review_due || '')} · 连对 ${question.review_streak || 0}</span>
              <div class="question-rich">${renderRichText(question.question_text)}</div>
              <span class="question-meta">${escapeHtml(question.knowledge_points || '待标注知识点')}</span>
              <div class="question-actions">
                <button type="button" class="ghost-btn" data-learning-action="review-practice" data-question-id="${escapeAttr(question.id)}">${icon('play')} 再练一次</button>
                <button type="button" class="ghost-btn" data-learning-action="view-solution" data-question-id="${escapeAttr(question.id)}">查看解析</button>
              </div>
            </article>`).join('')
          : learningEmpty('今天没有到期错题', '先练习错题并提交，系统会按结果安排下一次复习。')}
      </div>
    </div>`;
}

function learningMistakesHTML() {
  const libraries = learningState.libraries;
  const active = libraries.find((item) => item.id === learningState.activeLibraryId);
  return `
    <div class="section-card">
      <div class="section-head">
        <div><h3>我的错题本</h3><p class="section-sub">按书/章节建库；题目图只在校内预处理后保存，识别结果可修改。</p></div>
        <div class="section-head-actions">
          <span class="learning-count">${libraries.length} 个库</span>
          <button type="button" class="ghost-btn" data-learning-action="question-trash">${icon('trash')} 题目回收站</button>
          <button type="button" class="ghost-btn" data-learning-action="library-trash">${icon('book')} 错题本回收站</button>
        </div>
      </div>
      <div class="library-create-row">
        <input id="new-library-name" class="text-input" placeholder="例如：高等数学上错题本" maxlength="60" />
        <input id="new-library-subject" class="text-input" placeholder="学科（可选）" maxlength="30" />
        <button type="button" class="primary-btn" data-learning-action="create-library">${icon('plus')} 新建</button>
      </div>
      <div class="library-grid">
        ${libraries.length
          ? libraries
              .map(
                (lib) => `
            <div class="library-card ${lib.id === learningState.activeLibraryId ? 'is-active' : ''}">
              <button type="button" class="library-open" data-learning-action="select-library" data-library-id="${escapeAttr(lib.id)}">
                <span class="library-icon">${icon('book')}</span>
                <strong>${escapeHtml(lib.name)}</strong>
                <span>${escapeHtml(lib.subject || '未设学科')} · ${lib.question_count || 0} 道题</span>
              </button>
              <div class="library-card-actions">
                <button type="button" class="text-btn task-delete" data-learning-action="delete-library" data-library-id="${escapeAttr(lib.id)}">删除</button>
              </div>
            </div>`
              )
              .join('')
          : learningEmpty('还没有错题本', '先建一个「高等数学上错题本」。')}
      </div>
    </div>

    ${active ? `
      <div class="section-card">
        <div class="section-head"><div><h3>${escapeHtml(active.name)}</h3><p class="section-sub">上传题目图片，或直接粘贴题干。</p></div><span class="learning-count">${learningState.questions.length} 道</span></div>
        <div class="upload-box">
          <label class="file-drop">
            <input type="file" id="question-file" accept="image/png,image/jpeg,image/webp" />
            <span>${icon('upload')} 选择题目图片</span>
            <small>JPG/PNG/WebP，最大 12MB；原图会先去元数据、缩放到 1600px。</small>
          </label>
          <div id="question-preview" class="question-preview ${learningState.imageData ? 'has-image' : ''}">
            ${learningState.imageData ? `<img src="${learningState.imageData}" alt="题目预览" />` : ''}
          </div>
          <textarea id="question-text" class="learning-textarea" rows="3" placeholder="也可以直接粘贴题干（可选）"></textarea>
          <div class="recognition-limit">
            <span>识别上限 <strong>${learningState.recognitionTokens || 16384}</strong> tokens · 每次上传独立</span>
            <button type="button" class="settings-toggle" data-learning-action="recognition-tokens">${icon('settings')} 调节</button>
          </div>
          <button type="button" class="primary-btn" data-learning-action="upload-question">${icon('spark')} ${learningState.overview?.vision_mode === 'http' ? '识别并保存' : '先配置模型再识别'}</button>
        </div>
        <div class="question-grid">
          ${learningState.questions.length
            ? learningState.questions
                .map(
                  (question, index) => `
              <article class="question-card">
                ${question.image_url ? `<img src="${question.image_url}" alt="题目图" />` : ''}
                <span class="eyebrow">QUESTION ${String(index + 1).padStart(2, '0')}</span>
                <div class="question-rich">${renderRichText(question.question_text)}</div>
                <span class="question-meta">${escapeHtml(question.knowledge_points || '待标注知识点')} · ${escapeHtml(question.difficulty || '中等')}</span>
                <div class="question-actions">
                  <button type="button" class="ghost-btn" data-learning-action="practice" data-question-id="${escapeAttr(question.id)}">${icon('play')} 开始练习</button>
                  <button type="button" class="ghost-btn" data-learning-action="view-solution" data-question-id="${escapeAttr(question.id)}">查看解析</button>
                  <button type="button" class="text-btn task-delete" data-learning-action="delete-question" data-question-id="${escapeAttr(question.id)}">删除</button>
                </div>
              </article>`
                )
                .join('')
            : learningEmpty('这个库还没有题', '上传一张题目图片，或粘贴题干。')}
        </div>
      </div>` : ''}`;
}

function courseWeekLabel(course) {
  const weeks = String(course.weeks || '').trim();
  if (!weeks) return '每周';
  const parity =
    course.week_parity === 'odd' ? ' · 单周' : course.week_parity === 'even' ? ' · 双周' : '';
  return `第 ${weeks} 周${parity}`;
}

function courseWeekNumber(dateISO, semesterStart) {
  if (!semesterStart) return 0;
  const start = new Date(`${semesterStart}T00:00:00`);
  const target = new Date(`${dateISO}T00:00:00`);
  const days = Math.floor((target - start) / 86400000);
  return days < 0 ? 0 : Math.floor(days / 7) + 1;
}

function courseMatchesWeek(course, dateISO, semesterStart, settings) {
  if (settings?.showOffWeek) return true;
  const weeks = String(course.weeks || '').trim();
  if (!weeks || !semesterStart) return true;
  const week = courseWeekNumber(dateISO, semesterStart);
  if (!week) return false;
  const ranges = weeks.split(/[,，;；\s]+/).filter(Boolean);
  let inRange = false;
  for (const range of ranges) {
    const parts = range.split(/[-~到]/).map((part) => Number(part)).filter(Boolean);
    if (!parts.length) continue;
    const start = parts[0];
    const end = parts.length > 1 ? parts[1] : start;
    if (week >= Math.min(start, end) && week <= Math.max(start, end)) {
      inRange = true;
      break;
    }
  }
  if (!inRange) return false;
  if (course.week_parity === 'odd') return week % 2 === 1;
  if (course.week_parity === 'even') return week % 2 === 0;
  return true;
}

function calendarStyleVars(settings) {
  return [
    `--calendar-cell-height:${Number(settings.cellHeight) || 126}px`,
    `--calendar-radius:${Number(settings.radius) || 12}px`,
    `--calendar-opacity:${Number(settings.opacity) || 1}`,
    `--calendar-text:${settings.textColor || '#26364a'}`,
    `--calendar-border:${settings.borderColor || '#d7e0e8'}`,
  ].join(';');
}

function calendarItemHTML(item, mode, settings) {
  if (mode === 'courses') {
    const time = String(item.start_time || '').slice(0, 5);
    return `<span class="calendar-course" title="${escapeAttr(`${time}-${item.end_time || ''} ${item.name} ${item.location || ''}`)}">${settings.showTime ? `<b>${escapeHtml(time)}</b> ` : ''}${escapeHtml(item.name)}</span>`;
  }
  return `<span class="calendar-task" title="${escapeAttr(`${item.title} · ${item.duration_min || 60} 分钟`)}">${escapeHtml(item.title)}${settings.showTime ? ` <i>${escapeHtml(String(item.duration_min || 60))}m</i>` : ''}</span>`;
}

function calendarDayItems(day, mode, settings, courses, semesterStart) {
  if (mode === 'courses') {
    return courses
      .filter((course) => Number(course.weekday) === Number(day.weekday))
      .filter((course) => courseMatchesWeek(course, day.date, semesterStart, settings))
      .sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
  }
  return day.tasks || [];
}

function renderCalendarWeek(data, mode, settings) {
  const courses = data.courses || learningState.courses || [];
  const semesterStart = data.semester_start || learningState.semesterStart || '';
  const days = (data.days || []).filter((day) => settings.showWeekends || !day.is_weekend);
  const columns = days.length || 1;
  const labels = ['一', '二', '三', '四', '五', '六', '日'];
  const today = todayISO();
  return `
    <div class="calendar-week-head" style="grid-template-columns:repeat(${columns},minmax(0,1fr))">
      ${days.map((day) => `
        <div class="calendar-week-title ${day.date === today ? 'is-today' : ''}">
          <strong>${day.month}/${day.day}</strong>
          <span>周${labels[day.weekday - 1]}</span>
        </div>`).join('')}
    </div>
    <div class="calendar-week-days" style="grid-template-columns:repeat(${columns},minmax(0,1fr))">
      ${days.map((day) => {
        const items = calendarDayItems(day, mode, settings, courses, semesterStart);
        const visible = items.slice(0, 8);
        return `
          <div class="calendar-week-cell ${day.is_weekend ? 'is-weekend' : ''} ${day.holiday ? 'is-holiday' : ''} ${day.date === today ? 'is-today' : ''}">
            ${day.holiday ? `<span class="calendar-holiday">${escapeHtml(day.holiday)}</span>` : ''}
            ${visible.map((item) => calendarItemHTML(item, mode, settings)).join('')}
            ${items.length > visible.length ? `<span class="calendar-more">+${items.length - visible.length} 更多</span>` : ''}
          </div>`;
      }).join('')}
    </div>`;
}

function renderCalendarMonth(calendar, mode, settings) {
  const courses = calendar.courses || learningState.courses || [];
  const semesterStart = calendar.semester_start || learningState.semesterStart || '';
  const order = settings.showWeekends
    ? settings.weekStart === 'sunday'
      ? [7, 1, 2, 3, 4, 5, 6]
      : [1, 2, 3, 4, 5, 6, 7]
    : [1, 2, 3, 4, 5];
  const labels = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '日' };
  const today = todayISO();
  const firstWeekday = calendar.days[0]?.weekday;
  const firstIndex = order.indexOf(firstWeekday);
  const blankCount = firstIndex >= 0 ? firstIndex : 0;
  const days = calendar.days.filter((day) => order.includes(day.weekday));
  return `
    <div class="calendar-weekhead" style="grid-template-columns:repeat(${order.length},minmax(0,1fr))">
      ${order.map((weekday) => `<span>${labels[weekday]}</span>`).join('')}
    </div>
    <div class="calendar-days" style="grid-template-columns:repeat(${order.length},minmax(0,1fr))">
      ${Array.from({ length: blankCount }, () => '<div class="calendar-cell is-blank"></div>').join('')}
      ${days.map((day) => {
        const items = calendarDayItems(day, mode, settings, courses, semesterStart);
        const visible = items.slice(0, 3);
        return `
          <div class="calendar-cell ${day.is_weekend ? 'is-weekend' : ''} ${day.holiday ? 'is-holiday' : ''} ${day.date === today ? 'is-today' : ''}">
            <div class="calendar-cell-head">
              <span class="calendar-day">${day.day}</span>
              ${day.date === today ? '<span class="calendar-today-label">今天</span>' : ''}
            </div>
            ${day.holiday ? `<span class="calendar-holiday">${escapeHtml(day.holiday)}</span>` : ''}
            ${visible.map((item) => calendarItemHTML(item, mode, settings)).join('')}
            ${items.length > visible.length ? `<span class="calendar-more">+${items.length - visible.length} 更多</span>` : ''}
          </div>`;
      }).join('')}
    </div>`;
}

function calendarSettingsHTML(settings, semesterStart = '') {
  const check = (key) => (settings[key] ? 'checked' : '');
  return `
    <div class="settings-block">
      <button type="button" class="settings-toggle" data-learning-action="toggle-settings" data-target="calendar-settings-panel">${icon('settings')} 显示设置</button>
      <div id="calendar-settings-panel" class="calendar-settings-panel" hidden>
      <div class="calendar-settings-grid">
        <label>学期开始日期（第 1 周）
          <input type="date" value="${escapeAttr(semesterStart)}" data-semester-start />
        </label>
        <label>周起始
          <select data-calendar-setting="weekStart">
            <option value="monday" ${settings.weekStart === 'monday' ? 'selected' : ''}>周一</option>
            <option value="sunday" ${settings.weekStart === 'sunday' ? 'selected' : ''}>周日</option>
          </select>
        </label>
        <label><input type="checkbox" data-calendar-setting="showWeekends" ${check('showWeekends')} /> 显示周末</label>
        <label><input type="checkbox" data-calendar-setting="showTime" ${check('showTime')} /> 显示时间</label>
        <label><input type="checkbox" data-calendar-setting="showGrid" ${check('showGrid')} /> 显示网格</label>
        <label><input type="checkbox" data-calendar-setting="showOffWeek" ${check('showOffWeek')} /> 显示非本周课程</label>
        <label>格子高度
          <input type="range" min="90" max="240" step="2" value="${Number(settings.cellHeight) || 126}" data-calendar-setting="cellHeight" />
        </label>
        <label>圆角
          <input type="range" min="0" max="24" step="1" value="${Number(settings.radius) || 12}" data-calendar-setting="radius" />
        </label>
        <label>不透明度
          <input type="range" min="0.5" max="1" step="0.05" value="${Number(settings.opacity) || 1}" data-calendar-setting="opacity" />
        </label>
        <label>文字颜色 <input type="color" value="${escapeAttr(settings.textColor || '#26364a')}" data-calendar-setting="textColor" /></label>
        <label>边框颜色 <input type="color" value="${escapeAttr(settings.borderColor || '#d7e0e8')}" data-calendar-setting="borderColor" /></label>
        <button type="button" class="text-btn" data-learning-action="reset-calendar-settings">恢复默认</button>
      </div>
      </div>
    </div>`;
}

function learningCalendarHTML() {
  const settings = learningState.calendarSettings || defaultCalendarSettings();
  const mode = learningState.calendarMode || 'courses';
  const view = learningState.calendarView || 'month';
  const data = view === 'week' ? learningState.calendarWeek : learningState.calendar;
  const label = view === 'week' && data
    ? `${data.start} 至 ${data.end}`
    : data
      ? `${data.year} 年 ${data.month} 月`
      : '加载中…';
  return `
    <div class="calendar-stack" style="${calendarStyleVars(settings)}">
      <div class="section-card calendar-main">
        <div class="section-head calendar-head">
          <div>
            <h3>${label}</h3>
            <p class="section-sub">${mode === 'courses' ? '课程表按星期显示；周视图适合看这一周的课。' : '待办任务按截止日显示；没有日期的任务不会凭空出现。'}</p>
          </div>
          <div class="calendar-controls">
            <div class="calendar-mode-switch" role="tablist" aria-label="日历模式">
              <button type="button" class="${mode === 'courses' ? 'is-active' : ''}" data-learning-action="calendar-mode" data-mode="courses">课程表</button>
              <button type="button" class="${mode === 'tasks' ? 'is-active' : ''}" data-learning-action="calendar-mode" data-mode="tasks">待办任务</button>
            </div>
            <div class="calendar-mode-switch" role="tablist" aria-label="日历范围">
              <button type="button" class="${view === 'week' ? 'is-active' : ''}" data-learning-action="calendar-view" data-view="week">周</button>
              <button type="button" class="${view === 'month' ? 'is-active' : ''}" data-learning-action="calendar-view" data-view="month">月</button>
            </div>
            <div class="calendar-nav">
              <button type="button" class="icon-btn" data-learning-action="calendar-prev">${icon('chevron')}</button>
              <button type="button" class="icon-btn" data-learning-action="calendar-next">${icon('chevron')}</button>
            </div>
          </div>
        </div>
        <div class="calendar-legend">
          ${mode === 'courses' ? '<span class="legend-chip legend-course"></span> 课程' : '<span class="legend-chip legend-task"></span> 到期任务'}
          <span class="legend-chip legend-holiday"></span> 节假日
          <span class="legend-note">${view === 'week' ? '一周一屏，适合逐日看；可切换月视图。' : '整月总览；格子高度、颜色可在显示设置里调。'}</span>
        </div>
        ${calendarSettingsHTML(settings, learningState.semesterStart || data?.semester_start || '')}
        ${mode === 'courses' && data && !(data.courses || []).length
          ? '<div class="notice-box">还没有课程。先在下方「课程管理」添加一门课，日历对应星期就会出现。</div>'
          : ''}
        <div class="calendar-grid ${settings.showGrid ? '' : 'calendar-no-grid'}" id="learning-calendar">
          ${data
            ? view === 'week'
              ? renderCalendarWeek(data, mode, settings)
              : renderCalendarMonth(data, mode, settings)
            : '<p class="muted-text">加载中…</p>'}
        </div>
      </div>

      ${mode === 'courses' ? courseManagerHTML() : calendarTasksHTML(data, view)}
    </div>`;
}

function courseManagerHTML() {
  const courses = learningState.courses || [];
  return `
    <div class="section-card">
      <div class="section-head"><div><h3>课程表 · 课程管理</h3><p class="section-sub">课程来自这里；可手动添加、粘贴整张课表，或打开课程资料。</p></div><span class="learning-count">${courses.length} 门</span></div>
      <div class="course-list">
        ${courses.length
          ? courses
              .map(
                (course) => `
            <div class="course-row">
              <span class="course-day">周${'一二三四五六日'[course.weekday - 1]}</span>
              <div><strong>${escapeHtml(course.name)}</strong><span>${escapeHtml(course.start_time)}–${escapeHtml(course.end_time)} · ${escapeHtml(course.location || '地点待定')} · ${escapeHtml(courseWeekLabel(course))}</span>${course.assignment ? `<em>作业：${escapeHtml(course.assignment)}</em>` : ''}</div>
              <button type="button" class="ghost-btn" data-learning-action="course-materials" data-course-id="${escapeAttr(course.id)}">资料</button>
            </div>`
              )
              .join('')
          : '<p class="muted-text">还没有课程。添加后会在上面日历的对应星期显示。</p>'}
      </div>
      <details class="course-form">
        <summary>+ 添加一门课</summary>
        <input id="course-name" class="text-input" placeholder="课程名" />
        <div class="learning-form-row">
          <select id="course-weekday" class="select-input">${[1,2,3,4,5,6,7].map((d) => `<option value="${d}">周${'一二三四五六日'[d-1]}</option>`).join('')}</select>
          <input id="course-start" class="text-input" value="08:00" />
          <input id="course-end" class="text-input" value="09:40" />
        </div>
        <input id="course-location" class="text-input" placeholder="地点" />
        <div class="learning-form-row">
          <input id="course-weeks" class="text-input" placeholder="周次：1-16 或 5,10-17" />
          <select id="course-parity" class="select-input">
            <option value="all">每周</option>
            <option value="odd">仅单周</option>
            <option value="even">仅双周</option>
          </select>
        </div>
        <input id="course-assignment" class="text-input" placeholder="本周作业（可选）" />
        <button type="button" class="primary-btn" data-learning-action="add-course">保存课程</button>
      </details>
      <details class="course-form">
        <summary>粘贴整张课程表导入</summary>
        <textarea id="course-import" class="learning-textarea" rows="5" placeholder="周一 08:00-09:40 高等数学 A101&#10;周二 13:30-15:10 大学物理 B203"></textarea>
        <button type="button" class="primary-btn" data-learning-action="import-courses">解析并导入</button>
      </details>
    </div>`;
}

function calendarTasksHTML(calendar, view = 'month') {
  const tasks = [];
  for (const day of calendar?.days || []) {
    for (const task of day.tasks || []) {
      tasks.push({ ...task, due_date: task.due_date || day.date });
    }
  }
  const title = view === 'week' ? '本周待办' : '本月待办';
  return `
    <div class="section-card">
      <div class="section-head"><div><h3>${title}</h3><p class="section-sub">按截止日期列出；完成、删除、开始专注都可以直接操作。</p></div><span class="learning-count">${tasks.length} 项</span></div>
      <div class="learning-task-list">
        ${tasks.length
          ? tasks.map((task) => taskRowHTML(task)).join('')
          : '<p class="muted-text">本月没有待办任务。</p>'}
      </div>
    </div>`;
}

const MATH_SYMBOLS = {
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', theta: 'θ',
  lambda: 'λ', mu: 'μ', pi: 'π', rho: 'ρ', sigma: 'σ', tau: 'τ', phi: 'φ',
  omega: 'ω', Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Pi: 'Π',
  Sigma: 'Σ', Phi: 'Φ', Omega: 'Ω', times: '×', cdot: '·', div: '÷',
  pm: '±', mp: '∓', le: '≤', leq: '≤', ge: '≥', geq: '≥', neq: '≠',
  approx: '≈', equiv: '≡', propto: '∝', infty: '∞', sum: '∑', prod: '∏',
  iint: '∬', iiint: '∭', oint: '∮', coprod: '∐', bigcup: '⋃', bigcap: '⋂',
  int: '∫', partial: '∂', nabla: '∇', to: '→', rightarrow: '→',
  leftarrow: '←', leftrightarrow: '↔', therefore: '∴', because: '∵',
  degree: '°', angle: '∠', perp: '⊥', parallel: '∥', in: '∈', notin: '∉',
  subset: '⊂', subseteq: '⊆', cup: '∪', cap: '∩', emptyset: '∅',
  forall: '∀', exists: '∃', sim: '∼', cong: '≅', triangle: '△',
};

const MATH_LARGE_OPERATORS = new Set([
  'int', 'iint', 'iiint', 'oint', 'sum', 'prod', 'coprod', 'bigcup', 'bigcap',
]);

function renderChem(src) {
  let value = escapeHtml(src);
  value = value.replace(/<=>/g, '⇌').replace(/-&gt;/g, '→').replace(/<->/g, '↔');
  value = value.replace(/([A-Z][a-z]?)(\d+)/g, '$1<sub>$2</sub>');
  value = value.replace(/([)\]])(\d+)/g, '$1<sub>$2</sub>');
  value = value.replace(/\^(\d*[+-])/g, '<sup>$1</sup>');
  return `<span class="math-chem">${value}</span>`;
}

function mathParse(src) {
  let index = 0;
  function readGroup() {
    while (src[index] === ' ') index += 1;
    if (src[index] === '{') {
      let depth = 1;
      const start = ++index;
      while (index < src.length && depth > 0) {
        if (src[index] === '{') depth += 1;
        if (src[index] === '}') depth -= 1;
        index += 1;
      }
      return src.slice(start, index - 1);
    }
    return src[index++] || '';
  }
  let output = '';
  while (index < src.length) {
    const char = src[index++];
    if (char === '\\') {
      if (src[index] === '\\') {
        index += 1;
        output += '<br>';
        continue;
      }
      const command = /^[A-Za-z]+/.exec(src.slice(index));
      let name = command ? command[0] : src[index++];
      if (command) index += command[0].length;
      if (name === 'frac') {
        const numerator = readGroup();
        const denominator = readGroup();
        output += `<span class="math-frac"><span class="math-num">${mathParse(numerator)}</span><span class="math-den">${mathParse(denominator)}</span></span>`;
      } else if (name === 'sqrt') {
        let degree = '';
        if (src[index] === '[') {
          const close = src.indexOf(']', index);
          if (close > index) {
            degree = src.slice(index + 1, close);
            index = close + 1;
          }
        }
        const radicand = readGroup();
        output += `<span class="math-sqrt">${degree ? `<sup>${mathParse(degree)}</sup>` : ''}<span class="math-radical">√</span><span class="math-radicand">${mathParse(radicand)}</span></span>`;
      } else if (name === 'text' || name === 'mathrm') {
        output += escapeHtml(readGroup());
      } else if (name === 'mathbf') {
        output += `<strong>${mathParse(readGroup())}</strong>`;
      } else if (name === 'overline') {
        output += `<span class="math-overline">${mathParse(readGroup())}</span>`;
      } else if (name === 'vec') {
        output += `<span class="math-vec">${mathParse(readGroup())}</span>`;
      } else if (name === 'ce') {
        output += renderChem(readGroup());
      } else if (name === 'left' || name === 'right') {
        if (src[index] && src[index] !== '.') output += escapeHtml(src[index]);
        index += src[index] ? 1 : 0;
      } else if (MATH_LARGE_OPERATORS.has(name) && MATH_SYMBOLS[name]) {
        output += `<span class="math-operator">${MATH_SYMBOLS[name]}</span>`;
      } else if (MATH_SYMBOLS[name]) {
        output += `<span class="math-symbol">${MATH_SYMBOLS[name]}</span>`;
      } else if (name === ',' || name === ';' || name === 'quad') {
        output += ' ';
      } else {
        output += escapeHtml(name);
      }
      continue;
    }
    if (char === '^' || char === '_') {
      const argument = readGroup();
      output += char === '^' ? `<sup>${mathParse(argument)}</sup>` : `<sub>${mathParse(argument)}</sub>`;
      continue;
    }
    if (char === '{' || char === '}') continue;
    if (char === '&') {
      output += '&amp;';
      continue;
    }
    output += escapeHtml(char);
  }
  return output;
}

function renderMath(src, display = false) {
  return `<span class="math-formula${display ? ' math-display' : ''}">${mathParse(src.trim())}</span>`;
}

function renderInlineRich(text) {
  const formulas = [];
  const protectedText = String(text || '').replace(
    /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\))/g,
    (match) => {
      let source = match;
      let display = false;
      if (match.startsWith('$$')) {
        source = match.slice(2, -2);
        display = true;
      } else if (match.startsWith('\\[')) {
        source = match.slice(2, -2);
        display = true;
      } else if (match.startsWith('\\(')) {
        source = match.slice(2, -2);
      } else {
        source = match.slice(1, -1);
      }
      formulas.push(renderMath(source, display));
      return `@@MATH${formulas.length - 1}@@`;
    }
  );
  let html = escapeHtml(protectedText);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\n/g, '<br>');
  formulas.forEach((formula, index) => {
    html = html.replaceAll(`@@MATH${index}@@`, formula);
  });
  return html;
}

function renderRichText(text) {
  const source = String(text || '').replace(/\r\n/g, '\n').trim();
  if (!source) return '<p class="muted-text">暂无解析。</p>';
  return source
    .split(/\n{2,}/)
    .map((block) => {
      if (block.startsWith('```')) {
        return `<pre><code>${escapeHtml(block.replace(/^```[a-z]*\n?|```$/g, ''))}</code></pre>`;
      }
      const blockLines = block.split('\n');
      const heading = /^(#{1,4})\s+(.+)$/.exec(blockLines[0] || '');
      if (heading) {
        const level = Math.min(4, heading[1].length + 2);
        const rest = blockLines.slice(1).join('\n').trim();
        return `<h${level}>${renderInlineRich(heading[2])}</h${level}>${rest ? renderRichText(rest) : ''}`;
      }
      const lines = blockLines;
      if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
        return `<ul>${lines.map((line) => `<li>${renderInlineRich(line.replace(/^\s*[-*]\s+/, ''))}</li>`).join('')}</ul>`;
      }
      if (lines.every((line) => /^\s*\d+[.)]\s+/.test(line))) {
        return `<ol>${lines.map((line) => `<li>${renderInlineRich(line.replace(/^\s*\d+[.)]\s+/, ''))}</li>`).join('')}</ol>`;
      }
      return `<p>${renderInlineRich(block)}</p>`;
    })
    .join('');
}

function learningEmpty(title, desc) {
  return `<div class="learning-empty"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(desc)}</span></div>`;
}

/* ---------------- 任务提醒 ---------------- */

function startLearningReminders() {
  if (learningState.reminderHandle) clearInterval(learningState.reminderHandle);
  learningState.reminderHandle = setInterval(checkLearningReminders, 30000);
  checkLearningReminders();
}

function checkLearningReminders() {
  const now = Date.now();
  learningState.tasks
    .filter((task) => task.status === 'pending' && task.remind_at)
    .forEach((task) => {
      if (learningState.reminded.has(task.id)) return;
      const when = new Date(task.remind_at).getTime();
      if (Number.isNaN(when) || when > now) return;
      learningState.reminded.add(task.id);
      toast(`任务提醒：${task.title}`, 'info');
    });
}

/* ---------------- 专注计时 ---------------- */

function startLearningTimer(active, fromServer = false) {
  stopLearningTimer();
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  const plannedMin = Number(active.planned_min || active.plannedMin || pomodoro.focusMin || 25);
  const startedMs = active.started_at || active.startedAt
    ? new Date(active.started_at || active.startedAt).getTime()
    : Date.now();
  learningState.timer = {
    focusId: active.id,
    taskId: active.task_id || active.taskId || '',
    plannedMin,
    startedAt: startedMs,
    accumulatedMs: 0,
    paused: false,
    finished: false,
    mode: 'focus',
    round: pomodoro.round,
    fromServer,
  };
  pomodoro.mode = 'focus';
  learningState.timerHandle = setInterval(updateLearningTimerUI, 1000);
  updateLearningTimerUI();
  if (!fromServer) renderLearningContent();
}

function startBreakTimer(kind = 'short') {
  stopLearningTimer();
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  const plannedMin = pomodoroDuration(pomodoro, kind);
  pomodoro.mode = kind;
  learningState.timer = {
    focusId: null,
    taskId: '',
    plannedMin,
    startedAt: Date.now(),
    accumulatedMs: 0,
    paused: false,
    finished: false,
    mode: kind,
    round: pomodoro.round,
  };
  learningState.timerHandle = setInterval(updateLearningTimerUI, 1000);
  updateLearningTimerUI();
  renderLearningContent();
}

function stopLearningTimer() {
  if (learningState.timerHandle) clearInterval(learningState.timerHandle);
  learningState.timerHandle = null;
  document.title = '知行 · 校园智能服务助手';
}

function updateLearningTimerUI() {
  const timer = learningState.timer;
  const clock = $('#focus-clock');
  if (!timer || !clock) return;
  const elapsedSec = timerElapsedMs(timer) / 1000;
  const totalSec = timer.plannedMin * 60;
  const remaining = totalSec - elapsedSec;
  const abs = Math.abs(remaining);
  const minutes = String(Math.floor(abs / 60)).padStart(2, '0');
  const seconds = String(Math.floor(abs % 60)).padStart(2, '0');
  clock.textContent = `${remaining < 0 ? '+' : ''}${minutes}:${seconds}`;
  const stateLabel = $('#focus-state');
  if (stateLabel) {
    stateLabel.textContent = timer.paused
      ? '已暂停'
      : remaining < 0
        ? '已超时，收个尾'
        : `${pomodoroModeLabel(timer.mode)}中`;
  }
  const ring = $('#focus-ring');
  if (ring) ring.style.setProperty('--progress', `${Math.min(100, (elapsedSec / totalSec) * 100)}`);
  document.title = `${clock.textContent} · ${pomodoroModeLabel(timer.mode)}`;
  if (remaining <= 0 && !timer.finished && !timer.paused) {
    timer.finished = true;
    finishPomodoro();
  }
}

function playPomodoroSound() {
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  if (!pomodoro.sound) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      const context = new AudioContext();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.08, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.35);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.35);
    }
    navigator.vibrate?.(120);
  } catch (error) {
    // 提示音失败不影响计时。
  }
}

async function finishPomodoro() {
  const timer = learningState.timer;
  if (!timer) return;
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  const elapsedSeconds = Math.max(0, Math.round(timerElapsedMs(timer) / 1000));
  const wasFocus = timer.mode === 'focus';
  try {
    if (wasFocus && timer.focusId) {
      await api(`/learning/focus/${timer.focusId}/stop`, {
        method: 'POST',
        body: { completed: true, elapsed_seconds: elapsedSeconds },
      });
    }
  } catch (error) {
    toast(error.message, 'error');
  }
  stopLearningTimer();
  learningState.timer = null;
  if (wasFocus) {
    pomodoro.done = (pomodoro.done || 0) + 1;
    const longBreak = pomodoro.round >= pomodoro.roundsBeforeLong;
    pomodoro.mode = longBreak ? 'long' : 'short';
    pomodoro.round = longBreak ? 1 : pomodoro.round + 1;
    toast(longBreak ? '完成一轮，进入长休息。' : '完成一个番茄，短暂休息一下。');
  } else {
    pomodoro.mode = 'focus';
    toast('休息结束，回来继续。');
  }
  savePomodoro();
  playPomodoroSound();
  await renderLearningPage();
  if (pomodoro.autoNext) {
    if (wasFocus) startBreakTimer(pomodoro.mode);
    else startFocus('', pomodoro.focusMin);
  }
}

async function startFocus(taskId = '', plannedMin = 25) {
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  try {
    const data = await api('/learning/focus/start', {
      method: 'POST',
      body: { task_id: taskId || null, planned_min: Number(plannedMin) || pomodoro.focusMin || 25 },
    });
    startLearningTimer(data.item, false);
    toast('专注开始，先只做这一件事。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function startPomodoro() {
  const pomodoro = learningState.pomodoro || defaultPomodoro();
  if (learningState.timer) return;
  if (pomodoro.mode === 'short' || pomodoro.mode === 'long') {
    startBreakTimer(pomodoro.mode);
    return;
  }
  const taskId = $('#focus-task-select')?.value || '';
  const planned = Number($('#focus-plan-select')?.value || pomodoro.focusMin);
  await startFocus(taskId, planned);
}

function pausePomodoro() {
  const timer = learningState.timer;
  if (!timer || timer.paused) return;
  timer.accumulatedMs = timerElapsedMs(timer);
  timer.paused = true;
  updateLearningTimerUI();
  renderLearningContent();
}

function resumePomodoro() {
  const timer = learningState.timer;
  if (!timer || !timer.paused) return;
  timer.startedAt = Date.now();
  timer.paused = false;
  updateLearningTimerUI();
  renderLearningContent();
}

async function stopPomodoro() {
  const timer = learningState.timer;
  if (!timer) return;
  const elapsedSeconds = Math.max(0, Math.round(timerElapsedMs(timer) / 1000));
  try {
    if (timer.focusId) {
      await api(`/learning/focus/${timer.focusId}/stop`, {
        method: 'POST',
        body: { completed: false, elapsed_seconds: elapsedSeconds },
      });
    }
  } catch (error) {
    toast(error.message, 'error');
  }
  stopLearningTimer();
  learningState.timer = null;
  learningState.pomodoro.mode = 'focus';
  toast('已结束，本次专注记录已保存。');
  await renderLearningPage();
}

async function skipPomodoro() {
  const timer = learningState.timer;
  if (!timer) return;
  const elapsedSeconds = Math.max(0, Math.round(timerElapsedMs(timer) / 1000));
  const pomodoro = learningState.pomodoro;
  try {
    if (timer.focusId) {
      await api(`/learning/focus/${timer.focusId}/stop`, {
        method: 'POST',
        body: { completed: false, elapsed_seconds: elapsedSeconds },
      });
    }
  } catch (error) {
    toast(error.message, 'error');
  }
  stopLearningTimer();
  learningState.timer = null;
  pomodoro.mode = timer.mode === 'focus' ? 'short' : 'focus';
  savePomodoro();
  await renderLearningPage();
}

async function stopFocus() {
  return stopPomodoro();
}

/* ---------------- 任务清单 ---------------- */

async function addExam() {
  const course = $('#exam-course')?.value.trim() || '';
  const examDate = $('#exam-date')?.value || '';
  if (!course || !examDate) {
    toast('请填写课程名和考试日期。');
    return;
  }
  try {
    await api('/learning/exams', {
      method: 'POST',
      body: {
        course_name: course,
        exam_date: examDate,
        start_time: $('#exam-time')?.value.trim() || '',
        location: $('#exam-location')?.value.trim() || '',
        note: $('#exam-note')?.value.trim() || '',
      },
    });
    toast('考试已添加，点“生成计划”倒推复习任务。');
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function planExam(examId) {
  try {
    const data = await api(`/learning/exams/${examId}/plan`, { method: 'POST' });
    toast(`已生成 ${data.generated_days} 天复习计划。`);
    await renderLearningPage();
    learningState.tab = 'exam';
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteExam(examId) {
  if (!window.confirm('删除这场考试？未完成的复习任务也会删除。')) return;
  try {
    await api(`/learning/exams/${examId}`, { method: 'DELETE' });
    toast('考试已删除。');
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function openAssignmentImport() {
  learningState.assignmentImage = '';
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">ASSIGNMENTS</span><h2>从作业导入</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <p class="learning-hint">上传作业截图，或粘贴老师发的作业通知；AI 只负责提取，导入前你可以改。</p>
      <label class="file-drop">
        <input type="file" id="assignment-file" accept="image/png,image/jpeg,image/webp" />
        <span>${icon('upload')} 选择作业截图</span>
        <small>JPG/PNG/WebP，最大 12MB</small>
      </label>
      <div id="assignment-preview" class="question-preview"></div>
      <textarea id="assignment-text" class="learning-textarea" rows="5" placeholder="或者粘贴作业通知：高等数学 P45 第 1-5 题，下周三交…"></textarea>
      <button type="button" class="primary-btn" data-learning-action="extract-assignments">${icon('spark')} 提取作业</button>
      <div id="assignment-drafts"></div>
    </div>`);
}

function readAssignmentFile(input) {
  const file = input.files?.[0];
  if (!file) return;
  if (file.size > 12 * 1024 * 1024) {
    toast('图片不能超过 12MB。', 'error');
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    learningState.assignmentImage = String(reader.result || '');
    const preview = $('#assignment-preview');
    if (preview) {
      preview.classList.add('has-image');
      preview.innerHTML = `<img src="${learningState.assignmentImage}" alt="作业预览" />`;
    }
  };
  reader.readAsDataURL(file);
}

async function extractAssignments() {
  const text = $('#assignment-text')?.value.trim() || '';
  if (!text && !learningState.assignmentImage) {
    toast('上传作业截图或粘贴作业通知。');
    return;
  }
  try {
    const data = await api('/learning/assignments/extract', {
      method: 'POST',
      body: { text: text || null, image_base64: learningState.assignmentImage || null },
    });
    learningState.assignmentDrafts = data.items || [];
    renderAssignmentDrafts();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function renderAssignmentDrafts() {
  const box = $('#assignment-drafts');
  if (!box) return;
  const items = learningState.assignmentDrafts || [];
  if (!items.length) {
    box.innerHTML = '<p class="muted-text">没有提取到作业。</p>';
    return;
  }
  box.innerHTML = `
    <div class="parsed-list">
      ${items.map((item, index) => `
        <div class="parsed-row assignment-row" data-assignment-index="${index}">
          <input class="text-input assignment-title" value="${escapeAttr(item.title)}" />
          <div class="learning-form-row">
            <input class="text-input assignment-course" placeholder="课程" value="${escapeAttr(item.course || '')}" />
            <input class="text-input assignment-due" type="date" value="${escapeAttr(item.due_date)}" />
          </div>
          <small>${escapeHtml(item.detail || '')}</small>
        </div>`).join('')}
    </div>
    <button type="button" class="primary-btn" data-learning-action="import-assignments">${icon('check')} 导入任务清单</button>`;
}

async function importAssignments() {
  const rows = Array.from(document.querySelectorAll('.assignment-row'));
  const tasks = rows.map((row) => {
    const title = row.querySelector('.assignment-title').value.trim() || '作业';
    const course = row.querySelector('.assignment-course').value.trim();
    return {
      title: course ? `${course}：${title}` : title,
      detail: row.querySelector('small')?.textContent || '',
      duration_min: 60,
      priority: 'medium',
      start_date: new Date().toISOString().slice(0, 10),
      due_date: row.querySelector('.assignment-due').value || new Date().toISOString().slice(0, 10),
    };
  });
  if (!tasks.length) return;
  try {
    await api('/learning/tasks', { method: 'POST', body: { tasks } });
    toast(`已导入 ${tasks.length} 项作业。`);
    closeDrawer();
    await renderLearningPage();
    learningState.tab = 'tasks';
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function parsePlan() {
  const text = $('#plan-input')?.value.trim();
  if (!text) {
    toast('先写一句今天的计划。');
    return;
  }
  try {
    const useModel = Boolean($('#plan-use-model')?.checked);
    const data = await api('/learning/tasks/parse', {
      method: 'POST',
      body: { text, use_model: useModel },
    });
    learningState.parsed = data.items || [];
    learningState.parseMode = data.mode || (useModel ? 'model' : 'rule');
    renderParsedPreview();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function renderParsedPreview() {
  const box = $('#parsed-preview');
  if (!box) return;
  if (!learningState.parsed.length) {
    box.innerHTML = `
      <p class="muted-text">没有解析出任务，可以换个写法，或手动新建一条。</p>
      <button type="button" class="ghost-btn" data-learning-action="add-parsed">+ 新建一条</button>`;
    return;
  }
  box.innerHTML = `
    <p class="learning-hint">${learningState.parseMode === 'model' ? '模型提炼' : '本地规则'} · ${learningState.parsed.length} 条，请逐条检查后再导入。</p>
    <div class="parsed-list">
      ${learningState.parsed
        .map(
          (task, index) => `
        <div class="parsed-row" data-parsed-index="${index}">
          <div class="parsed-row-head">
            <input class="text-input parsed-title" value="${escapeAttr(task.title)}" />
            <button type="button" class="text-btn task-delete" data-learning-action="remove-parsed" data-parsed-index="${index}">删除</button>
          </div>
          <div class="learning-form-row">
            <input class="text-input parsed-duration" type="number" min="5" max="600" value="${task.duration_min}" /> 分钟
            <select class="select-input parsed-priority">
              ${['high', 'medium', 'low', 'none'].map((key) => `<option value="${key}" ${task.priority === key ? 'selected' : ''}>${PRIORITY_LABEL[key]}</option>`).join('')}
            </select>
          </div>
          <div class="learning-form-row parsed-date-row">
            <label>开始 <input class="text-input parsed-start" type="date" value="${escapeAttr(task.start_date || '')}" /></label>
            <label>截止 <input class="text-input parsed-due" type="date" value="${escapeAttr(task.due_date)}" /></label>
            <label>提醒 <input class="text-input parsed-remind" type="datetime-local" /></label>
          </div>
          <small>${escapeHtml(task.detail || '')}</small>
        </div>`
        )
        .join('')}
    </div>
    <div class="learning-form-row">
      <button type="button" class="ghost-btn" data-learning-action="add-parsed">+ 新建一条</button>
      <button type="button" class="primary-btn" data-learning-action="import-tasks">${icon('check')} 导入今日清单</button>
    </div>`;
}

function removeParsedDraft(index) {
  learningState.parsed.splice(Number(index), 1);
  renderParsedPreview();
}

function addParsedDraft() {
  const today = new Date().toISOString().slice(0, 10);
  learningState.parsed.push({
    title: '新任务',
    detail: '',
    duration_min: 60,
    priority: 'none',
    start_date: today,
    due_date: today,
    remind_at: null,
  });
  renderParsedPreview();
}

function openCreateTask() {
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">NEW TASK</span><h2>新建任务</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <input id="new-task-title" class="text-input" placeholder="任务名称" />
      <div class="learning-form-row">
        <label>预计 <input id="new-task-duration" class="text-input" type="number" min="5" max="600" value="60" /> 分钟</label>
        <select id="new-task-priority" class="select-input">
          <option value="high">高优先级</option>
          <option value="medium">中优先级</option>
          <option value="low">低优先级</option>
          <option value="none" selected>无优先级</option>
        </select>
      </div>
      <label>截止 <input id="new-task-due" class="text-input" type="date" value="${new Date().toISOString().slice(0, 10)}" /></label>
      <button type="button" class="primary-btn" data-learning-action="save-new-task">保存任务</button>
    </div>`);
}

async function saveNewTask() {
  const title = $('#new-task-title')?.value.trim() || '';
  if (!title) {
    toast('先写任务名称。');
    return;
  }
  const today = new Date().toISOString().slice(0, 10);
  try {
    await api('/learning/tasks', {
      method: 'POST',
      body: {
        tasks: [
          {
            title,
            detail: '',
            duration_min: Number($('#new-task-duration')?.value) || 60,
            priority: $('#new-task-priority')?.value || 'none',
            start_date: today,
            due_date: $('#new-task-due')?.value || today,
            remind_at: null,
          },
        ],
      },
    });
    closeDrawer();
    toast('任务已新建。');
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteTask(taskId) {
  if (!window.confirm('删除这条任务？删除后不会出现在清单里。')) return;
  try {
    await api(`/learning/tasks/${taskId}`, { method: 'DELETE' });
    toast('任务已删除。');
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function importParsedTasks() {
  const rows = Array.from(document.querySelectorAll('.parsed-row'));
  const tasks = rows.map((row) => ({
    title: row.querySelector('.parsed-title').value.trim() || '学习任务',
    detail: row.querySelector('small')?.textContent || '',
    duration_min: Number(row.querySelector('.parsed-duration').value) || 60,
    priority: row.querySelector('.parsed-priority').value,
    start_date: row.querySelector('.parsed-start').value || new Date().toISOString().slice(0, 10),
    due_date: row.querySelector('.parsed-due').value || new Date().toISOString().slice(0, 10),
    remind_at: row.querySelector('.parsed-remind').value || null,
  }));
  if (!tasks.length) return;
  try {
    await api('/learning/tasks', { method: 'POST', body: { tasks } });
    toast('任务已导入今日清单。');
    await renderLearningPage();
    learningState.tab = 'tasks';
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function toggleTask(taskId, status) {
  try {
    await api(`/learning/tasks/${taskId}`, { method: 'PATCH', body: { status } });
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------------- 错题本 ---------------- */

async function createLibrary() {
  const name = $('#new-library-name')?.value.trim();
  const subject = $('#new-library-subject')?.value.trim() || '';
  if (!name) {
    toast('先给错题本起个名字。');
    return;
  }
  try {
    const lib = await api('/learning/libraries', { method: 'POST', body: { name, subject } });
    learningState.activeLibraryId = lib.id;
    toast('错题本已创建。');
    await reloadLibraries();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function reloadLibraries() {
  const data = await api('/learning/libraries');
  learningState.libraries = data.items || [];
  if (learningState.activeLibraryId) await loadQuestions();
  renderLearningContent();
}

async function selectLibrary(libraryId) {
  learningState.activeLibraryId = libraryId;
  await loadQuestions();
  renderLearningContent();
}

async function loadQuestions() {
  if (!learningState.activeLibraryId) return;
  const data = await api(`/learning/questions?library_id=${encodeURIComponent(learningState.activeLibraryId)}`);
  learningState.questions = data.items || [];
}

async function deleteQuestion(questionId) {
  if (!window.confirm('删除这道错题？会先移入回收站，保留 7 天，可恢复。')) return;
  try {
    await api(`/learning/questions/${questionId}`, { method: 'DELETE' });
    learningState.questions = learningState.questions.filter((item) => item.id !== questionId);
    toast('已移入回收站，7 天内可恢复。');
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function trashQuestionHTML(question) {
  const remain = question.purge_at
    ? Math.max(0, Math.ceil((new Date(question.purge_at).getTime() - Date.now()) / 86400000))
    : 7;
  return `
    <article class="trash-item">
      ${question.image_url ? `<img src="${question.image_url}" alt="题目图" />` : ''}
      <div class="trash-item-main">
        <div class="question-rich">${renderRichText(question.question_text)}</div>
        <small>删除于 ${escapeHtml((question.deleted_at || '').slice(0, 16).replace('T', ' '))} · 还剩 ${remain} 天</small>
      </div>
      <div class="question-actions">
        <button type="button" class="ghost-btn" data-learning-action="restore-question" data-question-id="${escapeAttr(question.id)}">恢复</button>
        <button type="button" class="text-btn task-delete" data-learning-action="purge-question" data-question-id="${escapeAttr(question.id)}">彻底删除</button>
      </div>
    </article>`;
}

async function openQuestionTrash() {
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">RECYCLE BIN</span><h2>错题回收站</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body"><p class="learning-hint">删除的错题会保留 7 天，之后自动彻底删除。</p><div id="question-trash-list"><p class="muted-text">加载中…</p></div></div>`);
  try {
    const data = await api('/learning/questions/trash');
    learningState.trashQuestions = data.items || [];
    const box = $('#question-trash-list');
    if (box) {
      box.innerHTML = learningState.trashQuestions.length
        ? learningState.trashQuestions.map((question) => trashQuestionHTML(question)).join('')
        : '<p class="muted-text">回收站是空的。</p>';
    }
  } catch (error) {
    const box = $('#question-trash-list');
    if (box) box.innerHTML = `<p class="muted-text">${escapeHtml(error.message)}</p>`;
  }
}

async function deleteLibrary(libraryId) {
  if (!window.confirm('删除这个错题本？会移入「错题本回收站」，保留 7 天，可恢复。')) return;
  try {
    await api(`/learning/libraries/${libraryId}`, { method: 'DELETE' });
    learningState.libraries = learningState.libraries.filter((item) => item.id !== libraryId);
    if (learningState.activeLibraryId === libraryId) {
      learningState.activeLibraryId = learningState.libraries[0]?.id || '';
      learningState.questions = [];
      if (learningState.activeLibraryId) await loadQuestions();
    }
    toast('错题本已移入回收站，7 天内可恢复。');
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function trashLibraryHTML(library) {
  const remain = library.purge_at
    ? Math.max(0, Math.ceil((new Date(library.purge_at).getTime() - Date.now()) / 86400000))
    : 7;
  return `
    <article class="trash-item">
      <span class="library-icon">${icon('book')}</span>
      <div class="trash-item-main">
        <p>${escapeHtml(library.name)}</p>
        <small>${escapeHtml(library.subject || '未设学科')} · ${library.question_count || 0} 道题 · 还剩 ${remain} 天</small>
      </div>
      <div class="question-actions">
        <button type="button" class="ghost-btn" data-learning-action="restore-library" data-library-id="${escapeAttr(library.id)}">恢复</button>
        <button type="button" class="text-btn task-delete" data-learning-action="purge-library" data-library-id="${escapeAttr(library.id)}">彻底删除</button>
      </div>
    </article>`;
}

async function openLibraryTrash() {
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">RECYCLE BIN</span><h2>错题本回收站</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <p class="learning-hint">错题本和题目回收站是分开的。这里是整个错题本，保留 7 天。</p>
      <div id="library-trash-list"><p class="muted-text">加载中…</p></div>
    </div>`);
  try {
    const data = await api('/learning/libraries/trash');
    const items = data.items || [];
    const box = $('#library-trash-list');
    if (box) {
      box.innerHTML = items.length
        ? items.map((library) => trashLibraryHTML(library)).join('')
        : '<p class="muted-text">错题本回收站是空的。</p>';
    }
  } catch (error) {
    const box = $('#library-trash-list');
    if (box) box.innerHTML = `<p class="muted-text">${escapeHtml(error.message)}</p>`;
  }
}

async function restoreLibrary(libraryId) {
  try {
    await api(`/learning/libraries/${libraryId}/restore`, { method: 'POST' });
    const data = await api('/learning/libraries');
    learningState.libraries = data.items || [];
    learningState.activeLibraryId = libraryId;
    await loadQuestions();
    toast('错题本已恢复。');
    await openLibraryTrash();
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function purgeLibrary(libraryId) {
  if (!window.confirm('彻底删除这个错题本及其中的题目？此操作不可恢复。')) return;
  try {
    await api(`/learning/libraries/${libraryId}/permanent`, { method: 'DELETE' });
    toast('错题本已彻底删除。');
    await openLibraryTrash();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function restoreQuestion(questionId) {
  try {
    await api(`/learning/questions/${questionId}/restore`, { method: 'POST' });
    toast('已恢复到错题本。');
    await loadQuestions();
    await openQuestionTrash();
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function purgeQuestion(questionId) {
  if (!window.confirm('彻底删除后无法恢复，确定吗？')) return;
  try {
    await api(`/learning/questions/${questionId}/permanent`, { method: 'DELETE' });
    toast('已彻底删除。');
    await openQuestionTrash();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function readQuestionFile(input) {
  const file = input.files?.[0];
  if (!file) return;
  if (file.size > 12 * 1024 * 1024) {
    toast('图片不能超过 12MB。', 'error');
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    learningState.imageData = String(reader.result || '');
    const preview = $('#question-preview');
    if (preview) {
      preview.classList.add('has-image');
      preview.innerHTML = `<img src="${learningState.imageData}" alt="题目预览" />`;
    }
  };
  reader.readAsDataURL(file);
}

function openRecognitionTokens() {
  const current = Number(learningState.recognitionTokens) || 16384;
  const presets = [
    [2048, '节省', '较快，适合清晰小题'],
    [4096, '较快', '简单题/节省额度'],
    [8192, '复杂', '多步解析/公式较多的题'],
    [16384, '常用', '大多数题目推荐'],
    [32768, '极大', '最慢且消耗最高，慎重'],
  ];
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">RECOGNITION LIMIT</span><h2>识别 token 上限</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <div class="notice-box">${icon('shield')} 这是<strong>每次上传</strong>的生成上限，不是累计余额；下一次上传会重新从所选值开始。数值越大，等待时间和模型费用通常越高。</div>
      <div class="recognition-presets">
        ${presets.map(([value, label, desc]) => `
          <button type="button" class="recognition-preset ${current === value ? 'is-active' : ''}" data-learning-action="recognition-token" data-token="${value}">
            <strong>${value}</strong><span>${label}（${desc}）</span>
          </button>`).join('')}
      </div>
      <label class="login-field">
        <span>也可以自己填（512–32768）</span>
        <input id="recognition-custom-tokens" class="text-input" type="number" min="512" max="32768" step="256" value="${current}" />
      </label>
      <label class="login-field">
        <span>快捷选择</span>
        <select id="recognition-token-select" class="select-input">
          ${presets.map(([value, label]) => `<option value="${value}" ${current === value ? 'selected' : ''}>${value} · ${label}</option>`).join('')}
        </select>
      </label>
      <div class="learning-form-row">
        <button type="button" class="primary-btn" data-learning-action="save-recognition-tokens">保存上限</button>
      </div>
    </div>`);
}

function selectRecognitionToken(value) {
  const input = $('#recognition-custom-tokens');
  if (input) input.value = String(value);
  document.querySelectorAll('.recognition-preset').forEach((button) => {
    button.classList.toggle('is-active', Number(button.dataset.token) === Number(value));
  });
}

function saveRecognitionTokens() {
  const value = Number($('#recognition-custom-tokens')?.value || 0);
  if (!value || value < 512 || value > 32768) {
    toast('请填写 512 到 32768 之间的数字。');
    return;
  }
  learningState.recognitionTokens = Math.round(value);
  localStorage.setItem('zhixing-recognition-tokens', String(learningState.recognitionTokens));
  closeDrawer();
  toast(`识别上限已设为 ${learningState.recognitionTokens} tokens，下次上传生效。`);
  renderLearningContent();
}

async function uploadQuestion() {
  if (!learningState.activeLibraryId) {
    toast('先选一个错题本。');
    return;
  }
  if (learningState.overview?.vision_mode !== 'http') {
    toast('请先在「模型设置」里配置你自己的 API Key。');
    openVisionSettings();
    return;
  }
  const text = $('#question-text')?.value.trim() || '';
  if (!learningState.imageData && !text) {
    toast('上传图片或输入题干。');
    return;
  }
  try {
    const question = await api('/learning/questions', {
      method: 'POST',
      body: {
        library_id: learningState.activeLibraryId,
        text: text || null,
        image_base64: learningState.imageData || null,
        max_tokens: learningState.recognitionTokens || 16384,
      },
    });
    learningState.imageData = '';
    learningState.questions.unshift(question);
    toast('识别完成，题目已保存。');
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function viewQuestionSolution(questionId) {
  try {
    const question = await api(`/learning/questions/${questionId}/solution`);
    openDrawer(`
      <div class="drawer-head"><div><span class="eyebrow">SOLUTION</span><h2>解答与解析</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
      <div class="drawer-body solution-body">
        ${question.image_url ? `<img class="practice-image" src="${question.image_url}" alt="题目图" />` : ''}
        <div class="solution-question">${renderRichText(question.question_text)}</div>
        <div class="solution-answer">
          <span class="eyebrow">ANSWER</span>
          <div class="rich-analysis">${renderRichText(question.reference_answer || '暂无参考答案')}</div>
        </div>
        <div class="solution-analysis">
          <div class="section-head"><div><h3>详细解析</h3></div></div>
          <div class="rich-analysis">${renderRichText(question.analysis || '这道题还没有保存解析。')}</div>
        </div>
        <div class="learning-form-row">
          <button type="button" class="primary-btn" data-learning-action="practice" data-question-id="${escapeAttr(question.id)}">开始练习</button>
        </div>
      </div>`);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function practiceQuestion(questionId) {
  const question =
    learningState.questions.find((item) => item.id === questionId) ||
    learningState.reviewQuestions.find((item) => item.id === questionId);
  if (!question) return;
  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">PRACTICE</span><h2>错题练习</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body practice-body">
      ${question.image_url ? `<img class="practice-image" src="${question.image_url}" alt="题目图" />` : ''}
      <div class="practice-question">${renderRichText(question.question_text)}</div>
      ${question.options?.length ? `<ul class="practice-options">${question.options.map((option) => `<li>${renderRichText(option)}</li>`).join('')}</ul>` : ''}
      <p class="learning-hint">答案和解析在提交前不会显示。先写下你的思路或最终答案。</p>
      <textarea id="practice-answer" class="learning-textarea" rows="6" placeholder="写下你的解答/思路…"></textarea>
      <div class="learning-form-row">
        <button type="button" class="primary-btn" data-learning-action="submit-attempt" data-question-id="${escapeAttr(question.id)}">提交批改</button>
        <button type="button" class="ghost-btn" data-learning-action="submit-teachback" data-question-id="${escapeAttr(question.id)}">用自己的话复述</button>
      </div>
      <div id="practice-feedback"></div>
    </div>`);
}

async function submitTeachback(questionId) {
  const explanation = $('#practice-answer')?.value || '';
  if (!explanation.trim()) {
    toast('先用自己的话写一遍思路。');
    return;
  }
  try {
    const data = await api(`/learning/questions/${questionId}/teachback`, {
      method: 'POST',
      body: { explanation },
    });
    const box = $('#practice-feedback');
    if (box) {
      box.innerHTML = `
        <div class="practice-result ${data.verdict === 'understood' ? 'correct' : 'incorrect'}">
          <div class="section-head"><div><h3>复述检查</h3><span>${Math.round((data.score || 0) * 100)} 分</span></div></div>
          <p>${escapeHtml(data.feedback || '')}</p>
          ${data.good?.length ? `<p class="learning-hint">讲对了：${data.good.map(escapeHtml).join('；')}</p>` : ''}
          ${data.missing?.length ? `<p class="learning-hint">漏掉了：${data.missing.map(escapeHtml).join('；')}</p>` : ''}
          ${data.misconceptions?.length ? `<p class="learning-hint danger-text">讲错了：${data.misconceptions.map(escapeHtml).join('；')}</p>` : ''}
        </div>`;
    }
    toast('复述检查完成。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function submitAttempt(questionId) {
  const answer = $('#practice-answer')?.value || '';
  try {
    const data = await api(`/learning/questions/${questionId}/attempts`, {
      method: 'POST',
      body: { answer },
    });
    const feedback = data.feedback || {};
    const box = $('#practice-feedback');
    if (box) {
      box.innerHTML = `
        <div class="practice-result ${feedback.correctness || ''}">
          <div class="section-head"><div><h3>${feedback.correctness === 'correct' ? '答对了' : feedback.correctness === 'partial' ? '部分正确' : '再想想'}</h3><span>${Math.round((feedback.score || 0) * 100)} 分</span></div></div>
          <p>${escapeHtml(feedback.feedback || '')}</p>
          <div class="feedback-steps">${(feedback.steps || []).map((step) => `<div><b>${escapeHtml(step.step)}</b><span>${escapeHtml(step.comment)}</span></div>`).join('')}</div>
          <button type="button" class="ghost-btn" data-learning-action="view-solution" data-question-id="${escapeAttr(questionId)}">查看完整解析</button>
        </div>`;
    }
    if (data.review?.due) {
      const box = $('#practice-feedback');
      if (box) {
        box.insertAdjacentHTML(
          'beforeend',
          `<p class="learning-hint">下次复习：${escapeHtml(data.review.due)}（连对 ${data.review.streak} 次）</p>`
        );
      }
      try {
        const review = await api('/learning/review');
        learningState.reviewQuestions = review.items || [];
        learningState.reviewSummary = review.summary || null;
      } catch (error) {
        // 复习列表刷新失败不影响本次批改结果。
      }
    }
    toast('批改完成，看看步骤反馈。');
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------------- 课程资料 ---------------- */

async function openCourseMaterials(courseId, query = '') {
  const course = (learningState.courses || []).find((item) => item.id === courseId);
  try {
    const data = await api(`/learning/courses/${courseId}/materials`);
    const items = data.items || [];
    let searchItems = [];
    if (query) {
      const result = await api(
        `/learning/courses/${courseId}/materials/search?q=${encodeURIComponent(query)}`
      );
      searchItems = result.items || [];
    }
    openDrawer(`
      <div class="drawer-head"><div><span class="eyebrow">COURSE MATERIALS</span><h2>${escapeHtml(course?.name || '课程资料')}</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
      <div class="drawer-body">
        <div class="learning-form-row">
          <input id="material-search" class="text-input" placeholder="在这门课的资料里搜…" value="${escapeAttr(query)}" />
          <button type="button" class="ghost-btn" data-learning-action="search-materials" data-course-id="${escapeAttr(courseId)}">搜索</button>
        </div>
        ${query ? `<div class="material-list">${searchItems.length ? searchItems.map((item) => `<div class="material-item"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.snippet)}</p><small>相关度 ${item.score}</small></div>`).join('') : '<p class="muted-text">没有匹配资料。</p>'}</div>` : ''}
        <div class="section-head"><div><h3>资料列表</h3><p class="section-sub">按课程隔离；只给当前学生使用。</p></div><span class="learning-count">${items.length} 份</span></div>
        <div class="material-list">
          ${items.length ? items.map((item) => `<div class="material-item"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.content.slice(0, 300))}</p></div>`).join('') : '<p class="muted-text">还没有资料，粘贴课件/笔记或知识点。</p>'}
        </div>
        <details class="course-form" open>
          <summary>+ 新增课程资料</summary>
          <input id="material-title" class="text-input" placeholder="标题，如：第二章 导数" />
          <textarea id="material-content" class="learning-textarea" rows="6" placeholder="粘贴课件文字、笔记或知识点…"></textarea>
          <div class="learning-form-row">
            <button type="button" class="primary-btn" data-learning-action="save-material" data-course-id="${escapeAttr(courseId)}">保存资料</button>
            <label class="ghost-btn file-inline">${icon('upload')} 上传 Word/PDF/TXT
              <input type="file" id="material-file" accept=".docx,.pdf,.txt,.md" hidden data-course-id="${escapeAttr(courseId)}" />
            </label>
          </div>
        </details>
      </div>`);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function uploadCourseMaterial(input) {
  const file = input.files?.[0];
  const courseId = input.dataset.courseId;
  if (!file || !courseId) return;
  if (file.size > 10 * 1024 * 1024) {
    toast('文件不能超过 10MB。', 'error');
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    const raw = String(reader.result || '');
    const base64 = raw.includes(',') ? raw.split(',', 2)[1] : raw;
    try {
      await api(`/learning/courses/${courseId}/materials/upload`, {
        method: 'POST',
        body: { filename: file.name, content_base64: base64 },
      });
      toast('资料已从文件导入。');
      await openCourseMaterials(courseId);
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  reader.readAsDataURL(file);
}

async function saveCourseMaterial(courseId) {
  const title = $('#material-title')?.value.trim() || '课程资料';
  const content = $('#material-content')?.value.trim() || '';
  if (!content) {
    toast('先粘贴资料内容。');
    return;
  }
  try {
    await api(`/learning/courses/${courseId}/materials`, {
      method: 'POST',
      body: { title, content },
    });
    toast('课程资料已保存。');
    await openCourseMaterials(courseId);
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------------- 日历 / 课程 ---------------- */

async function loadLearningCalendar() {
  try {
    const data = await api(`/learning/calendar?year=${learningState.calendarYear}&month=${learningState.calendarMonth}`);
    learningState.calendar = data;
    learningState.semesterStart = data.semester_start || '';
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function saveSemesterStart(value) {
  try {
    const data = await api('/learning/calendar/settings', {
      method: 'PUT',
      body: { start_date: value || '' },
    });
    learningState.semesterStart = data.semester_start || '';
    learningState.calendar = null;
    learningState.calendarWeek = null;
    toast(value ? `学期开始日期已设为 ${value}` : '已清空学期开始日期');
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function saveCalendarSettings() {
  const settings = learningState.calendarSettings || defaultCalendarSettings();
  settings.view = learningState.calendarView || 'month';
  localStorage.setItem(CALENDAR_SETTINGS_KEY, JSON.stringify(settings));
}

async function loadLearningWeek() {
  try {
    const settings = learningState.calendarSettings || defaultCalendarSettings();
    const start = learningState.weekStartDate || startOfWeekISO(todayISO(), settings.weekStart);
    learningState.weekStartDate = start;
    const data = await api(`/learning/calendar/week?start=${encodeURIComponent(start)}`);
    learningState.calendarWeek = data;
    learningState.semesterStart = data.semester_start || '';
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function shiftCalendar(delta) {
  if (learningState.calendarView === 'week') {
    learningState.weekStartDate = addDaysISO(learningState.weekStartDate, delta * 7);
    learningState.calendarWeek = null;
    await loadLearningWeek();
    return;
  }
  let month = learningState.calendarMonth + delta;
  let year = learningState.calendarYear;
  if (month < 1) { month = 12; year -= 1; }
  if (month > 12) { month = 1; year += 1; }
  learningState.calendarMonth = month;
  learningState.calendarYear = year;
  await loadLearningCalendar();
}

async function importCourses() {
  const text = $('#course-import')?.value.trim();
  if (!text) {
    toast('先粘贴课程表。');
    return;
  }
  try {
    const data = await api('/learning/courses/import', { method: 'POST', body: { text } });
    const courses = await api('/learning/courses');
    learningState.courses = courses.items || [];
    learningState.calendar = null;
    learningState.calendarWeek = null;
    toast(`已导入 ${data.count || 0} 门课。`);
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function addCourse() {
  const name = $('#course-name')?.value.trim();
  if (!name) {
    toast('先填课程名。');
    return;
  }
  try {
    await api('/learning/courses', {
      method: 'POST',
      body: {
        name,
        weekday: Number($('#course-weekday')?.value || 1),
        start_time: $('#course-start')?.value || '08:00',
        end_time: $('#course-end')?.value || '09:40',
        location: $('#course-location')?.value || '',
        weeks: $('#course-weeks')?.value.trim() || '',
        week_parity: $('#course-parity')?.value || 'all',
        assignment: $('#course-assignment')?.value || '',
      },
    });
    const data = await api('/learning/courses');
    learningState.courses = data.items || [];
    learningState.calendar = null;
    learningState.calendarWeek = null;
    toast('课程已加入课程表。');
    renderLearningContent();
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------------- 事件 ---------------- */

async function handleLearningClick(event) {
  const target = event.target;
  const tab = target.closest('[data-learning-tab]');
  if (tab) {
    learningState.tab = tab.dataset.learningTab;
    $$('.learning-tab').forEach((item) => item.classList.toggle('is-active', item === tab));
    if (learningState.tab === 'calendar') {
      if (learningState.calendarView === 'week' && !learningState.calendarWeek) {
        await loadLearningWeek();
      } else if (learningState.calendarView !== 'week' && !learningState.calendar) {
        await loadLearningCalendar();
      } else {
        renderLearningContent();
      }
    } else {
      renderLearningContent();
    }
    return;
  }
  const action = target.closest('[data-learning-action]');
  if (!action) return;
  event.preventDefault();
  const kind = action.dataset.learningAction;
  if (kind === 'start-focus' || kind === 'start-pomodoro') {
    await startPomodoro();
  } else if (kind === 'stop-focus' || kind === 'stop-pomodoro') {
    await stopPomodoro();
  } else if (kind === 'pause-pomodoro') {
    pausePomodoro();
  } else if (kind === 'resume-pomodoro') {
    resumePomodoro();
  } else if (kind === 'skip-pomodoro') {
    await skipPomodoro();
  } else if (kind === 'pomodoro-mode') {
    learningState.pomodoro.mode = action.dataset.mode;
    renderLearningContent();
  } else if (kind === 'start-task') {
    await startFocus(action.dataset.taskId, action.dataset.duration);
  } else if (kind === 'add-exam') {
    await addExam();
  } else if (kind === 'plan-exam') {
    await planExam(action.dataset.examId);
  } else if (kind === 'delete-exam') {
    await deleteExam(action.dataset.examId);
  } else if (kind === 'assignment-import') {
    openAssignmentImport();
  } else if (kind === 'extract-assignments') {
    await extractAssignments();
  } else if (kind === 'import-assignments') {
    await importAssignments();
  } else if (kind === 'add-parsed') {
    addParsedDraft();
  } else if (kind === 'remove-parsed') {
    removeParsedDraft(action.dataset.parsedIndex);
  } else if (kind === 'create-task') {
    openCreateTask();
  } else if (kind === 'save-new-task') {
    await saveNewTask();
  } else if (kind === 'parse-plan') {
    await parsePlan();
  } else if (kind === 'import-tasks') {
    await importParsedTasks();
  } else if (kind === 'toggle-task') {
    await toggleTask(action.dataset.taskId, action.dataset.taskStatus);
  } else if (kind === 'delete-task') {
    await deleteTask(action.dataset.taskId);
  } else if (kind === 'create-library') {
    await createLibrary();
  } else if (kind === 'select-library') {
    await selectLibrary(action.dataset.libraryId);
  } else if (kind === 'upload-question') {
    await uploadQuestion();
  } else if (kind === 'library-trash') {
    await openLibraryTrash();
  } else if (kind === 'delete-library') {
    await deleteLibrary(action.dataset.libraryId);
  } else if (kind === 'restore-library') {
    await restoreLibrary(action.dataset.libraryId);
  } else if (kind === 'purge-library') {
    await purgeLibrary(action.dataset.libraryId);
  } else if (kind === 'question-trash') {
    await openQuestionTrash();
  } else if (kind === 'delete-question') {
    await deleteQuestion(action.dataset.questionId);
  } else if (kind === 'restore-question') {
    await restoreQuestion(action.dataset.questionId);
  } else if (kind === 'purge-question') {
    await purgeQuestion(action.dataset.questionId);
  } else if (kind === 'view-solution') {
    await viewQuestionSolution(action.dataset.questionId);
  } else if (kind === 'practice') {
    practiceQuestion(action.dataset.questionId);
  } else if (kind === 'review-practice') {
    practiceQuestion(action.dataset.questionId);
  } else if (kind === 'submit-attempt') {
    await submitAttempt(action.dataset.questionId);
  } else if (kind === 'submit-teachback') {
    await submitTeachback(action.dataset.questionId);
  } else if (kind === 'toggle-settings') {
    const panel = document.getElementById(action.dataset.target);
    if (panel) panel.hidden = !panel.hidden;
  } else if (kind === 'calendar-mode') {
    learningState.calendarMode = action.dataset.mode === 'tasks' ? 'tasks' : 'courses';
    renderLearningContent();
  } else if (kind === 'calendar-view') {
    const view = action.dataset.view === 'week' ? 'week' : 'month';
    learningState.calendarView = view;
    learningState.calendarSettings.view = view;
    saveCalendarSettings();
    if (view === 'week') {
      learningState.weekStartDate = startOfWeekISO(
        todayISO(),
        learningState.calendarSettings.weekStart
      );
      learningState.calendarWeek = null;
    }
    renderLearningContent();
  } else if (kind === 'reset-calendar-settings') {
    learningState.calendarSettings = defaultCalendarSettings();
    learningState.calendarView = 'month';
    learningState.weekStartDate = startOfWeekISO(todayISO(), 'monday');
    learningState.calendarWeek = null;
    saveCalendarSettings();
    renderLearningContent();
  } else if (kind === 'calendar-prev') {
    await shiftCalendar(-1);
  } else if (kind === 'calendar-next') {
    await shiftCalendar(1);
  } else if (kind === 'course-materials') {
    await openCourseMaterials(action.dataset.courseId);
  } else if (kind === 'save-material') {
    await saveCourseMaterial(action.dataset.courseId);
  } else if (kind === 'search-materials') {
    await openCourseMaterials(action.dataset.courseId, $('#material-search')?.value.trim() || '');
  } else if (kind === 'add-course') {
    await addCourse();
  } else if (kind === 'import-courses') {
    await importCourses();
  } else if (kind === 'recognition-tokens') {
    openRecognitionTokens();
  } else if (kind === 'recognition-token') {
    selectRecognitionToken(action.dataset.token);
  } else if (kind === 'save-recognition-tokens') {
    saveRecognitionTokens();
  } else if (kind === 'vision-settings') {
    openVisionSettings();
  } else if (kind === 'save-profile') {
    await saveProfile();
  } else if (kind === 'test-profile') {
    await testProfile(action.dataset.profileId);
  } else if (kind === 'activate-profile') {
    await activateProfile(action.dataset.profileId);
  } else if (kind === 'delete-profile') {
    await deleteProfile(action.dataset.profileId);
  }
}

function providerLabel(provider) {
  return MODEL_PRESETS[provider]?.label || provider || '自定义';
}

function profileStatusLabel(status) {
  if (status === 'ok') return '已连通';
  if (status === 'error') return '连接失败';
  return '待测试';
}

function profileStatusClass(status) {
  if (status === 'ok') return 'profile-ok';
  if (status === 'error') return 'profile-error';
  return 'profile-unknown';
}

async function openVisionSettings() {
  let profiles = [];
  try {
    const data = await api('/learning/model-profiles');
    profiles = data.items || [];
  } catch (error) {
    toast(error.message, 'error');
    return;
  }
  const cards = profiles
    .map(
      (profile) => `
      <div class="model-profile-card ${profile.is_active ? 'is-active' : ''}">
        <div class="profile-card-head">
          <div>
            <strong>${escapeHtml(profile.name || profile.provider)}</strong>
            <span>${escapeHtml(providerLabel(profile.provider))} · ${escapeHtml(profile.model)}</span>
          </div>
          <div class="profile-badges">
            ${profile.is_active ? '<span class="profile-badge active">当前启用</span>' : ''}
            <span class="profile-badge ${profileStatusClass(profile.status)}">${profileStatusLabel(profile.status)}</span>
          </div>
        </div>
        <p class="profile-note">${escapeHtml(profile.note || '未填写备注')}</p>
        <div class="profile-meta">
          <span>${escapeHtml(profile.key_masked || '—')} · 指纹 ${escapeHtml(profile.key_fingerprint || '—')}</span>
          ${profile.official_url ? `<a href="${escapeAttr(profile.official_url)}" target="_blank" rel="noreferrer">官网 ↗</a>` : ''}
        </div>
        <div class="profile-actions">
          <button type="button" class="ghost-btn" data-learning-action="test-profile" data-profile-id="${escapeAttr(profile.id)}">测试连接</button>
          ${!profile.is_active ? `<button type="button" class="primary-btn" data-learning-action="activate-profile" data-profile-id="${escapeAttr(profile.id)}" ${profile.status !== 'ok' ? 'disabled title="测试通过后才能启用"' : ''}>设为当前</button>` : ''}
          <button type="button" class="ghost-btn profile-logout" data-learning-action="delete-profile" data-profile-id="${escapeAttr(profile.id)}">删除</button>
        </div>
      </div>`
    )
    .join('');

  openDrawer(`
    <div class="drawer-head"><div><span class="eyebrow">MODEL PROFILES</span><h2>我的模型配置</h2></div><button type="button" class="icon-btn" data-close-drawer>${icon('close')}</button></div>
    <div class="drawer-body">
      <div class="notice-box">${icon('shield')} API Key 只写一次：保存后任何页面/API 都不返回明文，不能覆盖；更换必须删除旧配置再录入。连接方式固定为“学校服务器代理”，不提供路由开关。</div>
      <div class="profile-list">${cards || '<p class="muted-text">还没有配置。先新增一个。</p>'}</div>
      <details class="course-form" ${profiles.length ? '' : 'open'}>
        <summary>+ 新增模型配置</summary>
        <label class="login-field"><span>供应商预设</span>
          <select id="profile-provider" class="select-input">
            <option value="deepseek">DeepSeek</option>
            <option value="qwen">Qwen-VL</option>
            <option value="custom">自定义</option>
          </select>
        </label>
        <div class="learning-form-row">
          <input id="profile-name" class="text-input" placeholder="配置名称（可选，如：我的 DeepSeek 高数）" />
          <input id="profile-note" class="text-input" placeholder="备注/用途（如：高数拍题）" />
        </div>
        <input id="profile-official" class="text-input" placeholder="官网链接（可选）" />
        <input id="profile-key" class="text-input" type="password" placeholder="API Key（保存后不可查看）" autocomplete="off" />
        <div class="learning-form-row">
          <input id="profile-model" class="text-input" placeholder="模型，如 deepseek-flash" value="deepseek-flash" />
          <input id="profile-base" class="text-input" placeholder="Base URL" value="https://api.deepseek.com" />
        </div>
        <button type="button" class="primary-btn" data-learning-action="save-profile">保存配置</button>
        <p class="learning-hint">保存后先点“测试连接”；只有测试通过的配置才能设为当前。</p>
      </details>
    </div>`);
}

function applyProfilePreset(provider) {
  const preset = MODEL_PRESETS[provider] || MODEL_PRESETS.custom;
  const set = (id, value) => {
    const el = $(id);
    if (el) el.value = value || '';
  };
  set('#profile-model', preset.model);
  set('#profile-base', preset.base);
  set('#profile-official', preset.official);
  set('#profile-note', preset.note);
  const name = $('#profile-name');
  if (name && !name.value) name.value = preset.label === '自定义' ? '' : `${preset.label} 学习模型`;
}

async function saveProfile() {
  const provider = $('#profile-provider')?.value || 'custom';
  const preset = MODEL_PRESETS[provider] || MODEL_PRESETS.custom;
  const apiKey = $('#profile-key')?.value.trim() || '';
  const baseUrl = $('#profile-base')?.value.trim() || '';
  const model = $('#profile-model')?.value.trim() || '';
  if (!apiKey) {
    toast('新增配置必须填写 API Key。');
    return;
  }
  if (!baseUrl || !model) {
    toast('请填写 Base URL 和模型名称。');
    return;
  }
  try {
    const profile = await api('/learning/model-profiles', {
      method: 'POST',
      body: {
        name: $('#profile-name')?.value.trim() || preset.label,
        provider,
        model,
        base_url: baseUrl,
        official_url: $('#profile-official')?.value.trim() || '',
        note: $('#profile-note')?.value.trim() || '',
        api_key: apiKey,
      },
    });
    toast('配置已保存。请先测试连接，再设为当前。');
    await openVisionSettings();
    const testButton = document.querySelector(`[data-learning-action="test-profile"][data-profile-id="${profile.id}"]`);
    if (testButton) testButton.focus();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function testProfile(profileId) {
  try {
    const data = await api(`/learning/model-profiles/${profileId}/test`, { method: 'POST' });
    toast(`连接正常：${data.model} · ${data.latency_ms}ms`);
    await openVisionSettings();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function activateProfile(profileId) {
  try {
    await api(`/learning/model-profiles/${profileId}/activate`, { method: 'POST' });
    toast('已切换当前配置。');
    closeDrawer();
    await renderLearningPage();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteProfile(profileId) {
  if (!window.confirm('删除配置后 Key 不可恢复，只能重新录入。确认删除？')) return;
  try {
    await api(`/learning/model-profiles/${profileId}`, { method: 'DELETE' });
    toast('配置已删除。');
    await openVisionSettings();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function handleLearningChange(event) {
  const target = event.target;
  if (target.id === 'recognition-token-select') {
    selectRecognitionToken(target.value);
    return;
  }
  if (target.matches('[data-pomodoro-setting]')) {
    const key = target.dataset.pomodoroSetting;
    const pomodoro = learningState.pomodoro || defaultPomodoro();
    pomodoro[key] = target.type === 'checkbox' ? target.checked : Number(target.value);
    if (key === 'focusMin' || key === 'shortMin' || key === 'longMin') {
      pomodoro[key] = Math.max(1, pomodoro[key] || 1);
    }
    if (key === 'roundsBeforeLong') {
      pomodoro.roundsBeforeLong = Math.max(2, Math.min(8, pomodoro[key] || 4));
    }
    savePomodoro();
    if (!learningState.timer) renderLearningContent();
    return;
  }
  if (target.matches('[data-semester-start]')) {
    saveSemesterStart(target.value);
    return;
  }
  if (target.matches('[data-calendar-setting]')) {
    const key = target.dataset.calendarSetting;
    const settings = learningState.calendarSettings || defaultCalendarSettings();
    if (target.type === 'checkbox') {
      settings[key] = target.checked;
    } else if (target.type === 'range' || target.type === 'number') {
      settings[key] = Number(target.value);
    } else {
      settings[key] = target.value;
    }
    learningState.calendarSettings = settings;
    if (key === 'weekStart') {
      learningState.weekStartDate = startOfWeekISO(todayISO(), settings.weekStart);
      learningState.calendarWeek = null;
    }
    saveCalendarSettings();
    renderLearningContent();
    return;
  }
  if (target.id === 'question-file') {
    readQuestionFile(target);
    return;
  }
  if (target.id === 'assignment-file') {
    readAssignmentFile(target);
    return;
  }
  if (target.id === 'material-file') {
    uploadCourseMaterial(target);
    return;
  }
  if (target.id === 'profile-provider') {
    applyProfilePreset(target.value);
    return;
  }
  if (target.id === 'focus-task-select') {
    const task = learningState.tasks.find((item) => item.id === target.value);
    const plan = $('#focus-plan-select');
    if (task && plan) plan.value = String(task.duration_min);
    return;
  }
  if (target.matches('[data-task-priority]')) {
    const taskId = target.dataset.taskPriority;
    api(`/learning/tasks/${taskId}`, { method: 'PATCH', body: { priority: target.value } })
      .then(() => renderLearningPage())
      .catch((error) => toast(error.message, 'error'));
  }
}

document.addEventListener('click', handleLearningClick);
document.addEventListener('change', handleLearningChange);
