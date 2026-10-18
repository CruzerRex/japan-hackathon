import { api } from '../api.js';
import { html, mount, $, $$, actions, ic, avatar, evidenceBadge, toast, loading, tsToSec, fmtDate, confirmDialog } from '../ui.js';
import { nm } from '../i18n.js';
import { pageHead } from './_common.js';
import { openAssistant } from '../app.js';

export async function render(el, ctx) {
  mount(el, loading(4));
  let mod = await api.get(`/api/training/modules/${ctx.params.id}`);
  const c = mod.content;
  let mode = ctx.query.mode || 'guided';
  let cur = 0; let showJa = false;
  const done = new Set(mod.progress?.completed_steps || []);
  const checks = { ...(mod.progress?.step_checks || {}) };
  const chal = { ...(mod.progress?.challenge_results || {}) };
  let attempt = null; let answers = {}; let hints = new Set(); let started = 0; let timer = null;
  const ja = mod.translation_ja && mod.translation_ja.status === 'reviewed' ? mod.translation_ja.content : null;

  const head = () => pageHead({ crumb: { href: '#/academy', label: 'Training Academy' }, eyebrow: `${mod.procedure.code} · v${mod.version.version_no} · expert-approved`, icon: 'academy',
    title: c.title, sub: html`Taught by ${avatar(mod.owner?.name, 'xs')} <b>${nm(mod.owner?.name, mod.owner?.name_ja)}</b> · approved by ${mod.version.approved_by_name || '—'} on ${fmtDate(mod.version.approved_at)}`,
    actions: html`${ja ? html`<button class="btn btn-ghost btn-sm ${showJa ? 'on' : ''}" data-action="ja">${ic('globe', 14)} ${showJa ? 'Hide 日本語' : '日本語 (reviewed)'}</button>` : ''}
      <button class="btn btn-ghost btn-sm" data-action="ask">${ic('chat', 14)} Ask about this module</button>` });
  const modeTabs = () => html`<div class="tabs">${[['guided', 'Guided mode'], ['challenge', 'Challenge mode'], ['assess', 'Final assessment']].map(([k, l]) =>
    html`<button class="tab ${mode === k ? 'on' : ''}" data-action="mode" data-k="${k}">${l}</button>`)}</div>`;

  // -- guided -----------------------------------------------------------------------------------------
  const guided = () => {
    const s = c.steps[cur];
    const tips = c.tips.filter((x) => x.step_id === s.step_id); const mis = c.mistakes.filter((x) => x.step_id === s.step_id);
    const fms = c.failure_modes.filter((x) => x.step_id === s.step_id);
    const qs = c.questions.filter((q) => q.step_id === s.step_id);
    const jt = ja?.steps?.[s.step_id];
    return html`<div class="player">
      <div class="card flat"><div class="step-rail">${c.steps.map((x, i) => html`<button class="rail-item ${i === cur ? 'on' : ''} ${done.has(x.step_id) ? 'done' : ''}" data-action="goto" data-i="${i}">
        <span class="rail-dot">${done.has(x.step_id) ? ic('check', 11) : i + 1}</span><span>${showJa && ja?.steps?.[x.step_id]?.title ? ja.steps[x.step_id].title : x.title}</span></button>`)}</div>
        <div class="sep"></div><small class="muted">${done.size}/${c.steps.length} understood</small></div>
      <div class="stack">
        <div class="card">
          <div class="row between"><span class="mono muted">Step ${cur + 1} of ${c.steps.length}</span>
            <span class="row">${s.safety_critical ? html`<span class="badge b-danger">${ic('shield', 11)} Safety-critical</span>` : ''}${s.critical_checkpoint ? html`<span class="badge b-warn">Critical checkpoint</span>` : ''}</span></div>
          <h2 style="margin:8px 0">${s.title}</h2>
          ${showJa && jt ? html`<p class="dim" lang="ja" style="margin-top:-4px">${jt.title}</p>` : ''}
          <p style="font-size:16px">${s.instruction}</p>
          ${showJa && jt ? html`<p lang="ja" class="dim">${jt.instruction}</p>` : ''}
          ${s.why ? html`<p class="why"><b>Why</b>${s.why}</p>` : ''}
          ${s.quality_check ? html`<p class="why"><b>Check before moving on</b>${s.quality_check}</p>` : ''}
          ${s.tolerance ? html`<p class="why"><b>Stated requirement</b>${s.tolerance.text} <small class="muted">— always confirm against the current drawing</small></p>` : ''}
          ${s.evidence_quote ? html`<div class="quote">“${s.evidence_quote}” — ${nm(mod.owner?.name, mod.owner?.name_ja)}
            ${s.source_timestamp && mod.video ? html` <a href="#" class="mono" data-action="seek" data-ts="${s.source_timestamp}">▶ ${s.source_timestamp}</a>` : s.source_timestamp ? html` <span class="mono">${s.source_timestamp}</span>` : ''}</div>` : ''}
          <div class="step-meta">${evidenceBadge(s.source_type, s.evidence_verified, s.source_timestamp)}</div>
          ${mod.video ? html`<video id="mvid" controls preload="metadata" src="/api/files/${mod.video.id}" style="margin-top:12px"></video>` : ''}
          ${tips.length || mis.length || fms.length ? html`<div class="attach">
            ${tips.map((x) => html`<div class="attach-item tip"><span class="lbl">Expert tip</span><div>${x.text}</div></div>`)}
            ${mis.map((x) => html`<div class="attach-item mistake"><span class="lbl">Avoid</span><div>${x.text}</div></div>`)}
            ${fms.map((x) => html`<div class="attach-item fm"><span class="lbl">If</span><div>${x.symptom} → <b>${x.action}</b></div></div>`)}</div>` : ''}
        </div>
        ${qs.map((q) => html`<div class="q-card ${q.critical ? 'critical' : ''}" data-q="${q.id}"><div class="q-head">Knowledge check ${q.critical ? html`<span class="badge b-warn">critical</span>` : ''}
            ${checks[q.id] ? html`<span class="badge ${checks[q.id].correct ? 'b-ok' : 'b-danger'}">${checks[q.id].correct ? 'answered correctly' : 'try again'}</span>` : ''}</div>
          <div class="q-prompt">${q.prompt}</div>
          ${q.options.map((o, j) => html`<button class="option" data-action="check" data-q="${q.id}" data-j="${j}"><span class="ol">${'ABCDEF'[j]}</span>${o}</button>`)}
          <div class="fb"></div></div>`)}
        <div class="row between">
          <button class="btn btn-ghost" data-action="prev" ${cur === 0 ? 'disabled' : ''}>${ic('back', 14)} Previous</button>
          <span class="row"><button class="btn btn-ghost btn-sm" data-action="flag" data-id="${s.step_id}">${ic('flag', 13)} Unclear?</button>
          ${cur < c.steps.length - 1 ? html`<button class="btn btn-primary" data-action="understood">${ic('check', 14)} Understood — next step</button>`
            : html`<button class="btn btn-ok" data-action="finish-guided">${ic('check', 14)} Complete walkthrough</button>`}</span>
        </div>
      </div></div>`;
  };

  // -- challenge -----------------------------------------------------------------------------------------
  const challenge = () => {
    if (!c.scenarios.length) return html`<div class="card"><p class="muted">This module has no troubleshooting scenarios. Go to the final assessment.</p></div>`;
    const correct = Object.values(chal).filter((r) => r.correct).length;
    return html`<div class="card flat" style="margin-bottom:12px"><div class="row between"><span>Choose the next action in realistic situations the expert described. Feedback cites the expert.</span>
      <span class="mono">${correct}/${c.scenarios.length} correct</span></div></div>
      ${c.scenarios.map((s, i) => html`<div class="q-card ${s.critical ? 'critical' : ''}"><div class="q-head">Scenario ${i + 1} ${s.critical ? html`<span class="badge b-warn">critical decision</span>` : ''}
          ${chal[s.id] ? html`<span class="badge ${chal[s.id].correct ? 'b-ok' : 'b-danger'}">${chal[s.id].correct ? 'correct' : 'review'}</span>` : ''}</div>
        <div class="q-prompt">${s.situation}</div>
        ${s.options.map((o, j) => html`<button class="option" data-action="check" data-q="${s.id}" data-j="${j}"><span class="ol">${'ABCDE'[j]}</span>${o}</button>`)}
        <div class="fb"></div></div>`)}
      <div class="row"><button class="btn btn-primary" data-action="mode" data-k="assess">Go to final assessment ${ic('arrow', 14)}</button></div>`;
  };

  // -- final assessment ------------------------------------------------------------------------------------
  const assess = () => {
    const r = mod.rules;
    if (!attempt) {
      return html`<div class="card accent"><h2>Final assessment</h2>
        <p class="dim">${c.questions.length + c.scenarios.length} items, option order shuffled per attempt. Answer keys stay on the server until you submit.</p>
        <div class="formula">score = ${r.knowledge_weight} × accuracy + ${r.critical_weight} × critical-checkpoint completion − ${r.hint_penalty_points} per hint (max ${r.max_hint_penalty})
pass  = score ≥ ${r.pass_threshold}  AND  every critical item correct (critical gate)
then  → trainer sign-off required before the competency counts as validated</div>
        ${!done.size ? html`<div class="notice warn" style="margin-top:10px">${ic('flag', 16)} You haven't started the guided walkthrough. You may still take the assessment.</div>` : ''}
        ${mod.attempts.length ? html`<p class="small muted" style="margin-top:10px">Previous attempts: ${mod.attempts.map((a) => html`<a href="#/attempts/${a.id}">#${a.attempt_no} ${a.score}</a> `)}</p>` : ''}
        <button class="btn btn-primary" data-action="start" style="margin-top:10px">${ic('play', 14)} Start attempt ${mod.attempts.length + 1}</button></div>`;
    }
    const answered = Object.keys(answers).length;
    return html`<div class="card flat" style="margin-bottom:12px;position:sticky;top:64px;z-index:5"><div class="row between">
        <span>Attempt #${attempt.attempt_no} · <span class="mono">${answered}/${attempt.items.length}</span> answered · hints used: <span class="mono">${hints.size}</span></span>
        <span class="row"><span class="timer" id="timer">00:00</span><button class="btn btn-primary btn-sm" data-action="submit">Submit for grading</button></span></div></div>
      ${attempt.items.map((it, i) => html`<div class="q-card ${it.critical ? 'critical' : ''}"><div class="q-head">${i + 1}. ${it.kind === 'scenario' ? 'Scenario' : 'Question'} ${it.critical ? html`<span class="badge b-warn">critical</span>` : ''}
          <button class="btn btn-sm btn-ghost" style="margin-left:auto" data-action="hint" data-q="${it.id}" ${hints.has(it.id) ? 'disabled' : ''}>${ic('sparkle', 12)} Hint (−${r.hint_penalty_points})</button></div>
        <div class="q-prompt">${it.prompt}</div>
        ${it.options.map((o, j) => html`<button class="option ${answers[it.id] === j ? 'sel' : ''}" data-action="answer" data-q="${it.id}" data-j="${j}"><span class="ol">${'ABCDEF'[j]}</span>${o}</button>`)}
        <div class="hint-out small dim" id="hint-${it.id}"></div></div>`)}`;
  };

  const draw = () => {
    mount(el, html`${head()}
      <div class="sim-banner">${ic('flag', 16)} Simulated training & knowledge assessment. It does not certify hands-on competence on live machinery.</div>
      ${modeTabs()}<div id="mode-body">${mode === 'guided' ? guided() : mode === 'challenge' ? challenge() : assess()}</div>`);
  };
  draw();

  const tick = () => { const t = $('#timer', el); if (t && started) { const s = Math.floor((Date.now() - started) / 1000); t.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; } };
  const saveProgress = (extra = {}) => api.post(`/api/training/modules/${ctx.params.id}/progress`, { completed_steps: [...done], ...extra });

  const off = actions(el, {
    mode: (b) => { if (attempt && b.dataset.k !== 'assess') { toast('Finish or submit your attempt first', 'error'); return; } mode = b.dataset.k; draw(); },
    goto: (b) => { cur = +b.dataset.i; draw(); },
    prev: () => { cur = Math.max(0, cur - 1); draw(); },
    understood: async () => { done.add(c.steps[cur].step_id); await saveProgress(); cur += 1; draw(); window.scrollTo(0, 0); },
    'finish-guided': async () => {
      done.add(c.steps[cur].step_id);
      await saveProgress({ guided_completed: true });
      toast('Guided walkthrough complete'); mode = c.scenarios.length ? 'challenge' : 'assess'; draw();
    },
    ja: () => { showJa = !showJa; draw(); },
    ask: () => openAssistant(ctx.params.id),
    seek: (b) => { const v = $('#mvid', el); if (v) { v.currentTime = tsToSec(b.dataset.ts); v.play().catch(() => {}); } },
    flag: async (b) => {
      const r = await confirmDialog('Flag this step as unclear', 'Your note goes to the expert as input for the next revision.', 'Send', true, true);
      if (r) { await api.post(`/api/procedures/${ctx.params.id}/feedback`, { step_id: b.dataset.id, note: r.comment }); toast('Sent to the expert — thank you'); }
    },
    check: async (b) => {
      const card = b.closest('.q-card'); const qid = b.dataset.q;
      const r = await api.post(`/api/training/modules/${ctx.params.id}/check`, { item_id: qid, choice: +b.dataset.j });
      $$('.option', card).forEach((o, j) => { o.classList.remove('right', 'wrong'); if (j === r.correct_index) o.classList.add('right'); });
      if (!r.correct) b.classList.add('wrong');
      (c.scenarios.some((s) => s.id === qid) ? chal : checks)[qid] = { correct: r.correct };
      $('.fb', card).innerHTML = String(html`<div class="feedback ${r.correct ? 'ok' : 'bad'}"><b>${r.correct ? 'Correct.' : 'Not quite.'}</b> ${r.option_feedback || ''} ${r.explanation}
        ${r.step ? html`<br><small>From step “${r.step.title}”${r.step.source_timestamp ? ` @ ${r.step.source_timestamp}` : ''}</small>` : ''}</div>`);
    },
    start: async () => {
      attempt = await api.post(`/api/training/modules/${ctx.params.id}/attempts`);
      answers = {}; hints = new Set(); started = Date.now(); clearInterval(timer); timer = setInterval(tick, 1000); draw();
    },
    answer: (b) => {
      answers[b.dataset.q] = +b.dataset.j;
      $$(`[data-action=answer][data-q="${b.dataset.q}"]`, el).forEach((o) => o.classList.toggle('sel', o === b));
      const head = el.querySelector('.card.flat .row span .mono'); if (head) head.textContent = `${Object.keys(answers).length}/${attempt.items.length}`;
    },
    hint: async (b) => {
      const r = await api.post(`/api/attempts/${attempt.attempt_id}/hint`, { item_id: b.dataset.q });
      hints.add(b.dataset.q); b.disabled = true;
      $(`#hint-${b.dataset.q}`, el).textContent = `Hint: ${r.hint} (−${r.penalty_points} points)`;
    },
    submit: async () => {
      const missing = attempt.items.length - Object.keys(answers).length;
      if (missing && !(await confirmDialog('Submit with unanswered items?', `${missing} item(s) unanswered will be graded as incorrect.`, 'Submit anyway'))) return;
      const r = await api.post(`/api/attempts/${attempt.attempt_id}/submit`, { answers, duration_s: Math.round((Date.now() - started) / 1000) });
      clearInterval(timer); attempt = null; ctx.refreshNotifications();
      ctx.go(`#/attempts/${r.attempt.id}`);
    },
  });
  return () => { off(); clearInterval(timer); };
}
