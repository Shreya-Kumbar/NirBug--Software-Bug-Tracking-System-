/* NirBug front-end: a small single-page app in plain JavaScript (no framework).
   - Talks to the Flask REST API with fetch() + Bearer token
   - Every value coming from the server is HTML-escaped (esc) to prevent XSS
*/
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = () => window.lucide && lucide.createIcons();

const state = { token: sessionStorage.getItem('token'), user: null, projects: [], users: [], charts: [] };
const STATUSES = ['NEW','ASSIGNED','IN_PROGRESS','FIXED','IN_TESTING','VERIFIED','CLOSED','REOPENED','REJECTED','DUPLICATE'];
const BOARD = ['NEW','ASSIGNED','IN_PROGRESS','FIXED','IN_TESTING','VERIFIED','CLOSED'];
const SEVS = ['CRITICAL','HIGH','MEDIUM','LOW'];
const isMgr = () => ['ADMIN','MANAGER'].includes(state.user?.role);

// ------------------------------------------------------------------ API helper
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json', ...(state.token ? { Authorization: 'Bearer ' + state.token } : {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && state.token && !path.startsWith('/auth')) { logout(); }
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function toast(msg, ok = true) {
  const t = $('#toast'); t.textContent = msg;
  t.className = `fixed bottom-6 right-6 z-[60] px-4 py-3 rounded-xl shadow-lg text-white fade-in ${ok ? 'bg-emerald-600' : 'bg-rose-600'}`;
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add('hidden'), 3000);
}
const sev = s => `<span class="badge sev-${esc(s)}">${esc(s)}</span>`;
const st = s => `<span class="badge st st-${esc(s)}">${esc(String(s).replace('_',' '))}</span>`;
const initials = n => esc((n || '?').split('_').pop().slice(0, 2).toUpperCase());
const ago = d => { if (!d) return ''; const s = (Date.now() - new Date(d.replace(' ', 'T') + 'Z')) / 1000;
  return s < 60 ? 'just now' : s < 3600 ? Math.floor(s/60) + 'm ago' : s < 86400 ? Math.floor(s/3600) + 'h ago' : Math.floor(s/86400) + 'd ago'; };

// ------------------------------------------------------------------ theme
function applyTheme(t) { document.documentElement.classList.toggle('dark', t === 'dark'); try { localStorage.setItem('theme', t); } catch {} }
let savedTheme = 'light'; try { savedTheme = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); } catch {}
applyTheme(savedTheme);
$('#theme-btn').onclick = () => applyTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark');

// ------------------------------------------------------------------ auth
let registerMode = false;
['admin','manager','dev_bob','tester','reporter'].forEach(u => {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'btn !py-1 !px-2 text-xs'; b.textContent = u;
  b.onclick = () => { $('[name=username]').value = u; $('[name=password]').value = 'Demo@1234'; };
  $('#demo-users').append(b);
});
$('#auth-switch').onclick = e => {
  e.preventDefault(); registerMode = !registerMode;
  $('#email-row').classList.toggle('hidden', !registerMode);
  $('#auth-title').textContent = registerMode ? 'Create account' : 'Welcome back';
  $('#auth-sub').textContent = registerMode ? 'New accounts start with the Reporter role' : 'Sign in to your workspace';
  $('#auth-btn').textContent = registerMode ? 'Create account' : 'Sign in';
  $('#auth-switch-text').textContent = registerMode ? 'Have an account?' : 'No account?';
  $('#auth-switch').textContent = registerMode ? 'Sign in' : 'Create one';
};
$('#auth-form').onsubmit = async e => {
  e.preventDefault(); const f = new FormData(e.target); const err = $('#auth-error'); err.classList.add('hidden');
  try {
    if (registerMode) {
      await api('/auth/register', { method: 'POST', body: { username: f.get('username'), email: f.get('email'), password: f.get('password') } });
      toast('Account created – please sign in'); $('#auth-switch').click(); return;
    }
    const r = await api('/auth/login', { method: 'POST', body: { username: f.get('username'), password: f.get('password') } });
    state.token = r.token; sessionStorage.setItem('token', r.token); boot();
  } catch (ex) { err.textContent = ex.message; err.classList.remove('hidden'); }
};
function logout() { sessionStorage.removeItem('token'); state.token = null; location.reload(); }
$('#logout').onclick = logout;

// ------------------------------------------------------------------ shell / routing
const VIEWS = { dashboard: 'Dashboard', triage: 'Triage & Assign', work: 'My Work', qa: 'QA Queue', reports: 'My Reports',
  bugs: 'All Bugs', board: 'Board', releases: 'Releases', team: 'Team', audit: 'Audit Log' };
// Each role sees its own menu (first entry = home page after login)
const NAV = {
  REPORTER:  [['reports', 'file-text', 'My Reports'], ['bugs', 'list-checks', 'All Bugs'], ['releases', 'rocket', 'Releases']],
  DEVELOPER: [['work', 'wrench', 'My Work'], ['board', 'kanban', 'Board'], ['bugs', 'list-checks', 'All Bugs'], ['releases', 'rocket', 'Releases']],
  TESTER:    [['qa', 'flask-conical', 'QA Queue'], ['board', 'kanban', 'Board'], ['bugs', 'list-checks', 'All Bugs'], ['reports', 'file-text', 'My Reports'], ['releases', 'rocket', 'Releases']],
  MANAGER:   [['dashboard', 'layout-dashboard', 'Dashboard'], ['triage', 'user-plus', 'Triage & Assign'], ['board', 'kanban', 'Board'], ['bugs', 'list-checks', 'All Bugs'], ['releases', 'rocket', 'Releases'], ['team', 'users', 'Team'], ['audit', 'scroll-text', 'Audit Log']],
  ADMIN:     [['dashboard', 'layout-dashboard', 'Dashboard'], ['team', 'users', 'Users & Roles'], ['triage', 'user-plus', 'Triage & Assign'], ['board', 'kanban', 'Board'], ['bugs', 'list-checks', 'All Bugs'], ['releases', 'rocket', 'Releases'], ['audit', 'scroll-text', 'Audit Log']],
};
const myNav = () => NAV[state.user?.role] || NAV.REPORTER;
function buildNav() {
  $('#nav').innerHTML = myNav().map(([v, ic, label]) => `<a data-view="${v}" class="nav-link"><i data-lucide="${ic}"></i>${label}</a>`).join('');
  $$('.nav-link').forEach(a => a.onclick = () => { location.hash = a.dataset.view; $('#sidebar').classList.add('-translate-x-full'); });
}
$('#menu-btn').onclick = () => $('#sidebar').classList.toggle('-translate-x-full');
window.onhashchange = route;
$('#new-bug-btn').onclick = openNewBug;
$('#global-search').onkeydown = e => { if (e.key === 'Enter') { state.search = e.target.value; location.hash = 'bugs'; route(); } };

