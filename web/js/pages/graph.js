import { api } from '../api.js';
import { html, mount, $, actions, ic, esc, loading, evidenceBadge, statusBadge } from '../ui.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const TYPES = {
  expert: ['Expert', '#f2a93b', 9], employee: ['Employee', '#6ea8fe', 7], procedure: ['Procedure', '#45c48a', 10],
  module: ['Training module', '#3cc6b4', 7], skill: ['Skill', '#b29dff', 9], step: ['Operational step', '#8a96a3', 5],
  machine: ['Machine', '#d7895b', 8], equipment: ['Tool / gauge', '#6b7680', 5], failure_mode: ['Failure mode', '#f0625f', 6],
  checkpoint: ['Quality checkpoint', '#ffc46b', 6], evidence: ['Evidence', '#4b5560', 4],
};
const DEFAULT_ON = ['expert', 'employee', 'procedure', 'module', 'skill', 'machine', 'failure_mode', 'checkpoint'];
const REL = { holds: 'holds', practises: 'practises', demonstrated: 'demonstrated', taught_as: 'taught as', teaches: 'teaches',
  performed_on: 'performed on', uses: 'uses', contains: 'contains', requires: 'requires', has_evidence: 'has evidence',
  verified_by: 'verified by', mitigated_by: 'mitigated by', competent_in: 'competent in', training_in: 'training in' };

