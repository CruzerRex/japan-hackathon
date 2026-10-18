import { api } from '../api.js';
import { html, mount, $, $$, actions, ic, avatar, outcomeBadge, compBadge, fmtDate, toast, loading, meter } from '../ui.js';
import { scoreGauge, sparkline } from '../charts.js';
import { nm } from '../i18n.js';
import { pageHead } from './_common.js';

export async function render(el, ctx) {
  mount(el, loading(4));
  const d = await api.get(`/api/attempts/${ctx.params.id}`);
  const a = d.attempt; const r = d.result; const rules = d.rules;
  const own = a.user_id === ctx.me.user.id;
  const canSign = ctx.can('assessment.signoff') && !own;
  const mins = Math.round((a.duration_s || 0) / 60);
  mount(el, html`
    ${pageHead({ crumb: own ? { href: '#/academy', label: 'Training Academy' } : { href: '#/competency', label: 'Competency Matrix' },
      eyebrow: `Assessment result · attempt #${a.attempt_no}`, icon: 'matrix', title: `${d.procedure.code} · ${d.procedure.title}`,
      sub: html`${avatar(d.learner.name, 'xs')} <b>${nm(d.learner.name, d.learner.name_ja)}</b> · ${d.learner.title} · submitted ${fmtDate(a.submitted_at, true)} · ${mins} min · module v${d.version_no}`,
      actions: html`<a class="btn btn-ghost" href="#/academy/${d.procedure.id}">${ic('academy', 15)} ${own ? 'Back to module' : 'Open module'}</a>` })}
    <div class="sim-banner">${ic('flag', 16)} Simulated knowledge assessment — evidence for a trainer's judgement, not a hands-on certification.</div>
    <div class="grid g-side" style="margin-bottom:16px">
      <div class="card"><div class="result-hero">
        ${scoreGauge(r.score, { threshold: rules.pass_threshold, label: 'score' })}
        <div><div class="row" style="margin-bottom:8px">${outcomeBadge(r.outcome)}
            <span class="badge ${a.signoff_status === 'approved' ? 'b-ok' : a.signoff_status === 'pending' ? 'b-warn' : a.signoff_status === 'not_applicable' ? 'b-neutral' : 'b-danger'}">
              sign-off: ${a.signoff_status.replace('_', ' ')}</span></div>
          <h2>${r.outcome === 'passed' ? (a.signoff_status === 'approved' ? 'Competency validated by a trainer' : 'Passed — awaiting trainer sign-off')
            : r.outcome === 'critical_failure' ? 'A critical checkpoint was missed' : 'Below the pass threshold'}</h2>
          <p class="dim">${r.outcome === 'critical_failure' ? 'Critical items are gated separately from accuracy: one miss means remediation, whatever the score.'
            : r.outcome === 'failed' ? `Score ${r.score} is below ${rules.pass_threshold}. Review the steps below and retake.`
            : 'A trainer reviews this evidence before the competency counts as validated.'}</p>
          ${d.history.length > 1 ? html`<div class="row small muted">Progress across attempts ${sparkline(d.history.map((h) => h.score))} ${d.history.map((h) => h.score).join(' → ')}</div>` : ''}
        </div></div>
        <div class="breakdown" style="margin-top:16px">
          <div><small>Accuracy (weighted)</small><b>${r.accuracy}%</b><small>× ${rules.knowledge_weight} = ${r.breakdown.knowledge_component}</small></div>
          <div><small>Critical checkpoints</small><b>${r.critical_passed}/${r.critical_total}</b><small>× ${rules.critical_weight} = ${r.breakdown.critical_component}</small></div>
          <div><small>Hints used</small><b>${r.hints_used}</b><small>penalty ${r.breakdown.hint_penalty}</small></div>
          <div><small>Final score</small><b>${r.score}</b><small>pass ≥ ${rules.pass_threshold} + critical gate</small></div></div>
        <details style="margin-top:12px"><summary class="small muted" style="cursor:pointer">How is this calculated? (rules ${r.rules_version})</summary>
          <div class="formula" style="margin-top:8px">score = ${rules.knowledge_weight} × accuracy + ${rules.critical_weight} × critical completion − hint penalty
