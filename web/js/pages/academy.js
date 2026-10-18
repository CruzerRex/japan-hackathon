import { api } from '../api.js';
import { html, mount, actions, ic, avatar, meter, outcomeBadge, empty, loading, fmtDate, toast } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

export async function render(el, ctx) {
  mount(el, loading(3));
  const { modules, remediation } = await api.get('/api/training/modules');
  const open = remediation.filter((r) => r.status === 'open');
  mount(el, html`
    ${pageHead({ eyebrow: 'Module E', icon: 'academy', title: t('academy.title'), sub: t('academy.sub') })}
    <div class="sim-banner">${ic('flag', 16)} Assessments here are <b>simulated knowledge assessments</b>. They do not certify anyone to operate hazardous equipment —
      practical sign-off on the floor follows your plant's rules.</div>
    ${open.length ? html`<div class="card" style="border-color:rgba(240,98,95,.45);margin-bottom:16px"><div class="card-h"><h2>${ic('flag', 18)} Your remediation tasks</h2></div>
      ${open.map((r) => html`<div class="req" style="margin-bottom:8px"><div class="row between"><b>${r.code} · ${r.title}</b><small class="muted">${r.assigned_by_name ? `assigned by ${r.assigned_by_name}` : 'automatic — critical checkpoint missed'} · ${fmtDate(r.created_at)}</small></div>
        <div>${r.description}</div><div class="row"><a class="btn btn-sm btn-primary" href="#/academy/${r.procedure_id}">Re-study in guided mode</a>
        <button class="btn btn-sm btn-ghost" data-action="done" data-id="${r.id}">${ic('check', 13)} Mark done</button></div></div>`)}</div>` : ''}
    ${modules.length ? html`<div class="grid g3">${modules.map((m) => {
      const pct = m.step_count ? Math.round((m.progress.completed_steps / m.step_count) * 100) : 0;
      return html`<div class="card module-card">
        <div class="row between"><span class="mono muted">${m.code} · v${m.version_no}</span>${m.last_attempt ? outcomeBadge(m.last_attempt.outcome) : html`<span class="badge b-neutral">not started</span>`}</div>
        <h3>${m.title}</h3>
        <p class="small dim" style="margin:0">${m.purpose}</p>
        <div class="row small muted">${avatar(m.owner_name, 'xs')} Taught by ${nm(m.owner_name, m.owner_name_ja)} · ~${m.est_minutes} min</div>
        <div class="skill-tags">${m.skills.map((s) => html`<span class="skill-tag">${nm(s.name, s.name_ja)}</span>`)}</div>
        <div><div class="row between small muted"><span>Guided walkthrough</span><span>${m.progress.completed_steps}/${m.step_count} steps</span></div>${meter(pct, 100, m.progress.guided_completed ? 'ok' : '')}</div>
        <div class="row small muted">${m.step_count} steps · ${m.critical_steps} critical checkpoints · ${m.item_count} assessment items
          ${m.best_score !== null ? html` · best score <b class="mono" style="color:var(--text)">${m.best_score}</b>` : ''}</div>
        <div class="row" style="margin-top:auto"><a class="btn btn-primary btn-sm" href="#/academy/${m.procedure_id}">${m.progress.completed_steps ? 'Continue' : 'Start module'} ${ic('arrow', 14)}</a>
          ${m.last_attempt ? html`<a class="btn btn-ghost btn-sm" href="#/attempts/${m.last_attempt.id}">Last result</a>` : ''}</div>
      </div>`;
    })}</div>` : html`<div class="card">${empty('No published modules yet', 'Training modules appear here once an expert approves and publishes a procedure.')}</div>`}`);
  return actions(el, { done: async (b) => { await api.post(`/api/remediation/${b.dataset.id}/complete`); toast('Remediation marked done'); ctx.reload(); } });
}
