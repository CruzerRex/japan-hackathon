// Application shell: session bootstrap, router, sidebar/topbar, global search,
// notifications, persona switcher, demo tour and the knowledge-assistant drawer.
import { api, setUnauthenticatedHandler } from './api.js';
import { html, raw, mount, $, actions, ic, avatar, toast, toastError, relTime, esc, evidenceBadge, modal } from './ui.js';
import { t, getLang, setLang, nm } from './i18n.js';

const NAV = [
  ['overview', 'overview', 'nav.overview'], ['capture', 'capture', 'nav.capture'], ['library', 'library', 'nav.library'],
  ['graph', 'graph', 'nav.graph'], ['academy', 'academy', 'nav.academy'], ['competency', 'matrix', 'nav.matrix'],
  ['risk', 'risk', 'nav.risk'], ['mentorship', 'mentor', 'nav.mentorship'], ['settings', 'settings', 'nav.settings'],
];
const ROUTES = [
  [/^$/, 'overview'], [/^overview$/, 'overview'], [/^capture$/, 'capture'], [/^capture\/([\w-]+)$/, 'capture', ['id']],
  [/^library$/, 'library'], [/^procedures\/([\w-]+)$/, 'procedure', ['id']], [/^graph$/, 'graph'],
  [/^academy$/, 'academy'], [/^academy\/([\w-]+)$/, 'module', ['id']], [/^attempts\/([\w-]+)$/, 'attempt', ['id']],
  [/^competency$/, 'competency'], [/^risk$/, 'risk'], [/^mentorship$/, 'mentorship'], [/^settings$/, 'settings'],
  [/^people\/([\w-]+)$/, 'person', ['id']], [/^login$/, 'login'],
];
const NAV_FOR = { capture: 'capture', procedure: 'library', module: 'academy', attempt: 'competency', person: 'competency' };

const state = { me: null, notifications: [], cleanup: [] };
window.__kf = state;

setUnauthenticatedHandler(() => { state.me = null; if (!location.hash.startsWith('#/login')) location.hash = '#/login'; });

function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  const [path, qs] = h.split('?');
  const query = Object.fromEntries(new URLSearchParams(qs || ''));
  for (const [re, page, keys] of ROUTES) {
    const m = path.match(re);
    if (m) return { page, params: Object.fromEntries((keys || []).map((k, i) => [k, m[i + 1]])), query, path };
  }
  return { page: 'notfound', params: {}, query, path };
}

export const can = (perm) => !!state.me && state.me.permissions.includes(perm);
export const me = () => state.me;
export function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }

async function loadMe() {
  try { state.me = await api.get('/api/me'); } catch { state.me = null; }
  return state.me;
}

async function loadNotifications() {
  try { state.notifications = (await api.get('/api/notifications')).items; } catch { state.notifications = []; }
  const n = $('#notif-count');
  if (n) { n.textContent = state.notifications.length || ''; n.hidden = !state.notifications.length; }
}

