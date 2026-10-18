import { api } from '../api.js';
import { html, mount, $$, actions, ic, avatar, bytes, fmtDate, relTime, empty, modal, toast, loading } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

export async function render(el, ctx) {
  mount(el, loading(4));
  const [s, { people }] = await Promise.all([api.get('/api/settings'), api.get('/api/people')]);
  let tab = ctx.query.tab || 'org';
  const isAdmin = ctx.me.user.role === 'admin';
  const tabs = [['org', 'Organisation'], ['ai', 'AI providers'], ['rules', 'Scoring & risk rules'], ['access', 'Roles & access'], ['people', 'People'],
    ['data', 'Data & privacy'], ...(ctx.can('audit.view') ? [['audit', 'Audit log']] : [])];

  const body = async () => {
    if (tab === 'org') return html`<div class="grid g2"><div class="card"><h2 style="margin-bottom:12px">${nm(s.org.name, s.org.name_ja)}</h2>
      <dl class="kv"><dt>Industry</dt><dd>${s.org.industry}</dd><dt>Location</dt><dd>${s.org.location}</dd><dt>Employees</dt><dd>${s.org.employee_count}</dd>
        <dt>Plan</dt><dd style="text-transform:capitalize">${s.org.plan_tier}</dd><dt>Data</dt><dd>${s.org.is_simulated ? 'Simulated demo organisation' : 'Production'}</dd>
        <dt>Retention</dt><dd>${s.org.retention_days} days</dd></dl></div>
      <div class="card"><h3 style="margin-bottom:8px">Stored knowledge</h3><dl class="kv">${Object.entries(s.counts).map(([k, v]) => html`<dt>${k.replace(/_/g, ' ')}</dt><dd class="mono">${v}</dd>`)}
        <dt>file storage</dt><dd class="mono">${bytes(s.storage_bytes)}</dd></dl></div></div>`;
    if (tab === 'ai') return html`<div class="stack">
      ${s.providers.extractors.map((p) => html`<div class="card"><div class="row between"><h3>${p.label}</h3>${p.available ? html`<span class="badge b-ok">available</span>` : html`<span class="badge b-neutral">not configured</span>`}</div>
        <p class="dim">${p.reason}</p><small class="muted">Kind: ${p.kind}${p.model ? ` · model ${p.model}` : ''}</small></div>`)}
      <div class="card"><div class="row between"><h3>Knowledge assistant</h3><span class="badge b-info">${s.providers.assistant.mode}</span></div><p class="dim">${s.providers.assistant.reason}</p></div>
      <div class="card"><div class="row between"><h3>Video understanding</h3><span class="badge b-neutral">not configured</span></div><p class="dim">${s.providers.video.reason}</p></div>
      <div class="notice">${ic('shield', 16)}<div class="small">Providers are selected explicitly. A failed provider is never silently replaced and no result is fabricated. API keys live only in the server environment (see <span class="mono">.env.example</span>) and are never sent to the browser.</div></div></div>`;
    if (tab === 'rules') return html`<div class="grid g2">
      <div class="card"><h3 style="margin-bottom:8px">Competency scoring · ${s.scoring_rules.version}</h3><div class="formula">${JSON.stringify(s.scoring_rules, null, 2)}</div>
        <p class="small muted" style="margin-top:8px">Defined in <span class="mono">kizuna/domain/scoring.py</span>; covered by unit tests.</p></div>
      <div class="card"><h3 style="margin-bottom:8px">Knowledge-risk scoring · ${s.risk_rules.version}</h3><div class="formula">${JSON.stringify(s.risk_rules, null, 2)}</div>
        <p class="small muted" style="margin-top:8px">Defined in <span class="mono">kizuna/domain/risk.py</span>; covered by unit tests.</p></div></div>`;
    if (tab === 'access') {
      const roles = ['admin', 'expert', 'trainer', 'trainee'];
      return html`<div class="card"><div class="card-h"><h2>Permission matrix<span class="sub">Enforced on the server for every protected operation; the UI only hides controls for convenience</span></h2></div>
        <div class="table-wrap"><table><thead><tr><th>Permission</th>${roles.map((r) => html`<th>${r}</th>`)}</tr></thead><tbody>
        ${Object.entries(s.permissions).map(([p, rs]) => html`<tr><td class="mono small">${p}</td>${roles.map((r) => html`<td>${rs.includes(r) ? html`<span style="color:var(--ok)">${ic('check', 14)}</span>` : html`<span class="muted">—</span>`}</td>`)}</tr>`)}</tbody></table></div></div>`;
    }
    if (tab === 'people') return html`<div class="card"><div class="card-h"><h2>People<span class="sub">Planned retirement dates are entered explicitly by an administrator and used only for knowledge-risk planning</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>Person</th><th>Role</th><th>Languages</th><th>Skills held</th>${ctx.can('risk.view') ? html`<th>Planned retirement</th>` : ''}</tr></thead><tbody>
      ${people.map((p) => html`<tr><td><a class="row" href="#/people/${p.id}" style="color:inherit">${avatar(p.name, 'sm')}<span><b>${nm(p.name, p.name_ja)}</b><span class="sub">${p.title}</span></span></a></td>
        <td style="text-transform:capitalize">${p.role}</td><td class="small">${p.languages || ''}</td>
        <td>${p.skills.map((k) => html`<span class="skill-tag">${k.code}<b>${k.proficiency}</b></span> `)}</td>
        ${ctx.can('risk.view') ? html`<td>${p.retirement_date ? fmtDate(p.retirement_date) : html`<span class="muted">—</span>`}
          ${isAdmin ? html` <button class="btn btn-sm btn-ghost" data-action="retire" data-id="${p.id}" data-v="${p.retirement_date || ''}">Edit</button>` : ''}</td>` : ''}</tr>`)}</tbody></table></div></div>`;
    if (tab === 'data') return html`<div class="grid g2">
      <div class="card"><h3 style="margin-bottom:8px">${ic('download', 16)} Data portability</h3>
        <p class="dim">Captured expertise is an organisational asset, not data trapped in a chat. Every export is plain, documented JSON/CSV/Markdown.</p>
        <div class="stack" style="gap:8px;margin-top:10px">
          ${ctx.can('org.export') ? html`<a class="btn btn-primary" href="/api/export/org">${ic('download', 15)} Full knowledge archive (JSON)</a>` : html`<span class="muted small">Full archive export: administrators only.</span>`}
          ${ctx.can('competency.view_all') ? html`<a class="btn btn-ghost" href="/api/export/training-records.csv">${ic('download', 15)} Training records (CSV)</a>` : ''}
          <span class="small muted">Per-procedure SOP exports (Markdown / JSON) are on each procedure page.</span></div></div>
      <div class="card"><h3 style="margin-bottom:8px">${ic('shield', 16)} Privacy & security defaults</h3>
        <ul class="small dim" style="padding-left:18px;margin:0;line-height:1.8">
          <li>Expert recordings are processed only after consent with a stated scope is recorded.</li>
          <li>Uploads are type- and content-checked, stored outside the web root and streamed only to authorised users of the same organisation.</li>
          <li>Every query is scoped to your organisation (tenant isolation is covered by automated tests).</li>
          <li>Passwords use PBKDF2-SHA256; sessions are HttpOnly SameSite=Strict cookies; state-changing requests need a client header (CSRF defence).</li>
          <li>Uploaded transcripts are screened for prompt-injection text and always treated as data.</li>
          <li>Logs are structured and exclude transcripts, passwords and tokens.</li>
          <li>Retention: ${s.org.retention_days} days. Deletion of a person's recordings is handled on request by an administrator.</li>
          <li>No security certification or regulatory compliance is claimed for this prototype.</li></ul></div></div>`;
    if (tab === 'audit') {
      const { events } = await api.get('/api/audit');
      return html`<div class="card" style="padding:6px 8px"><div class="table-wrap"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Summary</th></tr></thead><tbody>
        ${events.map((e) => html`<tr><td class="small muted" title="${e.created_at}">${relTime(e.created_at)}</td><td class="small">${e.actor_name || 'system'}</td>
          <td class="mono small">${e.action}</td><td>${e.summary}</td></tr>`)}</tbody></table></div></div>`;
    }
    return empty('Unknown tab', '');
  };
  const draw = async () => {
    mount(el, html`${pageHead({ eyebrow: 'Administration', icon: 'settings', title: t('settings.title'), sub: t('settings.sub') })}
      <div class="tabs">${tabs.map(([k, l]) => html`<button class="tab ${tab === k ? 'on' : ''}" data-action="tab" data-k="${k}">${l}</button>`)}</div>
      <div id="sbody">${loading(2)}</div>`);
    mount(el.querySelector('#sbody'), await body());
  };
  await draw();
  return actions(el, {
    tab: (b) => { tab = b.dataset.k; draw(); },
    retire: async (b) => {
      const r = await modal({ title: 'Planned retirement date', body: html`<p class="small muted">Only enter a date the person has confirmed. Leave empty to clear.</p>
        <label class="field"><span>Date</span><input type="date" id="rd" value="${b.dataset.v}"></label>`,
        actions: [{ label: 'Cancel' }, { label: 'Save', onClick: (w) => api.put(`/api/people/${b.dataset.id}/retirement`, { retirement_date: w.querySelector('#rd').value || null }) }] });
      if (r) { toast('Saved — risk scores updated'); ctx.reload(); }
    },
  });
}