outcome = critical_failure if any critical item wrong; passed if score ≥ ${rules.pass_threshold}; else failed
passed → competency "pending sign-off" until a trainer approves</div></details>
      </div>
      <div class="stack">
        <div class="card"><h3 style="margin-bottom:10px">Skill breakdown</h3>
          ${Object.entries(r.per_skill).map(([k, s]) => html`<div style="margin-bottom:10px"><div class="row between small"><span class="mono">${k}</span><span>${s.correct}/${s.total} · ${s.pct}%</span></div>${meter(s.pct, 100, s.pct >= 80 ? 'ok' : 'danger')}</div>`)}
          ${d.competency.length ? html`<div class="sep"></div><div class="small muted" style="margin-bottom:6px">Competency record now</div>${d.competency.map((c) => html`<div class="row between small" style="margin-bottom:4px"><span>${c.name}</span>${compBadge(c.status)}</div>`)}` : ''}</div>
        ${d.review_steps.length ? html`<div class="card"><h3 style="margin-bottom:8px">Recommended next steps</h3>
          <p class="small dim">Re-study these steps in guided mode${d.history.length ? ', then retake' : ''}:</p>
          ${d.review_steps.map((s) => html`<a class="chip" style="margin:3px 4px 3px 0" href="#/academy/${d.procedure.id}">${s.title}${s.source_timestamp ? html` <span class="mono muted">${s.source_timestamp}</span>` : ''}</a>`)}
          <p class="small muted" style="margin-top:8px">Book a mentor session from the Mentorship page if a step still feels unclear.</p></div>` : ''}
        ${d.remediation.length ? html`<div class="card" style="border-color:rgba(240,98,95,.4)"><h3 style="margin-bottom:8px">Remediation</h3>${d.remediation.map((t) => html`<p class="small">${t.status === 'done' ? '✓ ' : ''}${t.description}</p>`)}</div>` : ''}
        ${d.signoffs.length ? html`<div class="card"><h3 style="margin-bottom:8px">Trainer decisions</h3>${d.signoffs.map((s) => html`<div style="margin-bottom:8px"><b>${s.decision}</b> by ${s.trainer_name} <small class="muted">${fmtDate(s.created_at, true)}</small>${s.feedback ? html`<p class="small dim">“${s.feedback}”</p>` : ''}</div>`)}</div>` : ''}
      </div>
    </div>
    ${canSign && ['pending', 'not_applicable'].includes(a.signoff_status) ? html`<div class="card accent" style="margin-bottom:16px" id="signoff">
      <div class="card-h"><h2>${ic('shield', 18)} Trainer review<span class="sub">Your decision is recorded with your name. Approving validates the competency in the matrix.</span></h2></div>
      <label class="field"><span>Feedback to the learner</span><textarea id="so-fb" rows="2" placeholder="What you observed; what to practise next"></textarea></label>
      <details><summary class="small muted" style="cursor:pointer">Assign specific steps for remediation</summary>
        <div class="row" style="margin-top:8px">${r.items.filter((i) => i.step_id).map((i) => i.step_id).filter((v, i, arr) => arr.indexOf(v) === i).map((sid) => html`<label class="chip"><input type="checkbox" value="${sid}" class="so-step" ${r.review_steps.includes(sid) ? 'checked' : ''}> ${sid}</label>`)}</div></details>
      <div class="row" style="margin-top:12px">
        ${r.outcome === 'passed' ? html`<button class="btn btn-ok" data-action="sign" data-d="approve">${ic('check', 15)} Approve — validate competency</button>` : ''}
        <button class="btn btn-ghost" data-action="sign" data-d="remediate">Assign remediation</button>
        <button class="btn btn-ghost" data-action="sign" data-d="reassess">Require reassessment</button>
        <button class="btn btn-danger" data-action="sign" data-d="reject">Reject evidence</button></div></div>` : ''}
    <div class="card"><div class="card-h"><h2>Item review<span class="sub">Your answer, the expert-approved answer and why</span></h2></div>
      ${r.items.map((it, i) => html`<div class="q-card ${it.critical ? 'critical' : ''}"><div class="q-head">${i + 1}. ${it.kind} ${it.critical ? html`<span class="badge b-warn">critical</span>` : ''}
          <span class="badge ${it.is_correct ? 'b-ok' : 'b-danger'}">${it.is_correct ? 'correct' : it.chosen === null ? 'unanswered' : 'incorrect'}</span>${it.hint_used ? html`<span class="badge b-neutral">hint used</span>` : ''}</div>
        <div class="q-prompt">${it.prompt}</div>
        ${it.options.map((o, j) => html`<div class="option ${j === it.answer_index ? 'right' : j === it.chosen ? 'wrong' : ''}" style="cursor:default"><span class="ol">${'ABCDEF'[j]}</span>${o}</div>`)}
        ${it.explanation ? html`<p class="small dim">${it.explanation}</p>` : ''}</div>`)}</div>`);
  return actions(el, {
    sign: async (b) => {
      const decision = b.dataset.d; const feedback = $('#so-fb', el).value.trim();
      const body = { decision, feedback };
      if (decision === 'remediate') body.remediation = { step_ids: $$('.so-step:checked', el).map((c) => c.value), description: feedback };
      const res = await api.post(`/api/attempts/${a.id}/signoff`, body);
      toast(`Decision recorded — competency: ${res.competency_status.replace('_', ' ')}`); ctx.refreshNotifications(); ctx.reload();
    },
  });
}
