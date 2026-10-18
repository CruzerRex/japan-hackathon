// UI primitives: safe HTML templating, formatting, badges, toasts, modals, icons.

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s ?? ''));

function flatten(v) {
  if (v === null || v === undefined || v === false) return '';
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(flatten).join('');
  return esc(v);
}

/** Tagged template that escapes every interpolation unless wrapped in raw(). */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => { out += flatten(v) + strings[i + 1]; });
  return new Raw(out);
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function mount(el, content) { el.innerHTML = String(content); }

/** Delegated click handling: data-action="name" → handlers[name](el, event). */
export function actions(root, handlers) {
  const fn = async (e) => {
    const target = e.target.closest('[data-action]');
    if (!target || !root.contains(target)) return;
    const h = handlers[target.dataset.action];
    if (!h) return;
    if (target.tagName === 'A' || target.type === 'submit') e.preventDefault();
    if (target.dataset.busy) return;
    try {
      target.dataset.busy = '1';
      target.classList.add('is-busy');
      await h(target, e);
    } catch (err) {
      toastError(err);
    } finally {
      delete target.dataset.busy;
      target.classList.remove('is-busy');
    }
  };
  root.addEventListener('click', fn);
  return () => root.removeEventListener('click', fn);
}

// -- formatting ---------------------------------------------------------------------------------
export function fmtDate(iso, withTime = false) {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + (iso.length <= 16 ? ':00' : ''));
  if (isNaN(d)) return iso;
  const opts = { year: 'numeric', month: 'short', day: 'numeric' };
  if (withTime) Object.assign(opts, { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleString(document.documentElement.lang === 'ja' ? 'ja-JP' : 'en-GB', opts);
}
export function relTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  const fut = s < 0; const a = Math.abs(s);
  const units = [[60, 'second'], [3600, 'minute'], [86400, 'hour'], [604800, 'day'], [2629800, 'week'], [31557600, 'month'], [Infinity, 'year']];
  const divs = [1, 60, 3600, 86400, 604800, 2629800, 31557600];
  for (let i = 0; i < units.length; i++) {
    if (a < units[i][0]) {
      const n = Math.max(1, Math.round(a / divs[i]));
      const rtf = new Intl.RelativeTimeFormat(document.documentElement.lang === 'ja' ? 'ja' : 'en', { numeric: 'auto' });
      return rtf.format(fut ? n : -n, units[i][1]);
    }
  }
  return fmtDate(iso);
}
export const pct = (n) => (n === null || n === undefined ? '—' : `${Math.round(n)}%`);
export const bytes = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
export const tsToSec = (ts) => { if (!ts) return null; const p = ts.split(':').map(Number); return p.reduce((a, b) => a * 60 + b, 0); };
export const secToTs = (s) => { s = Math.max(0, Math.floor(s)); return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map((n) => String(n).padStart(2, '0')).join(':'); };

// -- badges ---------------------------------------------------------------------------------------
const STATUS = {
  DRAFT: ['Draft', 'neutral'], AI_PROCESSED: ['AI processed', 'violet'], EXPERT_REVIEW: ['Expert review', 'warn'],
  NEEDS_REVISION: ['Needs revision', 'danger'], APPROVED: ['Approved', 'info'], PUBLISHED: ['Published', 'ok'],
  REJECTED: ['Rejected', 'danger'], SUPERSEDED: ['Superseded', 'neutral'],
};
export function statusBadge(s) { const [l, c] = STATUS[s] || [s, 'neutral']; return html`<span class="badge b-${c}">${l}</span>`; }

const EVIDENCE = {
  demonstration: ['Demonstrated', 'ev-demo', 'The expert showed this (timestamped demonstration)'],
  transcript: ['Said', 'ev-said', 'Verbatim from the expert\'s spoken explanation'],
  expert_note: ['Written note', 'ev-note', 'Written by the expert in the capture studio'],
  expert_edit: ['Expert-authored', 'ev-edit', 'Authored or corrected by an expert during review'],
  inference: ['AI-inferred', 'ev-infer', 'Inferred — not directly evidenced; requires expert confirmation'],
};
export function evidenceBadge(src, verified, ts) {
  const [l, c, tip] = EVIDENCE[src] || ['Unknown', 'ev-unknown', 'No evidence'];
  const v = src === 'expert_edit' ? '' : verified ? ' ✓' : ' ?';
  const title = `${tip}${src !== 'expert_edit' && src !== 'inference' ? (verified ? ' · evidence verified against source' : ' · evidence NOT verified') : ''}`;
  return html`<span class="ev ${c} ${verified || src === 'expert_edit' ? '' : 'ev-unverified'}" title="${title}">${l}${v}${ts ? html` <span class="mono">${ts}</span>` : ''}</span>`;
}
export const EVIDENCE_LEGEND = EVIDENCE;

const COMP = {
  validated: ['Validated', 'ok'], pending_signoff: ['Pending sign-off', 'warn'], in_training: ['In training', 'info'],
  remediation: ['Remediation', 'danger'], reassessment_required: ['Reassess', 'danger'], rejected: ['Rejected', 'danger'],
  holder: ['Expert holder', 'amber'], practitioner: ['Practitioner', 'neutral'],
};
export function compBadge(s) { const [l, c] = COMP[s] || [s, 'neutral']; return html`<span class="badge b-${c}">${l}</span>`; }
export function bandBadge(b) { return html`<span class="badge band-${b}">${b}</span>`; }
export function outcomeBadge(o) {
  const m = { passed: ['Passed', 'ok'], failed: ['Not passed', 'warn'], critical_failure: ['Critical miss', 'danger'] }[o] || [o, 'neutral'];
  return html`<span class="badge b-${m[1]}">${m[0]}</span>`;
}

