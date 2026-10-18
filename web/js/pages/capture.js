import { api } from '../api.js';
import { html, mount, $, $$, actions, ic, avatar, relTime, statusBadge, meter, empty, modal, toast, toastError, bytes,
  secToTs, tsToSec, loading, esc } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

export async function render(el, ctx) {
  if (!ctx.can('capture.read')) {
    mount(el, html`${pageHead({ title: t('capture.title') })}<div class="card">${empty('Capture is for experts and trainers',
      'Knowledge capture sessions contain unreviewed expert recordings. Approved results appear in the Training Academy.',
      html`<a class="btn btn-primary" href="#/academy">Open Training Academy</a>`)}</div>`);
    return;
  }
  return ctx.params.id ? studio(el, ctx) : list(el, ctx);
}

// ---------------------------------------------------------------------------------------------------
async function list(el, ctx) {
  mount(el, loading(3));
  const [{ captures }, { skills }, { people }] = await Promise.all([api.get('/api/captures'), api.get('/api/skills'), api.get('/api/people')]);
  const experts = people.filter((p) => ['expert', 'trainer', 'admin'].includes(p.role));
  mount(el, html`
    ${pageHead({ eyebrow: 'Module B', icon: 'capture', title: t('capture.title'), sub: t('capture.sub'),
      actions: ctx.can('capture.write') ? html`<button class="btn btn-primary" data-action="new">${ic('plus', 16)} New capture session</button>` : '' })}
    <div class="notice info" style="margin-bottom:16px">${ic('shield', 16)}<div>Recordings are processed only after the expert's consent is recorded.
      Unreviewed output is never shown to trainees — it enters the expert review workflow first.</div></div>
    ${captures.length ? html`<div class="grid g3">${captures.map((c) => html`
      <a class="card" href="#/capture/${c.id}" style="color:inherit;text-decoration:none;display:flex;flex-direction:column;gap:10px">
        <div class="row between"><span class="badge ${c.status === 'extracted' ? 'b-ok' : 'b-warn'}">${c.status === 'extracted' ? 'Extracted' : 'Draft'}</span>
          <small class="muted">${relTime(c.updated_at)}</small></div>
        <h3>${c.title}</h3>
        <div class="row">${avatar(c.expert?.name, 'xs')}<small>${nm(c.expert?.name, c.expert?.name_ja)} · ${c.machine || 'machine not set'}</small></div>
        <div><div class="row between small muted"><span>Capture completeness</span><span>${c.completeness.pct}%</span></div>${meter(c.completeness.pct, 100, c.completeness.pct === 100 ? 'ok' : '')}</div>
        <div class="row small muted">${ic('clock', 14)} ${c.marker_count} markers · ${c.file_count} files ${c.consent_given ? html`· ${ic('shield', 14)} consent` : html`· <span style="color:var(--warn)">no consent yet</span>`}</div>
        ${c.procedure_id ? html`<small class="muted">→ linked procedure</small>` : ''}
      </a>`)}</div>` : html`<div class="card">${empty('No capture sessions yet', 'Start by recording a veteran expert demonstrating a critical task.')}</div>`}`);
  return actions(el, {
    new: async () => {
      const res = await modal({
        title: 'New capture session',
        body: html`<label class="field"><span>Task title</span><input id="nc-title" placeholder="e.g. Final bore inspection of SH-62 housings"></label>
          <label class="field"><span>Expert being recorded</span><select id="nc-expert">${experts.map((p) => html`<option value="${p.id}">${p.name} — ${p.title}</option>`)}</select></label>
          <label class="field"><span>Skills demonstrated</span><select id="nc-skills" multiple size="6">${skills.map((s) => html`<option value="${s.id}">${s.code} · ${s.name}</option>`)}</select>
          <small class="hint">Ctrl/Cmd-click to select several.</small></label>`,
        actions: [{ label: 'Cancel' }, {
          label: 'Create draft', onClick: async (w) => {
            const body = { title: $('#nc-title', w).value, expert_id: $('#nc-expert', w).value,
              skill_ids: [...$('#nc-skills', w).selectedOptions].map((o) => o.value) };
            return api.post('/api/captures', body);
          },
        }],
      });
      if (res && res.id) ctx.go(`#/capture/${res.id}`);
    },
  });
}

