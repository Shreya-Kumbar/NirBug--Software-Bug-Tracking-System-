/* BugSense front-end: a small single-page app in plain JavaScript (no framework).
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
const VIEWS = { dashboard: 'Dashboard', bugs: 'All Bugs', board: 'Board', mine: 'My Work', releases: 'Releases', team: 'Team', audit: 'Audit Log' };
$$('.nav-link').forEach(a => a.onclick = () => { location.hash = a.dataset.view; $('#sidebar').classList.add('-translate-x-full'); });
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
  $$('[data-perm]').forEach(a => a.classList.toggle('hidden',
    a.dataset.perm === 'assign' ? !isMgr() : !isMgr()));
  loadNotifications(); setInterval(loadNotifications, 30000);
  route();
}
function route() {
  const v = (location.hash || '#dashboard').slice(1);
  const view = VIEWS[v] ? v : 'dashboard';
  $('#view-title').textContent = VIEWS[view];
  $$('.nav-link').forEach(a => a.classList.toggle('active', a.dataset.view === view));
  state.charts.forEach(c => c.destroy()); state.charts = [];
  $('#view').innerHTML = '<div class="space-y-4"><div class="skeleton h-28"></div><div class="grid grid-cols-2 xl:grid-cols-4 gap-4"><div class="skeleton h-24"></div><div class="skeleton h-24"></div><div class="skeleton h-24"></div><div class="skeleton h-24"></div></div><div class="skeleton h-64"></div></div>';
  ({ dashboard: viewDashboard, bugs: () => viewBugs(false), mine: () => viewBugs(true), board: viewBoard,
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
  const d = await api('/dashboard');
  const stat = (label, val, icon, color) => `<div class="card hoverable glow-card p-5 flex items-center gap-4">
     <div class="stat-icon ${color}"><i data-lucide="${icon}"></i></div>
     <div><p class="text-sm text-slate-500">${label}</p><p class="text-3xl font-extrabold" data-count="${esc(val ?? '')}">${val == null ? '–' : 0}</p></div></div>`;
  $('#view').innerHTML = `
  <div class="fade-in space-y-6">
    <div class="rounded-2xl p-6 banner-anim text-white flex flex-wrap items-center gap-4 shadow-xl shadow-indigo-500/20">
      <div class="flex-1"><p class="text-indigo-100">Hello ${esc(state.user.username)} 👋</p>
      <h2 class="text-2xl font-bold">${d.critical_open ? `${d.critical_open} critical bug(s) need attention` : 'No open critical bugs – nice work!'}</h2></div>
      <div class="glass rounded-xl px-4 py-2 text-sm"><i data-lucide="brain" class="inline w-4 h-4"></i> AI / human severity agreement: <b>${d.ai_agreement ?? '–'}%</b></div>
    </div>
    <div class="grid sm:grid-cols-2 xl:grid-cols-4 gap-4 stagger">
      ${stat('Total bugs', d.total, 'bug', 'bg-indigo-100 text-indigo-600')}
      ${stat('Open', d.open, 'circle-dot', 'bg-amber-100 text-amber-600')}
      ${stat('Resolved', d.closed, 'circle-check', 'bg-emerald-100 text-emerald-600')}
      ${stat('Avg. time to close (days)', d.mttr_days, 'timer', 'bg-rose-100 text-rose-600')}
    </div>
    <div class="grid lg:grid-cols-3 gap-4">
      <div class="card p-5"><h3 class="font-bold mb-4">By severity</h3><canvas id="c-sev" height="220"></canvas></div>
      <div class="card p-5 lg:col-span-2"><h3 class="font-bold mb-4">By status</h3><canvas id="c-status" height="110"></canvas></div>
    </div>
    <div class="card p-5"><h3 class="font-bold mb-4">Developer workload <span class="text-xs font-normal text-slate-400">(severity-weighted, used by auto-assignment)</span></h3>
      <div class="space-y-3">${d.workload.map(w => `<div class="flex items-center gap-3">
        <div class="avatar !w-8 !h-8 text-xs">${initials(w.username)}</div><div class="w-28 text-sm font-medium">${esc(w.username)}</div>
        <div class="flex-1 h-3 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"><div class="h-full bar-fill bg-gradient-to-r from-brand-500 to-fuchsia-500" style="width:${Math.min(100, w.load_score * 8)}%"></div></div>
        <div class="w-40 text-xs text-slate-500">${w.open_bugs} open · load ${w.load_score} · ${esc(w.skills)}</div></div>`).join('')}</div></div>
  </div>`;
  const dark = document.documentElement.classList.contains('dark'); Chart.defaults.color = dark ? '#94a3b8' : '#64748b';
  state.charts.push(new Chart($('#c-sev'), { type: 'doughnut', data: { labels: SEVS,
    datasets: [{ data: SEVS.map(s => d.by_severity[s] || 0), backgroundColor: ['#ef4444','#f97316','#eab308','#22c55e'], borderWidth: 0 }] },
    options: { cutout: '65%', plugins: { legend: { position: 'bottom' } } } }));
  state.charts.push(new Chart($('#c-status'), { type: 'bar', data: { labels: STATUSES.map(s => s.replace('_',' ')),
    datasets: [{ data: STATUSES.map(s => d.by_status[s] || 0), backgroundColor: '#6366f1', borderRadius: 8 }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 } } } } }));
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
      <p class="font-bold flex items-center gap-2"><i data-lucide="sparkles" class="w-4 h-4 text-brand-600"></i>AI Triage</p><p class="text-slate-500 mt-2">Start typing a title and description…</p></div></div>
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
     ${u.skills ? `<p class="text-xs mt-1 text-slate-500">${esc(u.skills)}</p>` : ''}</div></div>`).join('')}</div></div>`;
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