export function avatar(name, size = 'md') {
  const ini = (name || '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  let h = 0; for (const ch of name || '') h = (h * 31 + ch.charCodeAt(0)) % 360;
  return html`<span class="avatar av-${size}" style="--h:${h}" aria-hidden="true">${ini}</span>`;
}

export function empty(title, body, action = '') {
  return html`<div class="empty"><div class="empty-mark">${raw(icon('inbox', 28))}</div><h3>${title}</h3><p>${body}</p>${action}</div>`;
}
export function loading(rows = 3) {
  return html`<div class="loading" aria-busy="true">${Array.from({ length: rows }, () => html`<div class="skeleton"></div>`)}</div>`;
}
export function errorBox(err) {
  return html`<div class="card error-card"><h3>Something went wrong</h3><p>${err.message || err}</p>
    ${err.details ? html`<pre class="mono small">${JSON.stringify(err.details, null, 2)}</pre>` : ''}</div>`;
}
export function meter(value, max = 100, cls = '') {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return html`<div class="meter ${cls}" role="meter" aria-valuenow="${value}" aria-valuemin="0" aria-valuemax="${max}"><span style="width:${w}%"></span></div>`;
}

// -- toasts & modals ----------------------------------------------------------------------------------
export function toast(msg, kind = 'ok') {
  let host = $('#toasts');
  if (!host) { host = document.createElement('div'); host.id = 'toasts'; host.setAttribute('role', 'status'); document.body.appendChild(host); }
  const t = document.createElement('div');
  t.className = `toast toast-${kind}`;
  t.textContent = msg;
  host.appendChild(t);
  setTimeout(() => t.classList.add('out'), 4200);
  setTimeout(() => t.remove(), 4700);
}
export function toastError(err) {
  const blockers = err?.details?.blockers;
  toast((err?.message || String(err)) + (blockers ? ` — ${blockers.length} blocker(s)` : ''), 'error');
  if (err && !(err.status >= 400 && err.status < 500)) console.error(err);
}

export function modal({ title, body, actions: acts = [], wide = false, onOpen }) {
  return new Promise((resolve) => {
    const wrap = document.createElement('div');
    wrap.className = 'modal-wrap';
    wrap.innerHTML = String(html`<div class="modal ${wide ? 'modal-wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="mdl-t">
      <div class="modal-h"><h2 id="mdl-t">${title}</h2><button class="icon-btn" data-close aria-label="Close">${raw(icon('x'))}</button></div>
      <div class="modal-b">${body}</div>
      <div class="modal-f">${acts.map((a, i) => html`<button class="btn ${a.cls || (i === acts.length - 1 ? 'btn-primary' : 'btn-ghost')}" data-i="${i}">${a.label}</button>`)}</div></div>`);
    document.body.appendChild(wrap);
    const close = (v) => { wrap.remove(); document.removeEventListener('keydown', onKey); resolve(v); };
    const onKey = (e) => { if (e.key === 'Escape') close(null); };
    document.addEventListener('keydown', onKey);
    wrap.addEventListener('click', async (e) => {
      if (e.target === wrap || e.target.closest('[data-close]')) return close(null);
      const b = e.target.closest('[data-i]');
      if (!b) return;
      const a = acts[+b.dataset.i];
      if (a.onClick) {
        try { b.classList.add('is-busy'); const r = await a.onClick(wrap); if (r !== false) close(r ?? a.value ?? true); }
        catch (err) { toastError(err); } finally { b.classList.remove('is-busy'); }
      } else close(a.value ?? null);
    });
    const first = wrap.querySelector('input, textarea, select, button.btn-primary');
    if (first) setTimeout(() => first.focus(), 30);
    if (onOpen) onOpen(wrap);
  });
}
export async function confirmDialog(title, text, okLabel = 'Confirm', withComment = false, required = false) {
  return modal({
    title,
    body: html`<p>${text}</p>${withComment ? html`<label class="field"><span>Comment${required ? ' (required)' : ''}</span><textarea id="mdl-comment" rows="3"></textarea></label>` : ''}`,
    actions: [{ label: 'Cancel', value: null }, {
      label: okLabel, onClick: (w) => {
        const c = withComment ? w.querySelector('#mdl-comment').value.trim() : '';
        if (required && !c) { toast('A comment is required', 'error'); return false; }
        return { comment: c };
      },
    }],
  });
}

// -- icons (inline SVG, stroke-based) ------------------------------------------------------------------
const P = {
  overview: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z"/>',
  capture: '<circle cx="12" cy="12" r="3.5"/><path d="M3 8V6a2 2 0 0 1 2-2h2M17 4h2a2 2 0 0 1 2 2v2M21 16v2a2 2 0 0 1-2 2h-2M7 20H5a2 2 0 0 1-2-2v-2"/>',
  library: '<path d="M4 4h5v16H4zM10 4h4v16h-4zM15.5 4.5l3.8-1 3.2 15.5-3.8 1z"/>',
  graph: '<circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><circle cx="12" cy="10" r="1.6"/><path d="M6.8 7.2 10.6 9.3M17.2 7.2l-3.8 2.1M12 11.6v4.2"/>',
  academy: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/><path d="M22 9v6"/>',
  matrix: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 17.5l2 2 4-4"/>',
  risk: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
  mentor: '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="10" r="2.4"/><path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6M14 20c0-2.4 1.4-4.5 3-4.5s4 1.6 4 4.5"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.3 17l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.3l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.7 7l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 20h16"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  users: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 4.5a3 3 0 0 1 0 6M21 20c0-2.6-1.7-4.9-4-5.7"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  route: '<circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="5" r="2.2"/><path d="M8 19h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
};
export function icon(name, size = 18) {
  return `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ''}</svg>`;
}
export const ic = (name, size) => raw(icon(name, size));