function shell(route) {
  const m = state.me; const u = m.user; const active = NAV_FOR[route.page] || route.page;
  return html`
  ${m.org.is_simulated ? html`<div class="demo-strip">${ic('flag', 14)} ${t('demo.banner')}</div>` : ''}
  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <a class="brand" href="#/overview"><span class="brand-mark">絆</span><span class="brand-text"><b>KIZUNA</b> FORGE</span></a>
      <div class="org-box"><div class="org-name">${nm(m.org.name, m.org.name_ja)}</div>
        <div class="org-meta">${m.org.plan_tier} plan · ${m.org.employee_count} staff</div></div>
      <nav aria-label="Primary">${NAV.map(([key, icn, label]) => html`
        <a href="#/${key}" class="nav-item ${active === key ? 'active' : ''}" ${active === key ? raw('aria-current="page"') : ''}>
          ${ic(icn)}<span>${t(label)}</span></a>`)}</nav>
      <div class="side-foot">
        <div class="tagline">Preserve mastery. Transfer skill.<br>Keep industry moving.</div>
      </div>
    </aside>
    <div class="main">
      <header class="topbar">
        <button class="icon-btn only-mobile" data-action="toggle-nav" aria-label="Menu">${ic('menu')}</button>
        <div class="search" role="search">
          ${ic('search', 16)}<input id="gsearch" type="search" placeholder="${t('search.placeholder')}" aria-label="Global search" autocomplete="off">
          <div class="search-results" id="gsearch-results" hidden></div>
        </div>
        <div class="top-actions">
          <button class="btn btn-ghost btn-sm" data-action="assistant">${ic('chat', 16)} <span class="hide-sm">${t('assistant.open')}</span></button>
          ${m.demo_mode && m.org.is_simulated ? html`<button class="btn btn-ghost btn-sm" data-action="tour">${ic('route', 16)} <span class="hide-sm">${t('demo.tour')}</span></button>` : ''}
          <button class="btn btn-ghost btn-sm lang" data-action="lang" aria-label="Switch language">${getLang() === 'ja' ? 'EN' : '日本語'}</button>
          <div class="pop-wrap">
            <button class="icon-btn" data-action="notif" aria-label="${t('notifications')}">${ic('bell')}<span class="count" id="notif-count" hidden></span></button>
            <div class="pop" id="notif-pop" hidden></div>
          </div>
          <div class="pop-wrap">
            <button class="user-btn" data-action="usermenu" aria-label="User menu">${avatar(u.name, 'sm')}
              <span class="user-meta"><b>${nm(u.name, u.name_ja)}</b><small>${u.role} · ${u.title || ''}</small></span></button>
            <div class="pop pop-right" id="user-pop" hidden></div>
          </div>
        </div>
      </header>
      <main id="page" class="page" tabindex="-1"></main>
    </div>
  </div>
  <aside class="drawer" id="assistant" hidden aria-label="Knowledge assistant"></aside>`;
}

async function render() {
  state.cleanup.forEach((f) => f()); state.cleanup = [];
  const route = parseHash();
  const app = $('#app');
  if (route.page === 'login') {
    const mod = await import('./pages/login.js');
    return mod.render(app, { go, reloadMe: loadMe });
  }
  if (!state.me && !(await loadMe())) { location.hash = '#/login'; return; }
  let stored = null;
  try { stored = localStorage.getItem('kf.lang'); } catch { /* storage unavailable */ }
  if (state.me.user.locale && !stored) setLang(state.me.user.locale);
  mount(app, shell(route));
  bindShell();
  loadNotifications();
  const page = $('#page');
  const ctx = { params: route.params, query: route.query, me: state.me, go, can, reload: () => render(), refreshNotifications: loadNotifications };
  try {
    const mod = await import(`./pages/${route.page === 'notfound' ? 'notfound' : route.page}.js`);
    const cleanup = await mod.render(page, ctx);
    if (typeof cleanup === 'function') state.cleanup.push(cleanup);
  } catch (err) {
    console.error(err);
    mount(page, html`<div class="card error-card"><h3>${err.status === 404 ? 'Not found' : err.status === 403 ? 'Access denied' : 'Could not load this page'}</h3>
      <p>${err.message}</p><a class="btn btn-ghost" href="#/overview">Back to overview</a></div>`);
  }
  page.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

function bindShell() {
  const app = $('#app');
  state.cleanup.push(actions(app, {
    'toggle-nav': () => $('#sidebar').classList.toggle('open'),
    lang: async () => {
      const next = getLang() === 'ja' ? 'en' : 'ja'; setLang(next);
      api.patch('/api/me', { locale: next }).catch(() => {});
      render();
    },
    notif: () => togglePop('#notif-pop', renderNotifPop),
    usermenu: () => togglePop('#user-pop', renderUserPop),
    persona: async (el) => {
      await api.post('/api/auth/demo-login', { user_id: el.dataset.id });
      state.me = null; await loadMe();
      toast(`Now signed in as ${state.me.user.name} (${state.me.user.role})`);
      render();
    },
    logout: async () => { await api.post('/api/auth/logout'); state.me = null; location.hash = '#/login'; },
    assistant: () => openAssistant(),
    tour: () => openTour(),
  }));
  // global search
  const input = $('#gsearch'); const box = $('#gsearch-results'); let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = input.value.trim();
      if (q.length < 2) { box.hidden = true; return; }
      try {
        const { results } = await api.get('/api/search?q=' + encodeURIComponent(q));
        mount(box, results.length ? html`${results.map((r) => html`<a class="sr" href="${r.route}"><span class="badge b-neutral">${r.type}</span><span>${r.label}</span>${r.sub ? html`<small class="muted">${r.sub}</small>` : ''}</a>`)}`
          : html`<div class="sr muted">No matches for “${q}”</div>`);
        box.hidden = false;
      } catch (e) { toastError(e); }
    }, 180);
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Escape') { box.hidden = true; input.blur(); } });
  box.addEventListener('click', () => { box.hidden = true; input.value = ''; });
  const outside = (e) => {
    if (!e.target.closest('.search')) box.hidden = true;
    if (!e.target.closest('.pop-wrap')) document.querySelectorAll('.pop').forEach((p) => { p.hidden = true; });
  };
  document.addEventListener('click', outside);
  state.cleanup.push(() => document.removeEventListener('click', outside));
  const keys = (e) => { if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') { e.preventDefault(); input.focus(); } };
  document.addEventListener('keydown', keys);
  state.cleanup.push(() => document.removeEventListener('keydown', keys));
}

