import { api } from '../api.js';
import { html, mount, $, $$, actions, ic, avatar, compBadge, fmtDate, relTime, empty, modal, toast, loading } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const ST = { requested: 'b-warn', accepted: 'b-ok', declined: 'b-danger', completed: 'b-info', cancelled: 'b-neutral' };

export async function render(el, ctx) {
  mount(el, loading(3));
  let d = await api.get('/api/mentorship');
  let skillFilter = ctx.query.skill || '';
  const meId = ctx.me.user.id;
  const draw = () => {
    const mentors = d.mentors.filter((m) => !skillFilter || m.skills.some((s) => s.id === skillFilter));
    const mine = d.requests;
    mount(el, html`
      ${pageHead({ eyebrow: 'Module H', icon: 'mentor', title: t('mentorship.title'), sub: t('mentorship.sub') })}
      <div class="notice info" style="margin-bottom:16px">${ic('clock', 16)}<div>Scheduling is handled in-app (no calendar integration is configured). Sessions record notes, mentor feedback and follow-up tasks against the learner's competency.</div></div>
      <div class="grid g-side">
        <div class="stack">
          <div class="card"><div class="card-h"><h2>Mentoring relationships<span class="sub">${mine.length} total</span></h2></div>
            ${mine.length ? mine.map((r) => {
              const isMentor = r.mentor_id === meId; const isMentee = r.mentee_id === meId;
              return html`<div class="req" style="margin-bottom:12px">
                <div class="row between"><span class="row">${avatar(r.mentee_name, 'sm')} <b>${nm(r.mentee_name, r.mentee_name_ja)}</b> ${ic('arrow', 14)} ${avatar(r.mentor_name, 'sm')} <b>${nm(r.mentor_name, r.mentor_name_ja)}</b></span>
                  <span class="badge ${ST[r.status]}">${r.status}</span></div>
                <div class="row small muted">${r.skill_name ? html`<span class="skill-tag">${r.skill_code} · ${r.skill_name}</span>` : ''} ${r.mentee_languages ? `· mentee languages: ${r.mentee_languages}` : ''} · ${relTime(r.created_at)}
                  ${r.mentee_competency ? html` · learner progress ${compBadge(r.mentee_competency.status)}` : ''}</div>
                <p class="dim" style="margin:0">“${r.message}”</p>${r.response_note ? html`<small class="muted">Mentor: ${r.response_note}</small>` : ''}
                ${r.sessions.map((s) => html`<div class="session"><div class="row between"><b>${ic('clock', 14)} ${fmtDate(s.scheduled_at, true)} · ${s.duration_min} min · ${s.mode}${s.location ? ` · ${s.location}` : ''}</b>
                    <span class="badge ${s.status === 'completed' ? 'b-ok' : s.status === 'scheduled' ? 'b-info' : 'b-neutral'}">${s.status}</span></div>
                  ${s.agenda ? html`<p class="small dim">Agenda: ${s.agenda}</p>` : ''}
                  ${s.notes ? html`<p class="small"><b>Notes:</b> ${s.notes}</p>` : ''}${s.mentor_feedback ? html`<p class="small"><b>Mentor feedback:</b> ${s.mentor_feedback}</p>` : ''}
                  ${s.followups.length ? html`<div class="small muted" style="margin-top:6px">Follow-ups</div>${s.followups.map((f) => html`<label class="followup ${f.done ? 'done' : ''}"><input type="checkbox" data-fu="${f.id}" ${f.done ? 'checked' : ''}><span>${f.description} <small class="muted">(${f.owner_name})</small></span></label>`)}` : ''}
                  ${isMentor || isMentee ? html`<div class="row" style="margin-top:8px">
                    <button class="btn btn-sm btn-ghost" data-action="notes" data-id="${s.id}" data-mentor="${isMentor ? 1 : 0}">${ic('edit', 13)} Notes${isMentor ? ' & feedback' : ''}</button>
                    <button class="btn btn-sm btn-ghost" data-action="followup" data-id="${s.id}" data-mentee="${r.mentee_id}" data-mentor-id="${r.mentor_id}">${ic('plus', 13)} Follow-up</button>
                    ${s.status === 'scheduled' ? html`<button class="btn btn-sm btn-ghost" data-action="complete-s" data-id="${s.id}">${ic('check', 13)} Mark held</button>` : ''}</div>` : ''}</div>`)}
                <div class="row">
                  ${isMentor && r.status === 'requested' ? html`<button class="btn btn-sm btn-ok" data-action="respond" data-id="${r.id}" data-a="accept">Accept</button><button class="btn btn-sm btn-danger" data-action="respond" data-id="${r.id}" data-a="decline">Decline</button>` : ''}
                  ${(isMentor || isMentee) && r.status === 'accepted' ? html`<button class="btn btn-sm btn-primary" data-action="schedule" data-id="${r.id}">${ic('clock', 13)} Schedule session</button>
                    <button class="btn btn-sm btn-ghost" data-action="respond" data-id="${r.id}" data-a="complete">Close mentorship</button>` : ''}
                  ${r.procedure_code ? html`<span class="small muted">Shared procedure: ${r.procedure_code}</span>` : ''}</div>
              </div>`;
            }) : empty('No mentoring yet', 'Find a mentor on the right and send a request.')}</div>
        </div>
        <div class="stack">
          <div class="card"><div class="card-h"><h2>Find a mentor</h2></div>
            <select id="sk-filter" aria-label="Filter by skill"><option value="">All skills</option>${d.skills.map((s) => html`<option value="${s.id}" ${skillFilter === s.id ? 'selected' : ''}>${s.code} · ${nm(s.name, s.name_ja)}</option>`)}</select>
            <div class="stack" style="margin-top:12px;gap:12px">${mentors.map((m) => html`<div class="mentor card flat">
              <div class="mentor-top">${avatar(m.name, 'md')}<span><b>${nm(m.name, m.name_ja)}</b><small>${m.title} · ${m.years_experience} yrs · ${m.languages}</small></span></div>
              ${m.bio ? html`<p class="small dim" style="margin:0">${m.bio}</p>` : ''}
              <div class="skill-tags">${m.skills.map((s) => html`<span class="skill-tag">${nm(s.name, s.name_ja)}<b>${s.proficiency}</b></span>`)}</div>
              <div class="row small muted">${m.active_mentees} active mentee(s)${m.procedures.length ? ` · teaches ${m.procedures.map((p) => p.code).join(', ')}` : ''}</div>
              ${m.id !== meId ? html`<button class="btn btn-sm btn-primary" data-action="request" data-id="${m.id}">Request mentoring</button>` : ''}</div>`)}</div></div>
        </div>
      </div>`);
    $('#sk-filter', el).addEventListener('change', (e) => { skillFilter = e.target.value; draw(); });
    $$('[data-fu]', el).forEach((c) => c.addEventListener('change', async () => { await api.patch(`/api/followups/${c.dataset.fu}`, { done: c.checked }); c.closest('.followup').classList.toggle('done', c.checked); }));
  };
  const refresh = async () => { d = await api.get('/api/mentorship'); draw(); };
  draw();
  return actions(el, {
    request: async (b) => {
      const m = d.mentors.find((x) => x.id === b.dataset.id);
      const r = await modal({ title: `Request mentoring from ${m.name}`, body: html`
        <label class="field"><span>Skill</span><select id="rq-skill">${m.skills.map((s) => html`<option value="${s.id}" ${skillFilter === s.id ? 'selected' : ''}>${s.name}</option>`)}</select></label>
        <label class="field"><span>Shared procedure (optional)</span><select id="rq-proc"><option value="">—</option>${m.procedures.map((p) => html`<option value="${p.id}">${p.code} · ${p.title}</option>`)}</select></label>
        <label class="field"><span>What do you want to learn?</span><textarea id="rq-msg" rows="3"></textarea></label>`,
        actions: [{ label: 'Cancel' }, { label: 'Send request', onClick: (w) => api.post('/api/mentorship/requests', { mentor_id: m.id, skill_id: $('#rq-skill', w).value, procedure_id: $('#rq-proc', w).value || null, message: $('#rq-msg', w).value }) }] });
      if (r) { toast('Request sent'); refresh(); }
    },
    respond: async (b) => { await api.post(`/api/mentorship/requests/${b.dataset.id}/respond`, { action: b.dataset.a }); toast(`Mentorship ${b.dataset.a}ed`); ctx.refreshNotifications(); refresh(); },
    schedule: async (b) => {
      const def = new Date(Date.now() + 3 * 864e5); def.setHours(14, 0, 0, 0);
      const local = new Date(def.getTime() - def.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
      const r = await modal({ title: 'Schedule a session', body: html`
        <div class="grid g2"><label class="field"><span>Date & time</span><input type="datetime-local" id="ss-at" value="${local}"></label>
          <label class="field"><span>Duration (min)</span><input type="number" id="ss-dur" value="60" min="15" max="480"></label></div>
        <div class="grid g2"><label class="field"><span>Mode</span><select id="ss-mode"><option value="onsite">On-site</option><option value="remote">Remote (video)</option></select></label>
          <label class="field"><span>Location / link</span><input id="ss-loc" placeholder="Inspection room, bench 2"></label></div>
        <label class="field"><span>Agenda</span><textarea id="ss-agenda" rows="2"></textarea></label>`,
        actions: [{ label: 'Cancel' }, { label: 'Schedule', onClick: (w) => api.post(`/api/mentorship/requests/${b.dataset.id}/sessions`, { scheduled_at: $('#ss-at', w).value, duration_min: +$('#ss-dur', w).value, mode: $('#ss-mode', w).value, location: $('#ss-loc', w).value, agenda: $('#ss-agenda', w).value }) }] });
      if (r) { toast('Session scheduled'); refresh(); }
    },
    notes: async (b) => {
      const s = d.requests.flatMap((r) => r.sessions).find((x) => x.id === b.dataset.id);
      const isMentor = b.dataset.mentor === '1';
      const r = await modal({ title: 'Session notes', body: html`<label class="field"><span>Shared notes</span><textarea id="sn-notes" rows="4">${s.notes}</textarea></label>
        ${isMentor ? html`<label class="field"><span>Mentor feedback on the learner</span><textarea id="sn-fb" rows="3">${s.mentor_feedback}</textarea></label>` : ''}`,
        actions: [{ label: 'Cancel' }, { label: 'Save', onClick: (w) => api.patch(`/api/mentorship/sessions/${s.id}`, isMentor ? { notes: $('#sn-notes', w).value, mentor_feedback: $('#sn-fb', w).value } : { notes: $('#sn-notes', w).value }) }] });
      if (r) { toast('Saved'); refresh(); }
    },
    followup: async (b) => {
      const r = await modal({ title: 'Add follow-up task', body: html`<label class="field"><span>Task</span><input id="fu-d"></label>
        <label class="field"><span>Owner</span><select id="fu-o"><option value="${b.dataset.mentee}">Mentee</option><option value="${b.dataset.mentorId}">Mentor</option></select></label>`,
        actions: [{ label: 'Cancel' }, { label: 'Add', onClick: (w) => api.post(`/api/mentorship/sessions/${b.dataset.id}/followups`, { description: $('#fu-d', w).value, owner_id: $('#fu-o', w).value }) }] });
      if (r) refresh();
    },
    'complete-s': async (b) => { await api.patch(`/api/mentorship/sessions/${b.dataset.id}`, { status: 'completed' }); toast('Session marked as held'); refresh(); },
  });
}
