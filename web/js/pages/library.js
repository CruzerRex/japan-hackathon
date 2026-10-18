import { api } from '../api.js';
import { html, mount, actions, ic, avatar, relTime, statusBadge, empty, modal, $, loading } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const FILTERS = [['all', 'All'], ['PUBLISHED', 'Published'], ['review', 'Awaiting review'], ['REJECTED', 'Rejected']];

export async function render(el, ctx) {
  mount(el, loading(4));
  const { procedures } = await api.get('/api/procedures');
  let filter = ctx.query.filter || 'all';
  const match = (p) => filter === 'all' || (filter === 'review' ? !['PUBLISHED', 'REJECTED', 'SUPERSEDED'].includes(p.latest_status) : p.latest_status === filter);
  const draw = () => {
    const rows = procedures.filter(match);
    mount(el, html`
      ${pageHead({ eyebrow: 'Modules C · J', icon: 'library', title: t('library.title'), sub: t('library.sub'),
        actions: ctx.can('procedure.create') ? html`<button class="btn btn-ghost" data-action="new">${ic('edit', 16)} Author manually</button>
          <a class="btn btn-primary" href="#/capture">${ic('capture', 16)} Capture from an expert</a>` : '' })}
      <div class="tabs">${FILTERS.map(([k, l]) => html`<button class="tab ${filter === k ? 'on' : ''}" data-action="filter" data-k="${k}">${l}
        <span class="badge b-neutral">${procedures.filter((p) => k === 'all' || (k === 'review' ? !['PUBLISHED', 'REJECTED', 'SUPERSEDED'].includes(p.latest_status) : p.latest_status === k)).length}</span></button>`)}</div>
      ${rows.length ? html`<div class="card" style="padding:6px 8px"><div class="table-wrap"><table>
        <thead><tr><th>Procedure</th><th>Source expert</th><th>Skills</th><th>Latest</th><th>Evidence</th><th>Training</th><th>Updated</th></tr></thead>
        <tbody>${rows.map((p) => html`<tr class="clickable" data-action="open" data-id="${p.id}">
          <td><b class="mono">${p.code}</b> ${p.title}<span class="sub">${p.machine}</span></td>
          <td><span class="row">${avatar(p.owner_name, 'xs')} ${nm(p.owner_name, p.owner_name_ja)}</span></td>
          <td>${p.skills.map((s) => html`<span class="skill-tag">${s}</span> `)}</td>
          <td>v${p.latest_version_no} ${statusBadge(p.latest_status)}${p.published_version_no && p.published_version_no !== p.latest_version_no ? html`<span class="sub">v${p.published_version_no} published</span>` : ''}</td>
          <td><span class="mono">${p.verified_steps}/${p.step_count}</span><span class="sub">steps verified${p.safety_critical_steps ? ` · ${p.safety_critical_steps} safety-critical` : ''}</span></td>
          <td>${p.published_version_id ? html`<span class="badge b-ok">${p.question_count} items</span>` : html`<span class="muted small">not published</span>`}</td>
          <td class="small muted">${relTime(p.updated_at)}</td></tr>`)}</tbody></table></div></div>`
        : html`<div class="card">${empty('Nothing here yet', filter === 'all' ? 'Capture an expert demonstration to create the first procedure.' : 'No procedures match this filter.')}</div>`}`);
  };
  draw();
  return actions(el, {
    filter: (b) => { filter = b.dataset.k; draw(); },
    open: (r) => ctx.go(`#/procedures/${r.dataset.id}`),
    new: async () => {
      const r = await modal({
        title: 'Author a procedure manually',
        body: html`<p class="muted small">Manual steps are marked "Expert-authored". The draft still goes through review before publishing.</p>
          <label class="field"><span>Title</span><input id="np-title"></label>
          <label class="field"><span>First step title</span><input id="np-step" value="Prepare the work area"></label>
          <label class="field"><span>First step instruction</span><textarea id="np-instr" rows="3"></textarea></label>`,
        actions: [{ label: 'Cancel' }, { label: 'Create draft', onClick: (w) => api.post('/api/procedures', { content: {
          title: $('#np-title', w).value, steps: [{ title: $('#np-step', w).value, instruction: $('#np-instr', w).value, source_type: 'expert_edit' }] } }) }],
      });
      if (r && r.procedure_id) ctx.go(`#/procedures/${r.procedure_id}`);
    },
  });
}