async function togglePop(sel, fill) {
  const pop = $(sel); const willOpen = pop.hidden;
  document.querySelectorAll('.pop').forEach((p) => { p.hidden = true; });
  if (willOpen) { await fill(pop); pop.hidden = false; }
}

function renderNotifPop(pop) {
  const items = state.notifications;
  mount(pop, html`<div class="pop-h">${t('notifications')}</div>
    ${items.length ? items.map((n) => html`<a class="pop-item" href="${n.route}"><span class="dot dot-${n.kind}"></span><span><b>${n.title}</b><small>${n.detail}</small></span></a>`)
      : html`<div class="pop-empty">Nothing waiting for you.</div>`}`);
}

async function renderUserPop(pop) {
  const u = state.me.user;
  let accounts = [];
  if (state.me.demo_mode && state.me.org.is_simulated) {
    try { accounts = (await api.get('/api/auth/demo-accounts')).accounts; } catch { /* ignore */ }
  }
  mount(pop, html`<div class="pop-h">${u.name}<small>${u.email}</small></div>
    ${accounts.length ? html`<div class="pop-sub">${t('switch')} <small class="muted">(simulated org only)</small></div>
      ${accounts.map((a) => html`<button class="pop-item ${a.id === u.id ? 'current' : ''}" data-action="persona" data-id="${a.id}">
        ${avatar(a.name, 'xs')}<span><b>${nm(a.name, a.name_ja)}</b><small>${a.role} · ${a.title}${a.org_name.includes('isolation') ? ' · other tenant' : ''}</small></span></button>`)}` : ''}
    <button class="pop-item" data-action="logout">${ic('back', 16)}<span><b>${t('signout')}</b></span></button>`);
}

// -- demo tour -------------------------------------------------------------------------------------
async function openTour() {
  let st;
  try { st = await api.get('/api/demo/status'); } catch (e) { return toastError(e); }
  await modal({
    title: 'Signature demo — 7 acts', wide: true,
    body: html`<p class="muted">A veteran inspector retires in ${st.days_to_retirement} days. Follow the acts in order; each checkmark is computed from live data.</p>
      <ol class="tour">${st.acts.map((a) => html`<li class="${a.done ? 'done' : ''}">
        <span class="tour-n">${a.done ? ic('check', 14) : a.act}</span>
        <div><b>Act ${a.act} — ${a.title}</b><p>${a.how}</p><small class="muted">Persona: ${a.persona} · ${a.state}</small></div>
        <span class="tour-go">${a.persona_id && a.persona_id !== state.me.user.id ? html`<button class="btn btn-sm btn-ghost" data-tour-persona="${a.persona_id}" data-tour-route="${a.route}">Switch & open</button>`
          : html`<a class="btn btn-sm btn-ghost" href="${a.route}" data-close>Open</a>`}</span></li>`)}</ol>`,
    actions: [{ label: 'Close', value: null }],
    onOpen: (w) => w.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-tour-persona]');
      if (!b) { if (e.target.closest('a[data-close]')) w.remove(); return; }
      try {
        await api.post('/api/auth/demo-login', { user_id: b.dataset.tourPersona });
        state.me = null; await loadMe(); w.remove();
        toast(`Signed in as ${state.me.user.name}`); go(b.dataset.tourRoute);
      } catch (err) { toastError(err); }
    }),
  });
}