async function boot() {
  if (!state.token) { $('#auth-screen').classList.remove('hidden'); icons(); return; }
  try { state.user = await api('/auth/me'); } catch { return; }
  [state.projects, state.users] = await Promise.all([api('/projects'), api('/users')]);
  $('#auth-screen').classList.add('hidden'); $('#app-screen').classList.remove('hidden');
  $('#me-name').textContent = state.user.username; $('#me-role').textContent = state.user.role;
  $('#me-avatar').innerHTML = initials(state.user.username);
  buildNav();
  loadNotifications(); setInterval(loadNotifications, 30000);
  route();
}
function route() {
  const allowed = myNav().map(n => n[0]);
  const v = (location.hash || '').slice(1);
  const view = allowed.includes(v) ? v : allowed[0];   // unknown / not-allowed page -> role's home page
  $('#view-title').textContent = myNav().find(n => n[0] === view)[2];
  $$('.nav-link').forEach(a => a.classList.toggle('active', a.dataset.view === view));
  state.charts.forEach(c => c.destroy()); state.charts = [];
  $('#view').innerHTML = '<div class="space-y-4"><div class="skeleton h-28"></div><div class="grid grid-cols-2 xl:grid-cols-4 gap-4"><div class="skeleton h-24"></div><div class="skeleton h-24"></div><div class="skeleton h-24"></div><div class="skeleton h-24"></div></div><div class="skeleton h-64"></div></div>';
  ({ dashboard: viewDashboard, triage: viewTriage, work: viewWork, qa: viewQA, reports: viewReports,
     bugs: () => viewBugs(false), board: viewBoard,
     releases: viewReleases, team: viewTeam, audit: viewAudit })[view]().then(() => { icons(); fx(); }).catch(e => toast(e.message, false));
}

// ------------------------------------------------------------------ notifications
async function loadNotifications() {
  const list = await api('/notifications').catch(() => []);
  $('#notif-dot').classList.toggle('hidden', !list.some(n => !n.is_read));
  $('#notif-panel').innerHTML = list.length ? list.map(n => `<div class="p-3 rounded-lg text-sm ${n.is_read ? '' : 'bg-brand-50 dark:bg-slate-800'}">
      <p>${esc(n.message)}</p><p class="text-xs text-slate-400 mt-1">${ago(n.created_at)}</p></div>`).join('')
    : '<p class="p-4 text-sm text-slate-400">No notifications</p>';
}
$('#notif-btn').onclick = async () => { $('#notif-panel').classList.toggle('hidden'); await api('/notifications/read', { method: 'POST' }); $('#notif-dot').classList.add('hidden'); };

