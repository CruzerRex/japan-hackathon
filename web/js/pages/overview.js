import { api } from '../api.js';
import { html, mount, ic, avatar, relTime, statusBadge, compBadge, empty, actions, loading } from '../ui.js';
import { stackedBars, donut, riskBars } from '../charts.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const ACTION_ICON = { capture: 'capture', extraction: 'sparkle', procedure: 'library', assessment: 'academy', competency: 'matrix',
  translation: 'globe', mentorship: 'mentor', training: 'academy', feedback: 'flag', remediation: 'flag', people: 'users', auth: 'users', org: 'download' };

export async function render(el, ctx) {
  mount(el, loading(4));
  const d = await api.get('/api/dashboard');
  const m = d.metrics; const trainee = ctx.me.user.role === 'trainee';
  const kpi = (label, val, sub, icn, cls = '', href = '') => html`<a class="card kpi ${cls}" ${href ? html`href="${href}"` : ''} style="color:inherit;text-decoration:none">
    <div class="k-label">${ic(icn, 15)} ${label}</div><div class="k-val">${val}</div><div class="k-sub">${sub}</div></a>`;
  mount(el, html`
    ${pageHead({ eyebrow: nm(d.org.name, d.org.name_ja), icon: 'overview', title: t('overview.title'), sub: t('overview.sub'),
      actions: html`${ctx.can('capture.write') ? html`<a class="btn btn-primary" href="#/capture">${ic('capture', 16)} Start a capture</a>` : ''}
        ${ctx.can('risk.view') ? html`<a class="btn btn-ghost" href="#/risk">${ic('risk', 16)} Risk radar</a>` : html`<a class="btn btn-primary" href="#/academy">${ic('academy', 16)} My training</a>`}` })}
    <div class="grid g4" style="margin-bottom:16px">
      ${kpi('Documented procedures', html`${m.procedures_published}<small class="muted" style="font-size:15px"> / ${m.procedures_total}</small>`, 'published · total incl. drafts', 'library', '', '#/library')}
      ${kpi('Expert knowledge records', m.knowledge_records, `${m.records_breakdown.steps} steps · ${m.records_breakdown.tips} tips · ${m.records_breakdown.failure_modes} failure modes`, 'layers')}
      ${kpi('Training completed', m.modules_completed, `guided walkthroughs · ${m.assessments} assessments taken`, 'academy', '', '#/academy')}
      ${kpi('Validated workers', m.validated_workers, 'people with ≥1 trainer-validated competency', 'matrix', 'ok', '#/competency')}
      ${kpi('Skills at risk', html`${m.skills_at_risk}<small class="muted" style="font-size:15px"> / ${m.skills_total}</small>`, 'critical or high knowledge-loss risk', 'risk', m.skills_at_risk ? 'danger' : 'ok', ctx.can('risk.view') ? '#/risk' : '')}
      ${kpi('Awaiting expert review', m.review_queue, 'versions not yet approved & published', 'shield', m.review_queue ? 'warn' : '', '#/library')}
      ${kpi('Pending sign-off', m.pending_signoff, 'passed assessments awaiting a trainer', 'check', m.pending_signoff ? 'warn' : '', '#/competency')}
      ${kpi('Evidence-verified steps', `${m.evidence_verified_pct}%`, `of steps trace to a verified source · ${m.captures} capture sessions`, 'file')}
    </div>
    ${trainee && d.mine ? html`<div class="card accent" style="margin-bottom:16px"><div class="card-h"><h2>My competencies</h2>
        ${d.mine.remediation_open ? html`<span class="badge b-danger">${d.mine.remediation_open} remediation task(s)</span>` : ''}<a class="btn btn-sm btn-ghost" href="#/academy">Go to training</a></div>
        ${d.mine.competencies.length ? html`<div class="row">${d.mine.competencies.map((c) => html`<span class="holder" style="padding:4px 10px">${c.name} ${compBadge(c.status)}</span>`)}</div>`
          : html`<p class="muted">No training started yet. Open the Training Academy to begin.</p>`}</div>` : ''}
    <div class="grid g-side" style="margin-bottom:16px">
      <div class="card"><div class="card-h"><h2>Skills at risk of loss<span class="sub">Explainable score: expert concentration, retirement exposure, documentation and successor gaps</span></h2>
          ${ctx.can('risk.view') ? html`<a class="btn btn-sm btn-ghost" href="#/risk">Why? ${ic('arrow', 14)}</a>` : ''}</div>
        ${ctx.can('risk.view') ? riskBars(d.at_risk) : html`<p class="muted">Risk details are visible to experts, trainers and administrators.</p>`}</div>
      <div class="card"><div class="card-h"><h2>Risk distribution<span class="sub">${m.skills_total} tracked skills</span></h2></div>
        ${donut([{ label: 'Critical', value: d.risk_bands.critical, color: 'var(--danger)' }, { label: 'High', value: d.risk_bands.high, color: 'var(--warn)' },
          { label: 'Moderate', value: d.risk_bands.moderate, color: 'var(--steel)' }, { label: 'Low', value: d.risk_bands.low, color: 'var(--ok)' }],
          { center: d.risk_bands.critical + d.risk_bands.high, sub: 'at risk' })}</div>
    </div>
    <div class="grid g2" style="margin-bottom:16px">
      <div class="card"><div class="card-h"><h2>Knowledge coverage<span class="sub">Skills by documentation state, per category</span></h2></div>
        ${stackedBars(d.coverage.map((c) => ({ ...c, label: c.category })), ['published', 'in_progress', 'none'],
          { colors: { published: 'var(--ok)', in_progress: 'var(--warn)', none: 'var(--bg-4)' }, names: { published: 'Published procedure', in_progress: 'In review', none: 'Undocumented' } })}</div>
      <div class="card"><div class="card-h"><h2>Competency progress<span class="sub">People per status, by skill</span></h2></div>
        ${d.competency_progress.length ? stackedBars(d.competency_progress.map((c) => ({ ...c, label: c.name })), ['validated', 'pending_signoff', 'in_training', 'remediation', 'reassessment_required'],
          { colors: { validated: 'var(--ok)', pending_signoff: 'var(--warn)', in_training: 'var(--steel)', remediation: 'var(--danger)', reassessment_required: '#b65553' },
            names: { validated: 'Validated', pending_signoff: 'Pending sign-off', in_training: 'In training', remediation: 'Remediation', reassessment_required: 'Reassess' } })
          : empty('No training activity yet', 'Publish a procedure and enrol a trainee to see progress here.')}</div>
    </div>
    <div class="grid g2">
      <div class="card"><div class="card-h"><h2>Review queue<span class="sub">Generated knowledge is never training material until an expert approves it</span></h2></div>
        ${d.review_queue.length ? html`<div class="table-wrap"><table><tbody>${d.review_queue.map((v) => html`
          <tr class="clickable" data-action="open" data-href="#/procedures/${v.procedure_id}"><td><b>${v.code}</b> v${v.version_no}<span class="sub">${v.title}</span></td>
          <td>${statusBadge(v.status)}</td><td class="muted small">${relTime(v.updated_at)}</td></tr>`)}</tbody></table></div>`
          : trainee ? html`<p class="muted">Only approved, published modules are shown to trainees.</p>` : empty('Queue is clear', 'All captured knowledge has been reviewed.')}</div>
      <div class="card"><div class="card-h"><h2>Recent activity<span class="sub">From the audit trail</span></h2></div>
        ${d.activity.length ? html`<ul class="feed">${d.activity.map((a) => html`<li>${a.actor_name ? avatar(a.actor_name, 'sm') : html`<span class="avatar av-sm" style="--h:200">${ic(ACTION_ICON[a.action.split('.')[0]] || 'clock', 14)}</span>`}
          <div><div class="f-text">${a.summary}</div><div class="f-meta">${a.actor_name || 'System'} · ${relTime(a.created_at)}</div></div></li>`)}</ul>`
          : empty('No activity yet', 'Captures, reviews and assessments will appear here.')}</div>
    </div>`);
  return actions(el, { open: (r) => ctx.go(r.dataset.href), 'open-risk': (b) => ctx.go(`#/risk?skill=${b.dataset.code}`) });
}