export async function render(el, ctx) {
  mount(el, loading(2));
  const g = await api.get('/api/graph');
  const byId = Object.fromEntries(g.nodes.map((n) => [n.id, n]));
  let on = new Set(DEFAULT_ON); let sel = ctx.query.focus && byId[ctx.query.focus] ? ctx.query.focus : null;
  if (sel && !on.has(byId[sel].type)) on.add(byId[sel].type);
  let pos = {}; let view = { x: 0, y: 0, k: 1 }; let filterText = '';

  mount(el, html`
    ${pageHead({ eyebrow: 'Module D', icon: 'graph', title: t('graph.title'), sub: t('graph.sub'),
      actions: html`<input id="g-find" type="search" placeholder="Find a node…" style="width:220px" aria-label="Find node">` })}
    <div class="graph-wrap" id="gw">
      <svg id="gsvg" role="img" aria-label="Knowledge graph"><g id="gview"><g id="gedges"></g><g id="gnodes"></g></g></svg>
      <div class="graph-tools">${Object.entries(TYPES).map(([k, [l, c]]) => html`<button class="chip ${on.has(k) ? 'on' : ''}" data-action="type" data-t="${k}"><span class="nd" style="background:${c}"></span>${l} <small>${g.counts[k] || 0}</small></button>`)}</div>
      <div class="graph-side" id="gside"></div>
      <div class="graph-legend small muted">${g.nodes.length} nodes · ${g.edges.length} relationships · built live from the database · drag to pan, scroll to zoom</div>
    </div>`);
  const svg = $('#gsvg', el); const side = $('#gside', el);

  const visible = () => g.nodes.filter((n) => on.has(n.type));
  const visEdges = (ids) => g.edges.filter((e) => ids.has(e.source) && ids.has(e.target));

  function layout() {
    const nodes = visible(); const ids = new Set(nodes.map((n) => n.id)); const edges = visEdges(ids);
    const W = svg.clientWidth || 1000; const H = svg.clientHeight || 600;
    const ring = { skill: 0.0, procedure: 0.35, expert: 0.55, employee: 0.7, module: 0.45, machine: 0.8, equipment: 0.85, step: 0.6, checkpoint: 0.75, failure_mode: 0.9, evidence: 0.95 };
    nodes.forEach((n, i) => {
      if (pos[n.id]) return;
      const a = (i / nodes.length) * Math.PI * 2 * 3.1; const r = (ring[n.type] ?? 0.6) * Math.min(W, H) * 0.45 + 20;
      pos[n.id] = { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r };
    });
    const k = Math.sqrt((W * H) / Math.max(1, nodes.length)) * 0.62;
    for (let it = 0; it < 260; it++) {
      const temp = 18 * (1 - it / 260) + 0.5; const disp = {};
      nodes.forEach((n) => { disp[n.id] = { x: 0, y: 0 }; });
      for (let i = 0; i < nodes.length; i++) {
        const a = pos[nodes[i].id];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = pos[nodes[j].id]; let dx = a.x - b.x; let dy = a.y - b.y; let d2 = dx * dx + dy * dy || 0.01;
          if (d2 > 160000) continue;
          const f = (k * k) / d2; dx *= f; dy *= f;
          disp[nodes[i].id].x += dx; disp[nodes[i].id].y += dy; disp[nodes[j].id].x -= dx; disp[nodes[j].id].y -= dy;
        }
      }
      edges.forEach((e) => {
        const a = pos[e.source]; const b = pos[e.target]; const dx = a.x - b.x; const dy = a.y - b.y; const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const f = (d * d) / k / d * 0.9; disp[e.source].x -= dx * f; disp[e.source].y -= dy * f; disp[e.target].x += dx * f; disp[e.target].y += dy * f;
      });
      nodes.forEach((n) => {
        const p = pos[n.id]; const dd = disp[n.id];
        dd.x += (W / 2 - p.x) * 0.02; dd.y += (H / 2 - p.y) * 0.02;
        const len = Math.sqrt(dd.x * dd.x + dd.y * dd.y) || 1;
        p.x += (dd.x / len) * Math.min(len, temp); p.y += (dd.y / len) * Math.min(len, temp);
      });
    }
  }

  function neighbours(id) {
    const s = new Set([id]);
    g.edges.forEach((e) => { if (e.source === id) s.add(e.target); if (e.target === id) s.add(e.source); });
    return s;
  }

  function draw() {
    const nodes = visible(); const ids = new Set(nodes.map((n) => n.id)); const edges = visEdges(ids);
    const nb = sel ? neighbours(sel) : null; const ft = filterText.toLowerCase();
    $('#gview', el).setAttribute('transform', `translate(${view.x},${view.y}) scale(${view.k})`);
    $('#gedges', el).innerHTML = edges.map((e) => {
      const a = pos[e.source]; const b = pos[e.target];
      const hl = sel && (e.source === sel || e.target === sel); const dim = sel && !hl;
      return `<line class="g-edge ${hl ? 'hl' : ''} ${dim ? 'dim' : ''}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${esc(byId[e.source].label)} — ${REL[e.rel] || e.rel} → ${esc(byId[e.target].label)}</title></line>`;
    }).join('');
    $('#gnodes', el).innerHTML = nodes.map((n) => {
      const [, c, r] = TYPES[n.type]; const p = pos[n.id];
      const match = ft && n.label.toLowerCase().includes(ft);
      const dim = (nb && !nb.has(n.id)) || (ft && !match);
      const showLabel = view.k > 0.75 || ['skill', 'procedure', 'expert', 'machine'].includes(n.type) || (nb && nb.has(n.id)) || match;
      const rr = r + Math.min(6, (n.degree || 0) * 0.4);
      return `<g class="g-node ${dim ? 'dim' : ''} ${n.id === sel ? 'sel' : ''} ${nb && nb.has(n.id) ? 'hl' : ''}" data-id="${esc(n.id)}" transform="translate(${p.x},${p.y})" tabindex="0" role="button" aria-label="${esc(TYPES[n.type][0])}: ${esc(n.label)}">
        <circle r="${rr}" fill="${c}" ${n.type === 'procedure' && n.status !== 'PUBLISHED' ? 'stroke-dasharray="3 2" fill-opacity="0.45"' : ''}${n.type === 'evidence' && !n.verified ? ' fill-opacity="0.4"' : ''}></circle>
        ${showLabel ? `<text x="${rr + 4}" y="4">${esc(n.label.length > 34 ? n.label.slice(0, 33) + '…' : n.label)}</text>` : ''}</g>`;
    }).join('');
    drawSide();
  }

  function link(n) {
    if (n.type === 'procedure' || n.type === 'step' || n.type === 'evidence' || n.type === 'checkpoint' || n.type === 'failure_mode')
      return `#/procedures/${n.procedure_id}${n.step_id ? `?step=${n.step_id}` : ''}`;
    if (n.type === 'module') return `#/academy/${n.procedure_id}`;
    if (n.type === 'skill') return ctx.can('risk.view') ? `#/risk?skill=${n.code}` : '#/academy';
    if (n.type === 'expert' || n.type === 'employee') return `#/people/${n.person_id}`;
    return null;
  }

  function drawSide() {
    if (!sel) {
      side.innerHTML = String(html`<h3>Explore the graph</h3><p class="small dim">Select any node to see its relationships. Try a skill to find the procedure and module that teach it, the experts who hold it and who is competent in it.</p>
        <div class="small muted" style="margin-top:8px">Most connected skills</div>
        ${g.nodes.filter((n) => n.type === 'skill').sort((a, b) => b.degree - a.degree).slice(0, 8).map((n) => html`<button class="rel" data-sel="${n.id}"><span class="nd" style="background:${TYPES.skill[1]}"></span>${nm(n.label, n.name_ja)}<small class="muted" style="margin-left:auto">${n.degree}</small></button>`)}`);
      return;
    }
    const n = byId[sel]; const out = g.edges.filter((e) => e.source === sel); const inn = g.edges.filter((e) => e.target === sel);
    const href = link(n);
    side.innerHTML = String(html`<div class="row between"><span class="badge" style="background:${TYPES[n.type][1]}22;color:${TYPES[n.type][1]}">${TYPES[n.type][0]}</span>
        <button class="icon-btn" data-sel="" aria-label="Clear selection">${ic('x', 14)}</button></div>
      <h3 style="margin:8px 0 4px">${n.label}</h3>
      ${n.name_ja ? html`<div class="small muted">${n.name_ja}</div>` : ''}${n.title ? html`<div class="small muted">${n.title}</div>` : ''}
      ${n.status ? html`<div style="margin:6px 0">${statusBadge(n.status)}</div>` : ''}
      ${n.type === 'step' || n.type === 'evidence' ? html`<div style="margin:6px 0">${evidenceBadge(n.source_type || 'transcript', n.verified)}</div>` : ''}
      ${n.quote ? html`<div class="quote">“${n.quote}”</div>` : ''}${n.detail ? html`<p class="small dim">${n.detail}</p>` : ''}${n.action ? html`<p class="small dim">→ ${n.action}</p>` : ''}
      ${href ? html`<a class="btn btn-sm btn-primary" href="${href}" style="margin:8px 0">Open ${ic('arrow', 13)}</a>` : ''}
      ${[['Outgoing', out, 'target'], ['Incoming', inn, 'source']].map(([label, list, key]) => list.length ? html`<div class="small muted" style="margin-top:10px">${label} (${list.length})</div>
        ${list.slice(0, 40).map((e) => { const o = byId[e[key]]; return html`<button class="rel" data-sel="${o.id}"><span class="r-type">${REL[e.rel] || e.rel}</span><span class="nd" style="background:${TYPES[o.type][1]}"></span>${o.label}</button>`; })}` : '')}`);
  }

  layout();
  if (sel && pos[sel]) { view.x = (svg.clientWidth - 340) / 2 - pos[sel].x; view.y = svg.clientHeight / 2 - pos[sel].y; }
  draw();

  // interactions: select, pan, zoom, drag
  let drag = null;
  svg.addEventListener('pointerdown', (e) => {
    const nodeEl = e.target.closest('.g-node');
    drag = { node: nodeEl ? nodeEl.dataset.id : null, x: e.clientX, y: e.clientY, moved: false };
    svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x; const dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (!drag.moved) return;
    if (drag.node) { pos[drag.node].x += dx / view.k; pos[drag.node].y += dy / view.k; } else { view.x += dx; view.y += dy; }
    drag.x = e.clientX; drag.y = e.clientY; draw();
  });
  svg.addEventListener('pointerup', () => {
    if (drag && !drag.moved) { sel = drag.node || null; draw(); }
    drag = null;
  });
  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect(); const mx = e.clientX - rect.left; const my = e.clientY - rect.top;
    const f = e.deltaY < 0 ? 1.12 : 1 / 1.12; const nk = Math.max(0.3, Math.min(3, view.k * f));
    view.x = mx - (mx - view.x) * (nk / view.k); view.y = my - (my - view.y) * (nk / view.k); view.k = nk; draw();
  }, { passive: false });
  svg.addEventListener('keydown', (e) => { const n = e.target.closest('.g-node'); if (n && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); sel = n.dataset.id; draw(); } });
  side.addEventListener('click', (e) => {
    const b = e.target.closest('[data-sel]'); if (!b) return;
    sel = b.dataset.sel || null;
    if (sel && !on.has(byId[sel].type)) { on.add(byId[sel].type); layout(); el.querySelector(`[data-t="${byId[sel].type}"]`)?.classList.add('on'); }
    draw();
  });
  $('#g-find', el).addEventListener('input', (e) => { filterText = e.target.value.trim(); draw(); });
  return actions(el, {
    type: (b) => { const k = b.dataset.t; on.has(k) ? on.delete(k) : on.add(k); b.classList.toggle('on'); if (sel && !on.has(byId[sel].type)) sel = null; layout(); draw(); },
  });
}