// ------------------------------------------------------------------ dashboard
async function viewDashboard() {
  const [d, recent] = await Promise.all([api('/dashboard'), api('/bugs')]);
  const pct = (n) => d.total ? Math.round(100 * n / d.total) : 0;
  const stat = (label, val, icon, color, sub) => `<div class="card hoverable stat-card px-5 py-4" style="--accent:${color}">
     <div class="flex items-center justify-between"><p class="text-sm text-slate-400">${label}</p><i data-lucide="${icon}" class="w-4 h-4" style="color:${color}"></i></div>
     <p class="text-3xl font-bold mt-2 tracking-tight" data-count="${esc(val ?? '')}">${val == null ? '–' : 0}</p>
     <p class="text-xs text-slate-500 mt-1">${sub}</p></div>`;
  $('#view').innerHTML = `
  <div class="space-y-6 max-w-7xl">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div><h2 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Welcome back, ${esc(state.user.username)}</h2>
        <p class="text-sm text-slate-400 mt-1">Here's what's happening across your projects.</p></div>
      <div class="flex items-center gap-2 text-sm">
        ${d.critical_open ? `<span class="pill pill-danger"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>${d.critical_open} critical open</span>` : `<span class="pill pill-ok">No critical bugs</span>`}
        <span class="pill">AI agreement ${d.ai_agreement ?? '–'}%</span>
      </div>
    </div>
    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
      ${stat('Total bugs', d.total, 'bug', '#f9a8d4', 'Across all projects')}
      ${stat('Open', d.open, 'circle-dot', '#fbbf24', `${pct(d.open)}% of total`)}
      ${stat('Resolved', d.closed, 'circle-check', '#34d399', `${pct(d.closed)}% resolution rate`)}
      ${stat('Avg. days to close', d.mttr_days ?? 0, 'timer', '#7dd3fc', 'Mean time to resolution')}
    </div>
    <div class="grid lg:grid-cols-3 gap-4 stagger">
      <div class="card hoverable glow-panel p-5" style="--accent:#fdba74"><div class="flex justify-between items-center mb-4"><h3 class="font-semibold text-sm">By severity</h3><span class="chip"><i data-lucide="pie-chart"></i></span></div>
        <div class="relative"><canvas id="c-sev" height="230"></canvas>
        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none" style="bottom:42px"><p class="text-2xl font-bold">${d.total}</p><p class="text-xs text-slate-400">bugs</p></div></div></div>
      <div class="card hoverable glow-panel p-5 lg:col-span-2" style="--accent:#93c5fd"><div class="flex justify-between items-center mb-4"><h3 class="font-semibold text-sm">By status</h3><span class="chip"><i data-lucide="bar-chart-3"></i></span></div><canvas id="c-status" height="115"></canvas></div>
    </div>
    <div class="grid lg:grid-cols-5 gap-4 stagger">
      <div class="card hoverable glow-panel p-5 lg:col-span-3" style="--accent:#5eead4"><div class="flex justify-between items-center mb-4"><h3 class="font-semibold text-sm">Developer workload</h3><span class="flex items-center gap-3"><span class="text-xs text-slate-500">Severity-weighted</span><span class="chip"><i data-lucide="users"></i></span></span></div>
        <div class="space-y-4">${d.workload.map(w => `<div class="flex items-center gap-3">
          <div class="avatar !w-8 !h-8 text-[11px]">${initials(w.username)}</div>
          <div class="flex-1"><div class="flex justify-between text-sm"><span class="font-medium">${esc(w.username)}</span><span class="text-slate-500 text-xs">${w.open_bugs} open · load ${w.load_score}</span></div>
          <div class="mt-1.5 h-1.5 rounded-full bg-white/[.06] overflow-hidden"><div class="h-full bar-fill rounded-full bg-indigo-400" style="width:${Math.min(100, w.load_score * 8)}%"></div></div></div></div>`).join('')}</div></div>
      <div class="card hoverable glow-panel p-5 lg:col-span-2" style="--accent:#7dd3fc"><div class="flex justify-between items-center mb-4"><h3 class="font-semibold text-sm">Recent bugs</h3><span class="flex items-center gap-3"><a href="#bugs" class="text-xs text-indigo-400 hover:underline">View all</a><span class="chip"><i data-lucide="activity"></i></span></span></div>
        <div class="space-y-2">${recent.slice(0, 5).map(b => `<div class="recent-row" data-id="${b.id}">
          <span class="sev-dot sev-dot-${esc(b.severity)}"></span>
          <div class="flex-1 min-w-0"><p class="text-sm font-semibold truncate">${esc(b.title)}</p><p class="text-[11px] text-slate-400">#${b.id} · ${esc(b.component)} · ${ago(b.updated_at)}</p></div>${st(b.status)}</div>`).join('') || '<p class="text-sm text-slate-400">No bugs yet.</p>'}</div></div>
    </div>
  </div>`;
  $$('.recent-row').forEach(r => r.onclick = () => openBug(r.dataset.id));
  const dark = document.documentElement.classList.contains('dark'); Chart.defaults.color = dark ? '#94a3b8' : '#64748b';
  Chart.defaults.font.family = 'Inter'; Chart.defaults.borderColor = dark ? 'rgba(148,163,184,.08)' : 'rgba(100,116,139,.12)';
  state.charts.push(new Chart($('#c-sev'), { type: 'doughnut', data: { labels: SEVS,
    datasets: [{ data: SEVS.map(s => d.by_severity[s] || 0), backgroundColor: dark ? ['#fb7185cc','#fdba74cc','#fde68acc','#6ee7b7cc'] : ['#fda4af','#fdba74','#fde68a','#86efac'], borderWidth: 0, hoverOffset: 4, spacing: 2, borderRadius: 4 }] },
    options: { cutout: '72%', animation: { animateRotate: true, duration: 1200 }, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } } } } }));
  const ctx = $('#c-status').getContext('2d'), g = ctx.createLinearGradient(0, 0, 0, 260);
  g.addColorStop(0, dark ? '#c4b5fd' : '#c4b5fd'); g.addColorStop(1, dark ? '#818cf8' : '#a5b4fc');
  state.charts.push(new Chart($('#c-status'), { type: 'bar', data: { labels: STATUSES.map(s => s.replace('_',' ')),
    datasets: [{ data: STATUSES.map(s => d.by_status[s] || 0), backgroundColor: g, hoverBackgroundColor: '#c4b5fd', borderRadius: 6, borderSkipped: false, maxBarThickness: 36 }] },
    options: { animation: { duration: 1200, easing: 'easeOutQuart' }, plugins: { legend: { display: false } },
      scales: { y: { ticks: { precision: 0 }, grid: { color: 'rgba(148,163,184,.08)' } }, x: { grid: { display: false } } } } }));
}

// ------------------------------------------------------------------ bug list
async function viewBugs(mine) {
  const filters = state.filters || {};
  const opt = (arr, sel) => '<option value="">All</option>' + arr.map(v => `<option ${v == sel ? 'selected' : ''} value="${esc(v)}">${esc(v)}</option>`).join('');
  const q = new URLSearchParams({ ...filters, ...(mine ? { mine: 1 } : {}), q: state.search || '' });
  const bugs = await api('/bugs?' + q);
  $('#view').innerHTML = `<div class="fade-in space-y-4">
    <div class="card p-4 flex flex-wrap gap-3 items-end">
      <div><label class="lbl">Project</label><select class="inp" data-f="project_id"><option value="">All</option>${state.projects.map(p => `<option value="${p.id}" ${p.id == filters.project_id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
      <div><label class="lbl">Status</label><select class="inp" data-f="status">${opt(STATUSES, filters.status)}</select></div>
      <div><label class="lbl">Severity</label><select class="inp" data-f="severity">${opt(SEVS, filters.severity)}</select></div>
      ${state.search ? `<button class="btn" id="clear-search">“${esc(state.search)}” ✕</button>` : ''}
      <div class="flex-1 text-right text-sm text-slate-500">${bugs.length} bug(s)</div>
    </div>
    <div class="card overflow-x-auto">${bugs.length ? `<table class="tbl"><thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Priority</th><th>Status</th><th>Assignee</th><th>Component</th><th>Updated</th></tr></thead><tbody class="stagger">
      ${bugs.map(b => `<tr data-id="${b.id}"><td class="text-slate-400 font-mono">#${b.id}</td><td class="font-semibold max-w-md">${esc(b.title)}<div class="text-xs text-slate-400 font-normal">${esc(b.project_name)}</div></td>
      <td>${sev(b.severity)}</td><td><span class="font-bold">${esc(b.priority)}</span></td><td>${st(b.status)}</td>
      <td>${b.assignee_name ? `<span class="flex items-center gap-2"><span class="avatar !w-6 !h-6 text-[10px]">${initials(b.assignee_name)}</span>${esc(b.assignee_name)}</span>` : '<span class="text-slate-400">Unassigned</span>'}</td>
      <td><span class="text-xs px-2 py-1 rounded bg-slate-100 dark:bg-slate-800">${esc(b.component)}</span></td><td class="text-slate-400 text-xs">${ago(b.updated_at)}</td></tr>`).join('')}
    </tbody></table>` : `<div class="p-16 text-center text-slate-400"><i data-lucide="party-popper" class="w-10 h-10 mx-auto mb-3"></i>No bugs here.</div>`}</div></div>`;
  $$('[data-f]').forEach(s => s.onchange = () => { state.filters = { ...filters, [s.dataset.f]: s.value }; route(); });
  $('#clear-search') && ($('#clear-search').onclick = () => { state.search = ''; $('#global-search').value = ''; route(); });
  $$('tbody tr').forEach(tr => tr.onclick = () => openBug(tr.dataset.id));
}

// ------------------------------------------------------------------ kanban board (drag & drop)
async function viewBoard() {
  const bugs = await api('/bugs');
  $('#view').innerHTML = `<div class="fade-in"><p class="text-sm text-slate-500 mb-4">Drag a card to another column to change its status. Only transitions allowed by the bug life-cycle and your role succeed.</p>
   <div class="flex gap-4 overflow-x-auto pb-4">${BOARD.map(s => `<div class="kanban-col flex-1">
     <div class="flex items-center justify-between mb-3 px-1"><span class="font-bold text-sm">${st(s)}</span><span class="text-xs text-slate-400">${bugs.filter(b => b.status === s).length}</span></div>
     <div class="space-y-3 min-h-[200px] p-1 rounded-xl stagger" data-col="${s}">${bugs.filter(b => b.status === s).map(b => `
       <div class="card p-3 kcard fade-in" draggable="true" data-id="${b.id}">
         <div class="flex justify-between items-center mb-2"><span class="text-xs font-mono text-slate-400">#${b.id}</span>${sev(b.severity)}</div>
         <p class="text-sm font-semibold leading-snug">${esc(b.title)}</p>
         <div class="flex justify-between items-center mt-3 text-xs text-slate-400"><span>${esc(b.priority)} · ${esc(b.component)}</span>
         ${b.assignee_name ? `<span class="avatar !w-6 !h-6 text-[10px]" title="${esc(b.assignee_name)}">${initials(b.assignee_name)}</span>` : ''}</div></div>`).join('')}</div></div>`).join('')}</div></div>`;
  $$('.kcard').forEach(c => {
    c.ondragstart = e => { e.dataTransfer.setData('id', c.dataset.id); c.classList.add('dragging'); };
    c.ondragend = () => c.classList.remove('dragging');
    c.onclick = () => openBug(c.dataset.id);
  });
  $$('[data-col]').forEach(col => {
    col.ondragover = e => { e.preventDefault(); col.classList.add('drop-hover'); };
    col.ondragleave = () => col.classList.remove('drop-hover');
    col.ondrop = async e => {
      e.preventDefault(); col.classList.remove('drop-hover');
      try { await api(`/bugs/${e.dataTransfer.getData('id')}/status`, { method: 'POST', body: { status: col.dataset.col } }); toast('Status updated'); route(); }
      catch (ex) { toast(ex.message, false); }
    };
  });
}

// ------------------------------------------------------------------ modal helpers
function modal(html) { $('#modal-body').innerHTML = `<button class="absolute top-4 right-4 icon-btn" id="m-close"><i data-lucide="x"></i></button>` + html; $('#modal').classList.remove('hidden'); $('#m-close').onclick = closeModal; icons(); }
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };

// ------------------------------------------------------------------ report a bug (with AI assist)
function openNewBug() {
  const p0 = state.projects[0];
  modal(`<h2 class="text-xl font-bold mb-1">Report a bug</h2><p class="text-sm text-slate-500 mb-5">The AI assistant suggests severity, component and possible duplicates as you type.</p>
  <form id="bug-form" class="grid md:grid-cols-3 gap-4">
    <div class="md:col-span-2 space-y-4">
      <div><label class="lbl">Project</label><select name="project_id" class="inp">${state.projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div>
      <div><label class="lbl">Title</label><input name="title" class="inp" required minlength="5" maxlength="200" placeholder="e.g. App crashes when uploading a photo"></div>
      <div><label class="lbl">Description & steps to reproduce</label><textarea name="description" rows="6" class="inp" required minlength="10" placeholder="1. Go to …&#10;2. Click …&#10;Expected: …&#10;Actual: …"></textarea></div>
      <div class="grid grid-cols-2 gap-3">
        <div><label class="lbl">Severity</label><select name="severity" class="inp"><option value="">Let AI decide</option>${SEVS.map(s => `<option>${s}</option>`).join('')}</select></div>
        <div><label class="lbl">Component</label><input name="component" class="inp" placeholder="auto"></div>
        <div><label class="lbl">Found in version</label><input name="found_in_version" class="inp" placeholder="v1.0"></div>
        <div><label class="lbl">Target release</label><select name="target_release_id" class="inp" id="rel-sel"></select></div>
      </div>
    </div>
    <div class="space-y-3"><div class="rounded-xl p-4 bg-gradient-to-br from-brand-50 to-fuchsia-50 dark:from-slate-800 dark:to-slate-800 text-sm ai-glow" id="ai-box">
      <p class="font-bold flex items-center gap-2"><i data-lucide="sparkles" class="w-4 h-4 text-brand-600"></i>AI Triage</p><p class="text-slate-400 mt-2 text-xs leading-relaxed">This panel is read-only. As you type the <b>Title</b> and <b>Description</b> on the left, the AI will show here:</p>
      <ul class="mt-2 space-y-1 text-xs text-slate-400"><li>• Predicted severity</li><li>• Likely component</li><li>• Possible duplicate bugs</li></ul></div></div>
    <div class="md:col-span-3 flex justify-end gap-2"><button type="button" class="btn" id="cancel-bug">Cancel</button><button class="btn-primary">Submit bug</button></div>
  </form>`);
  const form = $('#bug-form');
  const fillReleases = () => { const p = state.projects.find(p => p.id == form.project_id.value) || p0;
    $('#rel-sel').innerHTML = '<option value="">None</option>' + (p?.releases || []).filter(r => r.status === 'PLANNED').map(r => `<option value="${r.id}">${esc(r.version)}</option>`).join(''); };
  fillReleases(); form.project_id.onchange = () => { fillReleases(); analyze(); };
  $('#cancel-bug').onclick = closeModal;
  let timer; const analyze = () => { clearTimeout(timer); timer = setTimeout(async () => {
    if (form.title.value.length < 5) return;
    const r = await api('/bugs/analyze', { method: 'POST', body: { project_id: form.project_id.value, title: form.title.value, description: form.description.value } });
    $('#ai-box').innerHTML = `<p class="font-bold flex items-center gap-2"><i data-lucide="sparkles" class="w-4 h-4 text-brand-600"></i>AI Triage</p>
      <p class="mt-3 text-slate-500">Predicted severity</p><div class="flex items-center gap-2 mt-1">${sev(r.severity)}<span class="text-xs text-slate-500">${Math.round(r.confidence * 100)}% confident</span></div>
      <p class="mt-3 text-slate-500">Component</p><p class="font-semibold">${esc(r.component)}</p>
      <p class="mt-3 text-slate-500">Possible duplicates</p>${r.duplicates.length ? r.duplicates.map(d => `<div class="mt-1 p-2 rounded-lg bg-amber-100 text-amber-800 text-xs">#${d.id} ${esc(d.title)} <b>${Math.round(d.similarity * 100)}%</b></div>`).join('') : '<p class="text-emerald-600 text-xs">None found ✓</p>'}`;
    icons(); }, 400); };
  form.title.oninput = analyze; form.description.oninput = analyze;
  form.onsubmit = async e => {
    e.preventDefault(); const body = Object.fromEntries(new FormData(form));
    try { const b = await api('/bugs', { method: 'POST', body }); toast(`Bug #${b.id} created (${b.severity}, ${b.priority})`); closeModal(); route(); }
    catch (ex) { toast(ex.message, false); }
  };
}

// ------------------------------------------------------------------ bug detail
async function openBug(id) {
  const b = await api('/bugs/' + id);
  const devs = state.users.filter(u => u.role === 'DEVELOPER');
  modal(`<div class="flex flex-wrap items-center gap-2 mb-2 pr-10"><span class="font-mono text-slate-400">#${b.id}</span>${sev(b.severity)}${st(b.status)}<span class="badge bg-slate-100 dark:bg-slate-800">${esc(b.priority)}</span></div>
  <h2 class="text-2xl font-bold">${esc(b.title)}</h2>
  <p class="text-sm text-slate-500 mt-1">${esc(b.project_name)} · reported by <b>${esc(b.reporter_name)}</b> ${ago(b.created_at)}</p>
  <div class="grid md:grid-cols-3 gap-6 mt-6">
    <div class="md:col-span-2 space-y-6">
      <div class="whitespace-pre-wrap text-sm leading-relaxed p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">${esc(b.description)}</div>
      <div><h3 class="font-bold mb-3">Comments</h3><div class="space-y-3">${b.comments.map(c => `<div class="flex gap-3"><div class="avatar !w-8 !h-8 text-xs">${initials(c.username)}</div>
        <div class="flex-1"><p class="text-sm"><b>${esc(c.username)}</b> <span class="text-xs text-slate-400">${ago(c.created_at)}</span></p><p class="text-sm whitespace-pre-wrap">${esc(c.body)}</p></div></div>`).join('') || '<p class="text-sm text-slate-400">No comments yet.</p>'}</div>
        <form id="c-form" class="mt-3 flex gap-2"><input name="body" class="inp" placeholder="Write a comment…" required maxlength="5000"><button class="btn-primary">Send</button></form></div>
      <div><h3 class="font-bold mb-3">History</h3><ol class="relative border-l border-slate-200 dark:border-slate-700 ml-2 space-y-3">${b.history.map(h => `<li class="ml-4 text-sm"><span class="absolute -left-1.5 w-3 h-3 rounded-full bg-brand-500"></span>
        <b>${esc(h.username || 'system')}</b> changed <i>${esc(h.field)}</i> ${h.old_value ? `from <code>${esc(h.old_value)}</code>` : ''} to <code>${esc(h.new_value)}</code> <span class="text-xs text-slate-400">${ago(h.created_at)}</span></li>`).join('')}</ol></div>
    </div>
    <div class="space-y-4 text-sm">
      <div class="card p-4 space-y-2"><p class="text-slate-500">Assignee</p><p class="font-semibold">${esc(b.assignee_name || 'Unassigned')}</p>
        ${isMgr() ? `<select id="as-sel" class="inp"><option value="">Auto (AI skill + workload)</option>${devs.map(d => `<option value="${d.id}">${esc(d.username)} – ${esc(d.skills)}</option>`).join('')}</select>
        <button class="btn w-full justify-center" id="as-btn"><i data-lucide="user-plus" class="w-4 h-4"></i>Assign</button>` : ''}</div>
      <div class="card p-4 space-y-2"><p class="text-slate-500">Move to</p>${b.allowed_transitions.length ? b.allowed_transitions.map(t => `<button class="btn w-full justify-center" data-to="${t}">${esc(t.replace('_',' '))}</button>`).join('') : '<p class="text-slate-400">No transitions available for your role.</p>'}</div>
      <div class="card p-4 space-y-1"><p class="text-slate-500">Details</p>
        <p>Component: <b>${esc(b.component)}</b></p><p>Found in: <b>${esc(b.found_in_version || '–')}</b></p><p>Target release: <b>${esc(b.target_version || '–')}</b></p>
        <p>AI severity: ${b.ai_severity ? sev(b.ai_severity) + ` <span class="text-xs text-slate-400">${Math.round(b.ai_confidence * 100)}%</span>` : '–'}</p>
        ${b.duplicate_of ? `<p>Duplicate of <b>#${b.duplicate_of}</b></p>` : ''}</div>
    </div></div>`);
  $('#c-form').onsubmit = async e => { e.preventDefault(); try { await api(`/bugs/${id}/comments`, { method: 'POST', body: { body: e.target.body.value } }); openBug(id); } catch (ex) { toast(ex.message, false); } };
  $('#as-btn') && ($('#as-btn').onclick = async () => { try { const v = $('#as-sel').value;
    const r = await api(`/bugs/${id}/assign`, { method: 'POST', body: v ? { assignee_id: +v } : { strategy: 'skill_based' } });
    toast('Assigned to ' + r.assignee_name); openBug(id); route(); } catch (ex) { toast(ex.message, false); } });
  $$('[data-to]').forEach(btn => btn.onclick = async () => {
    const body = { status: btn.dataset.to };
    if (body.status === 'DUPLICATE') { body.duplicate_of = prompt('Original bug id?'); if (!body.duplicate_of) return; }
    try { await api(`/bugs/${id}/status`, { method: 'POST', body }); toast('Moved to ' + body.status); openBug(id); route(); } catch (ex) { toast(ex.message, false); }
  });
}

// ================================================================== ROLE WORKSPACES
// Shared helpers ---------------------------------------------------
async function moveBug(id, status, note, extra = {}) {
  if (note) await api(`/bugs/${id}/comments`, { method: 'POST', body: { body: note } });
  await api(`/bugs/${id}/status`, { method: 'POST', body: { status, ...extra } });
}
/* Ask for a short text (fix note, failure reason ...) in a small modal. Resolves to the text or null. */
function askText(title, label, placeholder, required = true) {
  return new Promise(resolve => {
    modal(`<h2 class="text-xl font-bold mb-1">${esc(title)}</h2><p class="text-sm text-slate-500 mb-4">${esc(label)}</p>
      <form id="ask-form"><textarea name="t" rows="4" class="inp" placeholder="${esc(placeholder)}" ${required ? 'required' : ''}></textarea>
      <div class="flex justify-end gap-2 mt-4"><button type="button" class="btn" id="ask-cancel">Cancel</button><button class="btn-primary">Confirm</button></div></form>`);
    $('#modal-body').style.maxWidth = '520px';
    const done = v => { $('#modal-body').style.maxWidth = ''; closeModal(); resolve(v); };
    $('#ask-cancel').onclick = () => done(null);
    $('#ask-form').onsubmit = e => { e.preventDefault(); done(e.target.t.value.trim()); };
    $('#ask-form textarea').focus();
  });
}
const statTile = (label, n, color, icon) => `<div class="card hoverable stat-card px-5 py-4" style="--accent:${color}">
  <div class="flex items-center justify-between"><p class="text-sm text-slate-400">${label}</p><i data-lucide="${icon}" class="w-4 h-4" style="color:${color}"></i></div>
  <p class="text-3xl font-bold mt-2" data-count="${n}">0</p></div>`;
/* A bug card with action buttons. actions: [{label, icon, kind:'primary'|'ok'|'danger'|'', run:async()=>{}}] */
function workCard(b, actions = [], extra = '') {
  const id = `wc-${b.id}-${Math.random().toString(36).slice(2, 7)}`;
  setTimeout(() => {
    const el = document.getElementById(id); if (!el) return;
    el.querySelector('[data-open]').onclick = () => openBug(b.id);
    el.querySelectorAll('[data-act]').forEach((btn, i) => btn.onclick = async () => {
      btn.disabled = true;
      try { await actions[i].run(); } catch (ex) { toast(ex.message, false); } finally { btn.disabled = false; }
    });
    icons();
  });
  const cls = { primary: 'btn-primary', ok: 'btn btn-ok', danger: 'btn btn-danger', '': 'btn' };
  return `<div class="card work-card p-4" id="${id}">
    <div class="flex items-start gap-3">
      <span class="sev-dot sev-dot-${esc(b.severity)} mt-1.5"></span>
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-center gap-2 text-xs text-slate-400"><span class="font-mono">#${b.id}</span>${sev(b.severity)}<span class="font-bold">${esc(b.priority)}</span>${st(b.status)}<span>· ${esc(b.component)}</span></div>
        <p class="font-semibold mt-1.5 leading-snug cursor-pointer hover:underline" data-open>${esc(b.title)}</p>
        <p class="text-xs text-slate-400 mt-1">${esc(b.project_name)} · reported by ${esc(b.reporter_name)} · ${ago(b.updated_at)}${b.assignee_name ? ` · dev: <b>${esc(b.assignee_name)}</b>` : ''}</p>
        ${extra}
      </div>
    </div>
    ${actions.length ? `<div class="flex flex-wrap gap-2 mt-3 pl-5">${actions.map(a => `<button data-act class="${cls[a.kind || '']} !py-1.5 !px-3 text-sm"><i data-lucide="${a.icon}" class="w-4 h-4"></i>${esc(a.label)}</button>`).join('')}</div>` : ''}
  </div>`;
}
const section = (title, sub, cards, empty) => `<div class="space-y-3">
  <div class="flex items-baseline justify-between"><h3 class="font-semibold">${title} <span class="text-slate-400 font-normal text-sm">(${cards.length})</span></h3><span class="text-xs text-slate-500">${sub}</span></div>
  ${cards.length ? cards.join('') : `<div class="card p-6 text-center text-sm text-slate-400">${empty}</div>`}</div>`;
const pageHead = (title, sub, right = '') => `<div class="flex flex-wrap items-end justify-between gap-4">
  <div><h2 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">${title}</h2><p class="text-sm text-slate-400 mt-1">${sub}</p></div>${right}</div>`;

// DEVELOPER: My Work ------------------------------------------------
async function viewWork() {
  const bugs = await api('/bugs?mine=1');
  const by = s => bugs.filter(b => s.includes(b.status));
  const todo = by(['ASSIGNED', 'REOPENED']), doing = by(['IN_PROGRESS']), qa = by(['FIXED', 'IN_TESTING']), done = by(['VERIFIED', 'CLOSED']);
  const start = b => ({ label: b.status === 'REOPENED' ? 'Restart work' : 'Start work', icon: 'play', kind: 'primary',
    run: async () => { await moveBug(b.id, 'IN_PROGRESS'); toast(`#${b.id} is now IN PROGRESS`); route(); } });
  const fixed = b => ({ label: 'Mark as fixed', icon: 'check', kind: 'ok', run: async () => {
    const note = await askText(`Mark #${b.id} as fixed`, 'Describe what you changed so the tester knows what to verify.', 'e.g. Added null check in login form validation; added unit test.');
    if (note === null) return; await moveBug(b.id, 'FIXED', '🔧 Fix note: ' + note); toast(`#${b.id} sent to QA`); route(); } });
  const comment = b => ({ label: 'Add update', icon: 'message-square', run: async () => {
    const t = await askText(`Update on #${b.id}`, 'Post a progress update visible to the reporter and the team.', 'e.g. Reproduced the issue, root cause is ...');
    if (t) { await api(`/bugs/${b.id}/comments`, { method: 'POST', body: { body: t } }); toast('Update posted'); route(); } } });
  const reopenNote = b => b.status === 'REOPENED' ? `<p class="mt-2 text-xs px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 inline-block">Reopened by QA – check the latest comment for the failure reason</p>` : '';
  $('#view').innerHTML = `<div class="space-y-6 max-w-6xl">
    ${pageHead('My Work', 'Bugs assigned to you. Start working, post updates and send fixes to QA.')}
    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
      ${statTile('To do', todo.length, '#fbbf24', 'inbox')}${statTile('In progress', doing.length, '#a78bfa', 'loader')}
      ${statTile('Waiting for QA', qa.length, '#7dd3fc', 'flask-conical')}${statTile('Done', done.length, '#34d399', 'circle-check')}</div>
    <div class="grid lg:grid-cols-2 gap-6">
      ${section('To do', 'assigned to you – start one', todo.map(b => workCard(b, [start(b)], reopenNote(b))), 'Nothing new assigned to you 🎉')}
      ${section('In progress', 'when done, mark as fixed', doing.map(b => workCard(b, [fixed(b), comment(b)])), 'Start a bug from your To-do list')}
    </div>
    <div class="grid lg:grid-cols-2 gap-6">
      ${section('Waiting for QA', 'tester is verifying your fix', qa.map(b => workCard(b)), 'No fixes waiting for testing')}
      ${section('Done', 'verified / closed', done.slice(0, 6).map(b => workCard(b)), 'No completed bugs yet')}
    </div></div>`;
}

// TESTER: QA Queue --------------------------------------------------
async function viewQA() {
  const bugs = await api('/bugs?statuses=NEW,FIXED,IN_TESTING,VERIFIED');
  const by = s => bugs.filter(b => b.status === s);
  const ready = by('FIXED'), testing = by('IN_TESTING'), verified = by('VERIFIED'), fresh = by('NEW');
  const startT = b => ({ label: 'Start testing', icon: 'flask-conical', kind: 'primary', run: async () => { await moveBug(b.id, 'IN_TESTING'); toast(`Testing #${b.id}`); route(); } });
  const pass = b => ({ label: 'Pass – verified', icon: 'check-check', kind: 'ok', run: async () => {
    const n = await askText(`Verify #${b.id}`, 'Optional: how did you test it?', 'e.g. Tested on Chrome & Edge, login with empty password now shows an error.', false);
    if (n === null) return; await moveBug(b.id, 'VERIFIED', n ? '✅ Test passed: ' + n : '✅ Test passed'); toast(`#${b.id} verified`); route(); } });
  const fail = b => ({ label: 'Fail – reopen', icon: 'x', kind: 'danger', run: async () => {
    const r = await askText(`Reopen #${b.id}`, 'Explain what still fails. The developer will be notified.', 'e.g. Still crashes when the password contains spaces.');
    if (r === null) return; await moveBug(b.id, 'REOPENED', '❌ Test failed: ' + r); toast(`#${b.id} reopened and sent back`); route(); } });
  const close = b => ({ label: 'Close bug', icon: 'archive', run: async () => { await moveBug(b.id, 'CLOSED'); toast(`#${b.id} closed`); route(); } });
  const dup = b => ({ label: 'Mark duplicate', icon: 'copy', run: async () => {
    const o = await askText(`Mark #${b.id} as duplicate`, 'Enter the ID of the original bug (number only).', 'e.g. 8');
    if (!o) return; await moveBug(b.id, 'DUPLICATE', `Duplicate of #${o}`, { duplicate_of: parseInt(o) }); toast(`#${b.id} marked duplicate of #${o}`); route(); } });
  $('#view').innerHTML = `<div class="space-y-6 max-w-6xl">
    ${pageHead('QA Queue', 'Verify developer fixes, reopen failures, close verified bugs and catch duplicates.',
      `<button class="btn-primary" onclick="openNewBug()"><i data-lucide="bug" class="w-4 h-4"></i>Report a bug you found</button>`)}
    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
      ${statTile('Ready to test', ready.length, '#7dd3fc', 'inbox')}${statTile('Testing now', testing.length, '#a78bfa', 'flask-conical')}
      ${statTile('Verified', verified.length, '#34d399', 'check-check')}${statTile('New reports', fresh.length, '#fbbf24', 'sparkles')}</div>
    <div class="grid lg:grid-cols-2 gap-6">
      ${section('Ready to test', 'developer marked these as fixed', ready.map(b => workCard(b, [startT(b)])), 'No fixes waiting – nice!')}
      ${section('Testing now', 'pass or fail each one', testing.map(b => workCard(b, [pass(b), fail(b)])), 'Start testing a bug from the left')}
    </div>
    <div class="grid lg:grid-cols-2 gap-6">
      ${section('Verified – ready to close', 'close once the release is confirmed', verified.map(b => workCard(b, [close(b)])), 'Nothing to close')}
      ${section('New reports – check for duplicates', 'mark duplicates before triage', fresh.map(b => workCard(b, [dup(b)])), 'No new reports')}
    </div></div>`;
}

// MANAGER / ADMIN: Triage & Assign ----------------------------------
async function viewTriage() {
  const [bugs, dash] = await Promise.all([api('/bugs?statuses=NEW,REOPENED,ASSIGNED'), api('/dashboard')]);
  state.users = await api('/users');
  const devs = dash.workload;
  const queue = bugs.filter(b => b.status !== 'ASSIGNED'), assigned = bugs.filter(b => b.status === 'ASSIGNED');
  const devOptions = sel => devs.map(d => `<option value="${d.user_id}" ${d.user_id == sel ? 'selected' : ''}>${esc(d.username)} · ${esc(d.skills || '-')} · load ${d.load_score}</option>`).join('');
  const picker = b => `<div class="mt-3 flex flex-wrap items-center gap-2"><select class="inp !w-auto !py-1.5 text-sm" data-dev="${b.id}">${devOptions(b.assignee_id)}</select></div>`;
  const assign = b => ({ label: 'Assign selected', icon: 'user-check', kind: 'primary', run: async () => {
    const v = document.querySelector(`[data-dev="${b.id}"]`).value;
    const r = await api(`/bugs/${b.id}/assign`, { method: 'POST', body: { assignee_id: +v } }); toast(`#${b.id} → ${r.assignee_name}`); route(); } });
  const auto = b => ({ label: 'Auto-assign (AI)', icon: 'sparkles', run: async () => {
    const r = await api(`/bugs/${b.id}/assign`, { method: 'POST', body: { strategy: 'skill_based' } }); toast(`#${b.id} auto-assigned to ${r.assignee_name}`); route(); } });
  const reject = b => ({ label: 'Reject', icon: 'ban', kind: 'danger', run: async () => {
    const r = await askText(`Reject #${b.id}`, 'Why is this not a valid bug?', 'e.g. Works as designed / cannot reproduce.');
    if (r === null) return; await moveBug(b.id, 'REJECTED', '🚫 Rejected: ' + r); toast(`#${b.id} rejected`); route(); } });
  $('#view').innerHTML = `<div class="space-y-6 max-w-6xl">
    ${pageHead('Triage & Assign', 'Review incoming bugs, check the AI severity, and assign them to a developer.',
      queue.length ? `<button class="btn-primary" id="auto-all"><i data-lucide="wand-sparkles" class="w-4 h-4"></i>Auto-assign all (${queue.length})</button>` : '')}
    <div class="card p-5"><h3 class="font-semibold text-sm mb-3">Team workload <span class="text-slate-400 font-normal">– auto-assign picks the best skill match with the lowest load</span></h3>
      <div class="grid sm:grid-cols-3 gap-3">${devs.map(d => `<div class="flex items-center gap-3 p-3 rounded-xl bg-slate-500/5 border border-slate-500/10">
        <div class="avatar !w-9 !h-9 text-xs">${initials(d.username)}</div><div class="flex-1"><p class="text-sm font-semibold">${esc(d.username)}</p>
        <p class="text-[11px] text-slate-400">${esc(d.skills || '')}</p><div class="mt-1 h-1.5 rounded-full bg-slate-500/15 overflow-hidden"><div class="h-full bar-fill rounded-full bg-indigo-400" style="width:${Math.min(100, d.load_score * 8)}%"></div></div></div>
        <span class="text-xs text-slate-400">${d.open_bugs} open</span></div>`).join('')}</div></div>
    ${section('Needs assignment', 'new and reopened bugs', queue.map(b => workCard(b, [assign(b), auto(b), reject(b)],
      `${b.ai_severity ? `<p class="text-xs text-slate-400 mt-2">AI suggested ${sev(b.ai_severity)} (${Math.round((b.ai_confidence || 0) * 100)}%)</p>` : ''}${picker(b)}`)), 'Inbox zero – every bug is assigned ✅')}
    ${section('Assigned – not started yet', 'reassign if needed', assigned.map(b => workCard(b, [assign(b)], picker(b))), 'No waiting assignments')}
  </div>`;
  const all = $('#auto-all');
  if (all) all.onclick = async () => { all.disabled = true; let n = 0;
    for (const b of queue) { try { await api(`/bugs/${b.id}/assign`, { method: 'POST', body: { strategy: 'skill_based' } }); n++; } catch {} }
    toast(`Auto-assigned ${n} bug(s)`); route(); };
}

// REPORTER (and tester): My Reports ---------------------------------
const STEPS = ['NEW', 'ASSIGNED', 'IN_PROGRESS', 'FIXED', 'IN_TESTING', 'VERIFIED', 'CLOSED'];
function tracker(status) {
  if (['REJECTED', 'DUPLICATE'].includes(status)) return `<p class="mt-3 text-xs text-slate-400">This report was marked <b>${esc(status)}</b>.</p>`;
  const cur = status === 'REOPENED' ? 2 : STEPS.indexOf(status);
  return `<div class="tracker mt-3">${STEPS.map((s, i) => `<div class="tstep ${i < cur ? 'done' : i === cur ? 'now' : ''}"><span></span><p>${s.replace('_', ' ').toLowerCase()}</p></div>`).join('')}</div>`;
}
async function viewReports() {
  const bugs = await api('/bugs?reported=1');
  const open = bugs.filter(b => !['VERIFIED', 'CLOSED', 'REJECTED', 'DUPLICATE'].includes(b.status));
  const comment = b => ({ label: 'Add info', icon: 'message-square', run: async () => {
    const t = await askText(`Add information to #${b.id}`, 'Extra details, steps or screenshots links for the developer.', 'e.g. It also happens on mobile.');
    if (t) { await api(`/bugs/${b.id}/comments`, { method: 'POST', body: { body: t } }); toast('Added'); route(); } } });
  $('#view').innerHTML = `<div class="space-y-6 max-w-5xl">
    ${pageHead('My Reports', 'Bugs you reported and where they are in the fixing process.',
      `<button class="btn-primary" onclick="openNewBug()"><i data-lucide="plus" class="w-4 h-4"></i>Report a new bug</button>`)}
    <div class="grid sm:grid-cols-3 gap-4 stagger">${statTile('Reported by you', bugs.length, '#f9a8d4', 'file-text')}
      ${statTile('Still open', open.length, '#fbbf24', 'loader')}${statTile('Fixed & verified', bugs.filter(b => ['VERIFIED', 'CLOSED'].includes(b.status)).length, '#34d399', 'circle-check')}</div>
    ${section('Your reports', 'click a title to see comments & history', bugs.map(b => workCard(b, [comment(b)], tracker(b.status))),
      'You have not reported any bugs yet – click “Report a new bug”.')}
  </div>`;
}

// ------------------------------------------------------------------ releases
async function viewReleases() {
  state.projects = await api('/projects');
  const cards = await Promise.all(state.projects.flatMap(p => p.releases.map(r => api(`/releases/${r.id}/readiness`).then(x => ({ ...x, project: p.name })))));
  $('#view').innerHTML = `<div class="fade-in space-y-6">
   ${isMgr() ? `<form id="rel-form" class="card p-4 flex flex-wrap gap-3 items-end">
     <div><label class="lbl">Project</label><select name="project" class="inp">${state.projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div>
     <div><label class="lbl">Version</label><input name="version" class="inp" required placeholder="v1.2"></div>
     <div><label class="lbl">Release date</label><input name="date" type="date" class="inp"></div>
     <button class="btn-primary"><i data-lucide="plus" class="w-4 h-4"></i>New release</button>
     <div class="flex-1"></div>
     <div><label class="lbl">New project</label><input name="pname" class="inp" placeholder="Project name"></div><button type="button" id="proj-btn" class="btn">Add project</button></form>` : ''}
   <div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4 stagger">${cards.map(r => `<div class="card hoverable glow-card p-5">
     <div class="flex justify-between items-start"><div><p class="text-xs text-slate-400">${esc(r.project)}</p><h3 class="text-xl font-bold">${esc(r.version)}</h3></div>
     <span class="badge ${r.status === 'RELEASED' ? 'st-CLOSED' : 'st'}">${esc(r.status)}</span></div>
     <p class="text-sm text-slate-500 mt-1"><i data-lucide="calendar" class="inline w-3 h-3"></i> ${esc(r.release_date || 'no date')}</p>
     <div class="mt-4 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"><div class="h-full bar-fill ${r.ready ? 'bg-emerald-500' : 'bg-amber-500'}" style="width:${r.percent}%"></div></div>
     <p class="text-sm mt-2">${r.resolved}/${r.total} bugs resolved · <b class="${r.blockers ? 'text-rose-600' : 'text-emerald-600'}">${r.blockers} blocker(s)</b></p>
     ${isMgr() && r.status === 'PLANNED' ? `<button class="btn mt-4 w-full justify-center" data-ship="${r.id}"><i data-lucide="rocket" class="w-4 h-4"></i>Ship release</button>` : ''}</div>`).join('')}</div></div>`;
  const f = $('#rel-form');
  if (f) {
    f.onsubmit = async e => { e.preventDefault(); try { await api(`/projects/${f.project.value}/releases`, { method: 'POST', body: { version: f.version.value, release_date: f.date.value || null } }); toast('Release created'); route(); } catch (ex) { toast(ex.message, false); } };
    $('#proj-btn').onclick = async () => { try { await api('/projects', { method: 'POST', body: { name: f.pname.value } }); toast('Project created'); route(); } catch (ex) { toast(ex.message, false); } };
  }
  $$('[data-ship]').forEach(b => b.onclick = async () => { try { await api(`/releases/${b.dataset.ship}/ship`, { method: 'POST' }); toast('Release shipped 🚀'); route(); } catch (ex) { toast(ex.message, false); } });
}

// ------------------------------------------------------------------ team (admin creates users)
async function viewTeam() {
  state.users = await api('/users');
  const admin = state.user.role === 'ADMIN';
  $('#view').innerHTML = `<div class="fade-in space-y-6">
   ${admin ? `<form id="u-form" class="card p-4 grid md:grid-cols-6 gap-3 items-end">
     <div><label class="lbl">Username</label><input name="username" class="inp" required></div>
     <div><label class="lbl">E-mail</label><input name="email" type="email" class="inp" required></div>
     <div><label class="lbl">Password</label><input name="password" type="password" class="inp" required></div>
     <div><label class="lbl">Role</label><select name="role" class="inp">${['DEVELOPER','TESTER','MANAGER','REPORTER','ADMIN'].map(r => `<option>${r}</option>`).join('')}</select></div>
     <div><label class="lbl">Skills</label><input name="skills" class="inp" placeholder="ui,api"></div>
     <button class="btn-primary">Add member</button></form>` : ''}
   <div class="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 stagger">${state.users.map(u => `<div class="card hoverable glow-card p-5 flex items-center gap-4">
     <div class="avatar !w-12 !h-12">${initials(u.username)}</div><div class="min-w-0"><p class="font-bold truncate">${esc(u.username)}</p>
     <p class="text-xs text-slate-400 truncate">${esc(u.email)}</p><span class="badge st mt-1">${esc(u.role)}</span>
     ${u.skills ? `<p class="text-xs mt-1 text-slate-500">${esc(u.skills)}</p>` : ''}
     ${admin && u.id !== state.user.id ? `<div class="flex gap-2 mt-2"><select class="inp !py-1 !px-2 text-xs !w-auto" data-role="${u.id}">
        ${['REPORTER','DEVELOPER','TESTER','MANAGER','ADMIN'].map(r => `<option ${r === u.role ? 'selected' : ''}>${r}</option>`).join('')}</select>
        <button class="btn !py-1 !px-2 text-xs" data-save="${u.id}">Save role</button></div>` : ''}</div></div>`).join('')}</div></div>`;
  $$('[data-save]').forEach(b => b.onclick = async () => {
    const role = $(`[data-role="${b.dataset.save}"]`).value;
    try { await api(`/users/${b.dataset.save}`, { method: 'PATCH', body: { role } }); toast('Role updated to ' + role); route(); } catch (ex) { toast(ex.message, false); } });
  const f = $('#u-form');
  if (f) f.onsubmit = async e => { e.preventDefault(); try { await api('/users', { method: 'POST', body: Object.fromEntries(new FormData(f)) }); toast('Member added'); route(); } catch (ex) { toast(ex.message, false); } };
}

// ------------------------------------------------------------------ audit log
async function viewAudit() {
  const rows = await api('/audit');
  $('#view').innerHTML = `<div class="card overflow-x-auto fade-in"><table class="tbl"><thead><tr><th>Time (UTC)</th><th>User</th><th>Action</th><th>Detail</th><th>IP</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td class="text-xs text-slate-400 whitespace-nowrap">${esc(r.created_at)}</td><td>${esc(r.username || '–')}</td>
    <td><span class="badge ${r.action.includes('failed') ? 'sev-CRITICAL' : 'st'}">${esc(r.action)}</span></td><td>${esc(r.detail)}</td><td class="font-mono text-xs">${esc(r.ip_address || '')}</td></tr>`).join('')}</tbody></table></div>`;
}

// ------------------------------------------------------------------ visual effects
function fx() {
  const v = $('#view'); v.classList.remove('view-enter'); void v.offsetWidth; v.classList.add('view-enter');
  $$('[data-count]').forEach(el => { const end = parseFloat(el.dataset.count); if (isNaN(end)) return;
    const dec = String(el.dataset.count).includes('.') ? 2 : 0; const t0 = performance.now();
    const step = t => { const p = Math.min(1, (t - t0) / 900), e = 1 - Math.pow(1 - p, 3);
      el.textContent = (end * e).toFixed(dec); if (p < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); });
  $$('.glow-card').forEach(c => c.onmousemove = e => { const r = c.getBoundingClientRect();
    c.style.setProperty('--mx', (e.clientX - r.left) + 'px'); c.style.setProperty('--my', (e.clientY - r.top) + 'px'); });
}
document.addEventListener('click', e => {
  const b = e.target.closest('.btn-primary'); if (!b) return;
  const r = b.getBoundingClientRect(), s = Math.max(r.width, r.height), sp = document.createElement('span');
  sp.className = 'ripple'; sp.style.cssText = `width:${s}px;height:${s}px;left:${e.clientX - r.left - s / 2}px;top:${e.clientY - r.top - s / 2}px`;
  b.appendChild(sp); setTimeout(() => sp.parentNode && sp.parentNode.removeChild(sp), 600);
});
$$('.tilt').forEach(el => {
  el.onmousemove = e => { const r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    el.style.transform = `perspective(900px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg)`; };
  el.onmouseleave = () => { el.style.transform = ''; };
});
(() => { const box = $('#particles'); if (!box) return;
  for (let i = 0; i < 28; i++) { const p = document.createElement('span'); p.className = 'particle';
    const size = 2 + Math.random() * 5;
    p.style.cssText = `left:${Math.random() * 100}%;bottom:-10px;width:${size}px;height:${size}px;animation-duration:${8 + Math.random() * 14}s;animation-delay:${-Math.random() * 20}s;opacity:${.3 + Math.random() * .6}`;
    box.appendChild(p); } })();

boot();
