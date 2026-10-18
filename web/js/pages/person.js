import { api } from '../api.js';
import { html, mount, avatar, compBadge, outcomeBadge, fmtDate, empty, loading, ic } from '../ui.js';
import { sparkline } from '../charts.js';
import { nm } from '../i18n.js';
import { pageHead } from './_common.js';

export async function render(el, ctx) {
  mount(el, loading(3));
  const d = await api.get(`/api/people/${ctx.params.id}`);
  const u = d.user;
  mount(el, html`
    ${pageHead({ crumb: { href: '#/competency', label: 'Competency Matrix' }, eyebrow: u.role, icon: 'users', title: nm(u.name, u.name_ja),
      sub: html`${u.title} · ${u.department || ''} · languages: ${u.languages || '—'}${u.years_experience != null ? ` · ${u.years_experience} yrs experience` : ''}
        ${u.retirement_date ? html` · <span style="color:var(--warn)">planned retirement ${fmtDate(u.retirement_date)}</span>` : ''}` })}
    ${u.bio ? html`<p class="dim" style="margin:-8px 0 16px">${u.bio}</p>` : ''}
    <div class="grid g2">
      <div class="card"><div class="card-h"><h2>Competencies</h2></div>
        ${d.competencies.length ? d.competencies.map((c) => html`<div class="row between" style="padding:6px 0;border-bottom:1px solid var(--line)"><span>${nm(c.name, c.name_ja)} <small class="mono muted">${c.code}</small></span>
          <span class="row">${c.score != null ? html`<span class="mono small">${c.score}</span>` : ''}${compBadge(c.status)}</span></div>`) : empty('No competency records', 'Records appear when this person starts a training module.')}
        ${d.held_skills.length ? html`<div class="sep"></div><h3 style="margin-bottom:8px">Expert knowledge held</h3><div class="skill-tags">${d.held_skills.map((s) => html`<span class="skill-tag">${nm(s.name, s.name_ja)}<b>P${s.proficiency}</b></span>`)}</div>` : ''}</div>
      <div class="card"><div class="card-h"><h2>Assessment history</h2>${d.attempts.length > 1 ? sparkline(d.attempts.map((a) => a.score)) : ''}</div>
        ${d.attempts.length ? html`<div class="table-wrap"><table><tbody>${d.attempts.map((a) => html`<tr><td><a href="#/attempts/${a.id}">${a.code}</a> #${a.attempt_no}<span class="sub">${a.title}</span></td>
          <td class="mono">${a.score}</td><td>${outcomeBadge(a.outcome)}</td><td class="small muted">${fmtDate(a.submitted_at)}</td></tr>`)}</tbody></table></div>` : empty('No assessments', '')}
        ${d.remediation.length ? html`<div class="sep"></div><h3 style="margin-bottom:8px">${ic('flag', 15)} Remediation</h3>${d.remediation.map((r) => html`<p class="small">${r.status === 'done' ? '✓' : '•'} ${r.description}</p>`)}` : ''}</div>
    </div>`);
}