// ---------------------------------------------------------------------------------------------------
const SECTIONS = [['context', 'Task & context'], ['consent', 'Consent & access'], ['source', 'Recording & transcript'],
  ['markers', 'Demonstration markers'], ['tacit', 'Tacit knowledge'], ['extract', 'Extract knowledge']];

async function studio(el, ctx) {
  mount(el, loading(4));
  const [cap, { skills }, providers] = await Promise.all([api.get(`/api/captures/${ctx.params.id}`), api.get('/api/skills'), api.get('/api/providers')]);
  let state = cap;
  const editable = ctx.can('capture.write') && cap.status !== 'archived';
  let saveTimer = null; let pending = {};

  const save = async () => {
    const body = pending; pending = {};
    if (!Object.keys(body).length) return;
    $('#save-ind', el).textContent = 'Saving…';
    try { state = await api.patch(`/api/captures/${cap.id}`, body); $('#save-ind', el).textContent = `Saved ${new Date().toLocaleTimeString()}`; refreshNav(); }
    catch (e) { $('#save-ind', el).textContent = 'Not saved'; toastError(e); }
  };
  const queue = (field, value) => { pending[field] = value; clearTimeout(saveTimer); saveTimer = setTimeout(save, 700); $('#save-ind', el).textContent = 'Unsaved changes…'; };

  const video = () => state.files.filter((f) => f.kind === 'video').slice(-1)[0];
  const checks = () => state.completeness.checks;
  const navItem = ([id, label], i) => {
    const ok = { context: checks().metadata, consent: checks().consent, source: checks().source, markers: state.markers.length > 0,
      tacit: checks().tacit_notes, extract: !!state.procedure_id }[id];
    return html`<button class="wz ${ok ? 'ok' : ''}" data-action="jump" data-id="${id}"><span class="wz-n">${ok ? ic('check', 12) : i + 1}</span>${label}</button>`;
  };
  const refreshNav = () => { const n = $('#wz', el); if (n) mount(n, html`${SECTIONS.map(navItem)}`); };
  const txSegments = () => (state.transcript.match(/^\s*\[?\d{1,2}:\d{2}(:\d{2})?/gm) || []).length;

  const draw = () => {
    const v = video();
    mount(el, html`
      ${pageHead({ crumb: { href: '#/capture', label: 'All capture sessions' }, eyebrow: 'Capture Studio', icon: 'capture', title: state.title,
        sub: html`Expert: <b>${nm(state.expert?.name, state.expert?.name_ja)}</b> · ${state.expert?.title || ''}`,
        actions: html`<span class="muted small" id="save-ind">${editable ? 'All changes saved automatically' : 'Read-only'}</span>
          ${state.procedure ? html`<a class="btn btn-ghost" href="#/procedures/${state.procedure.id}">${ic('library', 16)} ${state.procedure.code} v${state.procedure.version_no} ${statusBadge(state.procedure.status)}</a>` : ''}` })}
      <div class="grid g-side-l">
        <aside><div class="card flat" style="position:sticky;top:76px"><div class="wizard-nav" id="wz">${SECTIONS.map(navItem)}</div>
          <div class="sep"></div><div class="small muted">Completeness</div>${meter(state.completeness.pct, 100, state.completeness.pct === 100 ? 'ok' : '')}
          <p class="small muted" style="margin-top:8px">Drafts save as you type; you can leave and resume any time.</p></div></aside>
        <div class="stack">
          <section class="card" id="sec-context"><div class="card-h"><h2>1 · Task & context</h2></div>
            <div class="grid g2">
              <label class="field"><span>Task title</span><input data-f="title" value="${state.title}" ${editable ? '' : 'disabled'}></label>
              <label class="field"><span>Task category</span><input data-f="task_category" value="${state.task_category || ''}" placeholder="e.g. Final inspection" ${editable ? '' : 'disabled'}></label>
              <label class="field"><span>Machine / part</span><input data-f="machine" value="${state.machine || ''}" ${editable ? '' : 'disabled'}></label>
              <label class="field"><span>Target learner level</span><input data-f="experience_level" value="${state.experience_level || ''}" ${editable ? '' : 'disabled'}></label>
              <label class="field"><span>Tools & gauges <small class="muted">(comma-separated)</small></span><input data-f="tools" data-list value="${state.tools.join(', ')}" ${editable ? '' : 'disabled'}></label>
              <label class="field"><span>Materials <small class="muted">(comma-separated)</small></span><input data-f="materials" data-list value="${state.materials.join(', ')}" ${editable ? '' : 'disabled'}></label>
            </div>
            <div class="field"><span>Required skills</span><div class="row">${skills.map((s) => html`<button class="chip ${state.skill_ids.includes(s.id) ? 'on' : ''}" data-action="skill" data-id="${s.id}" ${editable ? '' : 'disabled'}>${s.code} · ${nm(s.name, s.name_ja)}</button>`)}</div></div>
          </section>

          <section class="card" id="sec-consent"><div class="card-h"><h2>2 · Consent & access</h2>${state.consent_given ? html`<span class="badge b-ok">${ic('shield', 12)} Consent recorded</span>` : html`<span class="badge b-warn">Required before processing</span>`}</div>
            <p class="muted small">${ctx.me.org.recording_policy || ''}</p>
            <label class="field"><span>Consent scope — who may view this recording and for what purpose</span>
              <textarea id="consent-scope" rows="2" ${editable ? '' : 'disabled'}>${state.consent_scope || ''}</textarea></label>
            ${state.consent_given ? html`<p class="small muted">Recorded ${relTime(state.consent_at)}. ${editable ? html`<a href="#" data-action="consent" data-v="0">Withdraw consent</a>` : ''}</p>`
              : editable ? html`<button class="btn btn-primary btn-sm" data-action="consent" data-v="1">${ic('check', 14)} Record expert consent</button>` : ''}
          </section>

          <section class="card" id="sec-source"><div class="card-h"><h2>3 · Recording & transcript</h2></div>
            <div class="grid g2">
              <div>
                <h4 style="margin-bottom:8px">Demonstration video</h4>
                ${v ? html`<video id="vid" controls preload="metadata" src="/api/files/${v.id}"></video>
                  <p class="small muted">${v.original_name} · ${bytes(v.size_bytes)} · sha256 ${v.sha256.slice(0, 10)}…</p>`
                  : html`<div class="dropzone" data-drop="video">${ic('upload', 22)}<p>Drop an MP4/WebM/MOV demonstration or click to upload</p><small>Stored privately on this server; streamed only to authorised users.</small></div>`}
                <div class="notice" style="margin-top:10px">${ic('sparkle', 16)}<div class="small">${providers.video.reason}</div></div>
              </div>
              <div>
                <div class="row between" style="margin-bottom:8px"><h4>Transcript</h4>
                  <span class="row">${editable ? html`<button class="btn btn-sm btn-ghost" data-action="upload-transcript">${ic('upload', 14)} Upload .vtt/.srt/.txt</button>
                    ${ctx.me.org.is_simulated ? html`<button class="btn btn-sm btn-ghost" data-action="sample" data-lang="en">${ic('file', 14)} Insert sample (simulated)</button>
                      <button class="btn btn-sm btn-ghost" data-action="sample" data-lang="ja" lang="ja">${ic('globe', 14)} 日本語サンプル</button>` : ''}` : ''}</span></div>
                <textarea id="transcript" rows="14" class="mono" style="font-size:12px" placeholder="[00:01:24] Expert: Put the back of your hand on the housing…" ${editable ? '' : 'disabled'}>${state.transcript}</textarea>
                <small class="muted">${txSegments()} timestamped lines detected · source: ${state.transcript_source}. Timestamps become evidence links.</small>
              </div>
            </div>
            <h4 style="margin:14px 0 8px">Supporting documents & images</h4>
            <div class="row">${state.files.filter((f) => f.kind !== 'video').map((f) => html`<a class="chip" href="/api/files/${f.id}" target="_blank" rel="noopener">${ic('file', 13)} ${f.original_name} <small class="muted">${bytes(f.size_bytes)}</small></a>`)}
              ${editable ? html`<button class="btn btn-sm btn-ghost" data-action="upload-doc">${ic('plus', 14)} Attach image or PDF</button>` : ''}</div>
            <input type="file" id="file-in" hidden>
          </section>

          <section class="card" id="sec-markers"><div class="card-h"><h2>4 · Demonstration markers<span class="sub">Timestamp what the expert <i>shows</i> — these become "Demonstrated" evidence</span></h2></div>
            ${editable ? html`<div class="row" style="margin-bottom:12px">
              <input id="mk-t" style="width:110px" class="mono" placeholder="00:01:24" aria-label="Timestamp">
              ${v ? html`<button class="btn btn-sm btn-ghost" data-action="now">${ic('clock', 14)} Use video time</button>` : ''}
              <select id="mk-kind" style="width:130px"><option value="step">Step</option><option value="checkpoint">Checkpoint</option><option value="tip">Tip / cue</option><option value="mistake">Mistake</option><option value="safety">Safety</option></select>
              <input id="mk-label" style="flex:1;min-width:180px" placeholder="What is being demonstrated?">
              <button class="btn btn-sm btn-primary" data-action="add-marker">${ic('plus', 14)} Add</button></div>` : ''}
            ${state.markers.length ? html`<div class="marker-list">${state.markers.map((m) => html`<div class="marker">
                <button class="btn btn-sm btn-ghost mono" data-action="seek" data-t="${m.t_seconds}">${ic('play', 12)} ${secToTs(m.t_seconds)}</button>
                <span class="badge b-neutral m-kind">${m.kind}</span><span>${m.label}${m.note ? html` <small class="muted">— ${m.note}</small>` : ''}</span>
                ${editable ? html`<button class="icon-btn" data-action="del-marker" data-id="${m.id}" aria-label="Delete marker">${ic('x', 14)}</button>` : html`<span></span>`}</div>`)}</div>`
              : html`<p class="muted small">No markers yet.</p>`}
          </section>

          <section class="card" id="sec-tacit"><div class="card-h"><h2>5 · Tacit knowledge<span class="sub">What the expert knows that is rarely written down — one item per line</span></h2></div>
            <div class="grid g2">
              ${[['tips', 'Practical tips & sensory cues', 'e.g. Hold the gauge by the insulated grip only…'], ['mistakes', 'Common mistakes', 'e.g. Zeroing in a ring that has not soaked…'],
                ['troubleshooting', 'Troubleshooting (symptom -> action)', 'e.g. Needle never turns around -> re-centre the gauge'], ['safety_notes', 'Safety notes', 'e.g. Use the lift assist for parts over 10 kg'],
              ].map(([f, label, ph]) => html`<label class="field"><span>${label}</span><textarea data-f="${f}" rows="4" placeholder="${ph}" ${editable ? '' : 'disabled'}>${state[f]}</textarea></label>`)}
            </div>
            <label class="field"><span>General expert notes</span><textarea data-f="expert_notes" rows="2" ${editable ? '' : 'disabled'}>${state.expert_notes}</textarea></label>
          </section>

          <section class="card accent" id="sec-extract"><div class="card-h"><h2>6 · Extract structured knowledge</h2></div>
            <p class="dim">The pipeline screens the material for prompt injection, extracts steps, checkpoints, tips, mistakes, failure modes and questions,
              then <b>verifies every evidence quote against your source</b>. Output goes to expert review — never straight to trainees.</p>
            <div class="grid g2" style="margin:12px 0">${providers.extractors.map((p) => html`<label class="check card flat" style="padding:12px">
              <input type="radio" name="provider" value="${p.name}" ${p.name === 'rule_based' ? 'checked' : ''} ${p.available ? '' : 'disabled'}>
              <span><b>${p.label}</b> ${p.available ? html`<span class="badge b-ok">available</span>` : html`<span class="badge b-neutral">not configured</span>`}<br><small class="muted">${p.reason}</small></span></label>`)}</div>
            ${!state.consent_given ? html`<div class="notice warn">${ic('shield', 16)} Record consent in section 2 before extraction.</div>` : ''}
            <div class="row" style="margin-top:10px">${ctx.can('extraction.run') ? html`<button class="btn btn-primary" data-action="extract" ${state.consent_given ? '' : 'disabled'}>${ic('sparkle', 16)} Run extraction</button>` : ''}
              ${state.procedure ? html`<a class="btn btn-ghost" href="#/procedures/${state.procedure.id}">Review ${state.procedure.code} ${ic('arrow', 14)}</a>` : ''}</div>
            <div id="extract-out"></div>
          </section>
        </div>
      </div>`);
  };
  draw();

  const onInput = (e) => {
    const f = e.target.dataset.f;
    if (!f || !editable) return;
    queue(f, e.target.dataset.list !== undefined ? e.target.value.split(',').map((s) => s.trim()).filter(Boolean) : e.target.value);
  };
  el.addEventListener('input', (e) => {
    if (e.target.id === 'transcript') { queue('transcript', e.target.value); queue('transcript_source', 'typed'); return; }
    onInput(e);
  });

  const upload = async (kind, accept) => {
    const input = $('#file-in', el);
    input.accept = accept; input.value = '';
    return new Promise((resolve) => {
      input.onchange = async () => {
        const f = input.files[0]; if (!f) return resolve(null);
        try {
          toast(`Uploading ${f.name}…`);
          const k = typeof kind === 'function' ? kind(f.name) : kind;
          const r = await api.upload(`/api/captures/${cap.id}/files?kind=${k}&name=${encodeURIComponent(f.name)}`, f);
          toast(`${f.name} uploaded`); resolve(r);
        } catch (e) { toastError(e); resolve(null); }
      };
      input.click();
    });
  };
  const reload = async () => { await save(); state = await api.get(`/api/captures/${cap.id}`); draw(); };

  el.addEventListener('click', (e) => { const dz = e.target.closest('[data-drop]'); if (dz && editable) upload('video', '.mp4,.webm,.mov,.m4v').then((r) => r && reload()); });
  el.addEventListener('dragover', (e) => { const dz = e.target.closest('[data-drop]'); if (dz) { e.preventDefault(); dz.classList.add('drag'); } });
  el.addEventListener('drop', async (e) => {
    const dz = e.target.closest('[data-drop]'); if (!dz || !editable) return;
    e.preventDefault(); const f = e.dataTransfer.files[0]; if (!f) return;
    try { toast(`Uploading ${f.name}…`); await api.upload(`/api/captures/${cap.id}/files?kind=video&name=${encodeURIComponent(f.name)}`, f); await reload(); }
    catch (err) { toastError(err); }
  });

  const off = actions(el, {
    jump: (b) => $(`#sec-${b.dataset.id}`, el).scrollIntoView({ behavior: 'smooth', block: 'start' }),
    skill: async (b) => {
      const ids = new Set(state.skill_ids);
      ids.has(b.dataset.id) ? ids.delete(b.dataset.id) : ids.add(b.dataset.id);
      state.skill_ids = [...ids]; b.classList.toggle('on'); queue('skill_ids', state.skill_ids);
    },
    consent: async (b) => {
      const give = b.dataset.v === '1';
      state = await api.patch(`/api/captures/${cap.id}`, { consent_given: give, consent_scope: $('#consent-scope', el).value });
      toast(give ? 'Consent recorded' : 'Consent withdrawn'); draw();
    },
    sample: async (b) => {
      const lang = b.dataset.lang || 'en';
      const s = await api.get(`/api/samples/capture?lang=${lang}`);
      if (state.transcript.trim() && !(await modal({ title: 'Replace transcript?', body: html`<p>This replaces the current transcript with the simulated sample.</p>`, actions: [{ label: 'Cancel' }, { label: 'Replace', value: true }] }))) return;
      // Tacit-knowledge notes are only filled where the capture has none, never overwritten.
      const body = { transcript: s.transcript, transcript_source: 'sample' };
      for (const f of ['tips', 'mistakes', 'troubleshooting', 'safety_notes', 'expert_notes']) if (!state[f].trim()) body[f] = s[f];
      if (!state.markers.length) {
        for (const [t, kind, label, note] of s.markers) await api.post(`/api/captures/${cap.id}/markers`, { t_seconds: t, kind, label, note });
      }
      state = await api.patch(`/api/captures/${cap.id}`, body);
      toast(lang === 'ja' ? '日本語サンプル（シミュレーション）を挿入しました' : 'Sample transcript inserted (simulated data)'); draw();
    },
    'upload-transcript': async () => { if (await upload('transcript', '.vtt,.srt,.txt')) await reload(); },
    'upload-doc': async () => {
      const r = await upload((n) => (/\.(png|jpe?g|webp)$/i.test(n) ? 'image' : 'document'), '.pdf,.txt,.md,.png,.jpg,.jpeg,.webp');
      if (r === null) return; await reload();
    },
    now: () => { const vid = $('#vid', el); if (vid) $('#mk-t', el).value = secToTs(vid.currentTime); },
    seek: (b) => { const vid = $('#vid', el); if (vid) { vid.currentTime = +b.dataset.t; vid.play(); vid.scrollIntoView({ block: 'center', behavior: 'smooth' }); } else toast('No video attached — marker time ' + secToTs(+b.dataset.t)); },
    'add-marker': async () => {
      const tval = $('#mk-t', el).value.trim();
      const secs = /^\d+(\.\d+)?$/.test(tval) ? +tval : tsToSec(tval);
      await api.post(`/api/captures/${cap.id}/markers`, { t_seconds: secs, kind: $('#mk-kind', el).value, label: $('#mk-label', el).value });
      await reload(); toast('Marker added');
    },
    'del-marker': async (b) => { await api.del(`/api/captures/${cap.id}/markers/${b.dataset.id}`); await reload(); },
    extract: async () => {
      await save();
      const provider = ($('input[name=provider]:checked', el) || {}).value || 'rule_based';
      const out = $('#extract-out', el);
      mount(out, html`<div class="notice" style="margin-top:12px">${ic('sparkle', 16)} Extracting with ${provider}… parsing transcript, classifying statements, verifying evidence.</div>`);
      try {
        const r = await api.post(`/api/captures/${cap.id}/extract`, { provider });
        const s = r.meta.stats;
        mount(out, html`<div class="extract-result">
            <div><b>${s.steps}</b><small class="muted">steps (${s.steps_demonstrated} demonstrated)</small></div>
            <div><b>${s.steps_verified}/${s.steps}</b><small class="muted">steps evidence-verified</small></div>
            <div><b>${s.tips + s.mistakes}</b><small class="muted">tips & common mistakes</small></div>
            <div><b>${s.failure_modes}</b><small class="muted">troubleshooting branches</small></div>
            <div><b>${s.questions + s.scenarios}</b><small class="muted">assessment items</small></div>
            <div><b>${s.safety}</b><small class="muted">safety items</small></div>
            <div><b>${s.open_questions}</b><small class="muted">open questions for the expert</small></div>
            <div><b>${r.meta.duration_ms} ms</b><small class="muted">${r.meta.provider_label}</small></div></div>
          ${r.meta.injection_findings.length ? html`<div class="notice danger">${ic('shield', 16)}<div><b>Instruction-like text found in the source and ignored:</b>
            ${r.meta.injection_findings.map((f) => html`<div class="small mono">line ${f.line}: ${f.excerpt}</div>`)}</div></div>` : ''}
          <div class="notice warn" style="margin:10px 0">${ic('flag', 16)} Status: AI_PROCESSED — not approved. Video analysed by AI: no (markers are expert annotations).</div>
          <a class="btn btn-primary" href="#/procedures/${r.procedure_id}">Open for expert review ${ic('arrow', 14)}</a>`);
        state = await api.get(`/api/captures/${cap.id}`); refreshNav();
        ctx.refreshNotifications();
      } catch (e) {
        mount(out, html`<div class="notice danger" style="margin-top:12px">${ic('risk', 16)}<div><b>Extraction failed:</b> ${e.message}
          ${e.details?.retryable ? html`<br><small>This error is temporary — retry shortly.</small>` : ''}
          ${e.details?.version_id ? html`<br><small>Review or reject the existing extracted version first.</small>` : ''}
          <br><small>No result was fabricated. You can choose another provider explicitly.</small></div></div>`);
      }
    },
  });
  return () => { off(); clearTimeout(saveTimer); if (Object.keys(pending).length) save(); };
}