// -- knowledge assistant drawer -----------------------------------------------------------------------
export function openAssistant(procedureId = null, preset = '') {
  const d = $('#assistant');
  d.hidden = false;
  mount(d, html`<div class="drawer-h"><div><b>${ic('chat', 16)} Knowledge Assistant</b>
      <small class="muted">Answers only from approved procedures, with citations</small></div>
      <button class="icon-btn" data-close-drawer aria-label="Close">${ic('x')}</button></div>
    <div class="drawer-b" id="as-log">
      <div class="as-hint">Try:
        ${['Why do we let the housing soak before measuring?', 'What common mistakes should I look for?', 'Which procedure teaches spindle run-out?', 'What should I review before my assessment?']
          .map((q) => html`<button class="chip" data-q="${q}">${q}</button>`)}</div>
    </div>
    <form class="drawer-f" id="as-form"><input id="as-q" placeholder="Ask about an approved procedure…" autocomplete="off" value="${preset}" aria-label="Question">
      <button class="btn btn-primary btn-sm" type="submit">Ask</button></form>`);
  const log = $('#as-log', d);
  const ask = async (q) => {
    if (!q.trim()) return;
    log.insertAdjacentHTML('beforeend', String(html`<div class="as-q">${q}</div><div class="as-a pending">Searching approved knowledge…</div>`));
    log.scrollTop = log.scrollHeight;
    const pending = log.querySelector('.as-a.pending');
    try {
      const r = await api.post('/api/assistant/ask', { question: q, procedure_id: procedureId });
      pending.classList.remove('pending');
      const cites = Object.fromEntries((r.citations || []).map((c) => [c.pid, c]));
      pending.innerHTML = String(html`
        <div class="as-mode">${r.mode === 'claude' ? 'Claude · grounded in cited passages' : r.mode === 'extractive' ? 'Extractive · verbatim approved passages' : ''}</div>
        ${r.blocks.map((b) => b.type === 'verified' ? html`<div class="as-block verified"><span class="tag-verified">Verified instruction</span><p>${b.text}</p>
            ${(b.citations || []).map((pid) => cites[pid] ? html`<a class="cite" href="#/procedures/${cites[pid].procedure_id}?step=${cites[pid].step_id || ''}">${cites[pid].procedure_code} v${cites[pid].version_no} · ${cites[pid].label}
              ${cites[pid].source_type ? html` ${evidenceBadge(cites[pid].source_type, cites[pid].evidence_verified, cites[pid].source_timestamp)}` : ''}</a>` : '')}</div>`
          : b.type === 'general' ? html`<div class="as-block general"><span class="tag-general">General explanation — not plant-specific</span><p>${b.text}</p></div>`
          : b.type === 'unknown' ? html`<div class="as-block unknown"><p>${b.text}</p>${r.suggestion ? html`<small>${r.suggestion}</small>` : ''}</div>`
          : html`<p class="as-lead">${b.text}</p>`)}
        ${r.injection_flags && r.injection_flags.length ? html`<div class="as-block unknown"><small>Your question contained instruction-like text; it was treated as plain text.</small></div>` : ''}`);
    } catch (e) { pending.classList.remove('pending'); pending.textContent = e.message; }
    log.scrollTop = log.scrollHeight;
  };
  d.onclick = (e) => {
    if (e.target.closest('[data-close-drawer]')) { d.hidden = true; return; }
    const chip = e.target.closest('[data-q]'); if (chip) ask(chip.dataset.q);
    if (e.target.closest('.cite')) d.hidden = true;
  };
  $('#as-form', d).onsubmit = (e) => { e.preventDefault(); const i = $('#as-q', d); ask(i.value); i.value = ''; };
  $('#as-q', d).focus();
  if (preset) { ask(preset); $('#as-q', d).value = ''; }
}

window.addEventListener('hashchange', render);
render();
