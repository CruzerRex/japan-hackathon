import { api } from '../api.js';
import { html, mount, actions, ic, avatar, compBadge, outcomeBadge, relTime, empty, loading } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const CODE = { validated: 'VAL', pending_signoff: 'SIGN', in_training: 'TRN', remediation: 'REM', reassessment_required: 'RE', rejected: 'REJ', holder: 'EXP', practitioner: 'PR' };

export async function render(el, ctx) {
  mount(el, loading(4));
  const m = await api.get('/api/competency/matrix');
  const cell = (p, s) => {
    const c = m.cells[`${p.id}:${s.id}`];
    if (!c) return html`<span class="cell c-none" title="No record">·</span>`;
    const title = `${p.name} · ${s.name}: ${c.status.replace('_', ' ')}${c.score != null ? ` · score ${c.score}` : ''}${c.validated_by ? ` · validated by ${c.validated_by}` : ''}${c.proficiency ? ` · proficiency ${c.proficiency}/5` : ''}`;
    return c.attempt_id ? html`<a class="cell c-${c.status}" href="#/attempts/${c.attempt_id}" title="${title}">${CODE[c.status] || '?'}</a>`
      : html`<span class="cell c-${c.status}" title="${title}">${c.proficiency ? `${CODE[c.status]}${c.proficiency}` : CODE[c.status]}</span>`;
  };
  mount(el, html`
    ${pageHead({ eyebrow: 'Module F', icon: 'matrix', title: t('matrix.title'), sub: t('matrix.sub'),
      actions: ctx.can('competency.view_all') ? html`<a class="btn btn-ghost" href="/api/export/training-records.csv">${ic('download', 15)} Training records (CSV)</a>` : '' })}
    ${m.queue.length ? html`<div class="card accent" style="margin-bottom:16px"><div class="card-h"><h2>${ic('shield', 18)} Awaiting your sign-off<span class="sub">Passed simulated assessments — validate, remediate or require reassessment</span></h2></div>
      <div class="table-wrap"><table><tbody>${m.queue.map((q) => html`<tr class="clickable" data-action="open" data-id="${q.id}">
        <td><span class="row">${avatar(q.learner_name, 'sm')}<b>${nm(q.learner_name, q.learner_name_ja)}</b></span></td><td><b class="mono">${q.code}</b> ${q.title}</td>
        <td class="mono">${q.score}</td><td class="small">accuracy ${q.knowledge_accuracy}% · critical ${q.critical_passed}/${q.critical_total}</td>
        <td class="small muted">${relTime(q.submitted_at)}</td><td><span class="btn btn-sm btn-primary">Review</span></td></tr>`)}</tbody></table></div></div>` : ''}
    <div class="card" style="margin-bottom:16px"><div class="card-h"><h2>Skills × people<span class="sub">Expert holders (EXP + proficiency) and successors' validation status. Click a status to see the evidence.</span></h2></div>
      <div class="legend" style="margin-bottom:10px">${Object.entries(CODE).map(([k, v]) => html`<span><span class="cell c-${k}" style="width:auto;padding:0 6px;height:20px">${v}</span> ${k.replace('_', ' ')}</span>`)}</div>
      <div class="table-wrap"><table class="matrix"><thead><tr><th></th>${m.skills.map((s) => html`<th class="skill-h" title="${s.description}">${nm(s.name, s.name_ja)} <small>${s.code}</small></th>`)}</tr></thead>
        <tbody>${m.people.map((p) => html`<tr><td class="person"><a class="row" href="#/people/${p.id}" style="color:inherit">${avatar(p.name, 'sm')}<span><b>${nm(p.name, p.name_ja)}</b><br><small class="muted">${p.role} · ${p.title}</small></span></a></td>
          ${m.skills.map((s) => html`<td>${cell(p, s)}</td>`)}</tr>`)}</tbody></table></div></div>
    <div class="grid g2">
      <div class="card"><div class="card-h"><h2>Recent assessments</h2></div>
        ${m.recent.length ? html`<div class="table-wrap"><table><tbody>${m.recent.map((r) => html`<tr class="clickable" data-action="open" data-id="${r.id}">
          <td>${r.learner_name}<span class="sub">${r.code} · attempt #${r.attempt_no}</span></td><td class="mono">${r.score}</td><td>${outcomeBadge(r.outcome)}</td>
          <td><span class="badge b-neutral">${r.signoff_status.replace('_', ' ')}</span></td><td class="small muted">${relTime(r.submitted_at)}</td></tr>`)}</tbody></table></div>`
          : empty('No assessments yet', 'Results appear once trainees complete a module assessment.')}</div>
      <div class="card"><div class="card-h"><h2>How competency is decided<span class="sub">Rules ${m.rules.version} — deterministic and documented</span></h2></div>
        <div class="formula">score = ${m.rules.knowledge_weight} × weighted accuracy
      + ${m.rules.critical_weight} × critical-checkpoint completion
      − ${m.rules.hint_penalty_points} per hint (max ${m.rules.max_hint_penalty})

critical gate: any critical item wrong → remediation
score ≥ ${m.rules.pass_threshold} → pending sign-off
trainer approves → validated</div>
        <p class="small muted" style="margin-top:10px">No AI judges competence. The score is evidence; the trainer's recorded decision is what validates a person. A later failed practice attempt never silently revokes a validated competency.</p></div>
    </div>`);
  return actions(el, { open: (r) => ctx.go(`#/attempts/${r.dataset.id}`) });
}
