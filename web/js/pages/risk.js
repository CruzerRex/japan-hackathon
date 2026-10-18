import { api } from '../api.js';
import { html, mount, actions, ic, avatar, bandBadge, meter, fmtDate, empty, loading } from '../ui.js';
import { donut } from '../charts.js';
import { t, nm } from '../i18n.js';
import { pageHead } from './_common.js';

const RICON = { capture: 'capture', review: 'shield', training: 'academy', mentorship: 'mentor' };

export async function render(el, ctx) {
  if (!ctx.can('risk.view')) {
    mount(el, html`${pageHead({ title: t('risk.title') })}<div class="card">${empty('Restricted', 'Knowledge-risk details include planned retirement dates and are visible to experts, trainers and administrators.')}</div>`);
    return;
  }
  mount(el, loading(4));
  const r = await api.get('/api/risk');
  let band = 'all'; const open = new Set(ctx.query.skill ? [ctx.query.skill] : r.skills.slice(0, 1).map((s) => s.code));
  const draw = () => {
    const rows = r.skills.filter((s) => band === 'all' || s.band === band);
    mount(el, html`
      ${pageHead({ eyebrow: 'Module G', icon: 'risk', title: t('risk.title'), sub: t('risk.sub') })}
      <div class="grid g-side" style="margin-bottom:16px">
        <div class="card"><div class="card-h"><h2>How the score works<span class="sub">Rules ${r.rules.version} · as of ${fmtDate(r.as_of)}</span></h2></div>
          <div class="formula">base  = expert concentration (0–30) + retirement exposure (0–20)
      + documentation gap (0–25)   + successor gap (0–20)
score = min(100, base × (0.6 + 0.1 × criticality))      bands: ≥70 critical · ≥50 high · ≥30 moderate</div>
          <p class="small muted" style="margin-top:8px">Retirement exposure uses only dates entered by an administrator. Nothing is inferred from age or other personal data.</p></div>
        <div class="card">${donut([{ label: 'Critical', value: r.bands.critical, color: 'var(--danger)' }, { label: 'High', value: r.bands.high, color: 'var(--warn)' },
          { label: 'Moderate', value: r.bands.moderate, color: 'var(--steel)' }, { label: 'Low', value: r.bands.low, color: 'var(--ok)' }], { center: r.skills.length, sub: 'skills' })}</div>
      </div>
      <div class="tabs">${['all', 'critical', 'high', 'moderate', 'low'].map((b) => html`<button class="tab ${band === b ? 'on' : ''}" data-action="band" data-b="${b}">${b === 'all' ? 'All skills' : b[0].toUpperCase() + b.slice(1)}${b !== 'all' ? html` <span class="badge b-neutral">${r.bands[b]}</span>` : ''}</button>`)}</div>
      <div class="stack">${rows.map((s) => {
        const isOpen = open.has(s.code);
        return html`<div class="risk-row ${isOpen ? 'open' : ''}" id="risk-${s.code}">
          <div class="risk-score ${s.band}"><b>${s.score}</b>${bandBadge(s.band)}</div>
          <div>
            <div class="row between"><div><h3>${nm(s.name, s.name_ja)}</h3><small class="muted mono">${s.code} · ${s.category} · criticality ${s.criticality}/5 · multiplier ×${s.multiplier}</small></div>
              <button class="btn btn-sm btn-ghost" data-action="toggle" data-c="${s.code}">${isOpen ? 'Hide' : 'Why?'}</button></div>
            <div class="holders">${s.holders.length ? s.holders.map((h) => html`<span class="holder">${avatar(h.name, 'xs')}${nm(h.name, h.name_ja)} <small class="muted">P${h.proficiency}${h.retirement_date ? ` · retires ${h.retirement_date}` : ''}</small></span>`)
              : html`<span class="badge b-danger">no recorded expert</span>`}</div>
            ${isOpen ? html`<div class="factors">${s.factors.map((f) => html`<div class="factor"><b>${f.label}</b>${meter(f.points, f.max, f.points >= f.max * 0.7 ? 'danger' : f.points ? '' : 'ok')}<span class="mono">${f.points}/${f.max}</span>
              <span class="f-detail">${f.detail}</span></div>`)}</div>
              <p class="small muted" style="margin-top:6px">${s.base_points} base points × ${s.multiplier} = <b>${s.score}</b></p>` : ''}
          </div>
          <div class="reco-col"><div class="small muted" style="margin-bottom:6px">Recommended actions</div>
            ${s.recommendations.length ? html`<div class="reco">${s.recommendations.map((a) => html`<a href="${a.route}">${ic(RICON[a.type] || 'arrow', 15)}<span>${a.label}</span></a>`)}</div>`
              : html`<p class="small" style="color:var(--ok)">${ic('check', 14)} Well covered — keep validating successors.</p>`}</div>
        </div>`;
      })}</div>`);
    if (ctx.query.skill) document.getElementById(`risk-${ctx.query.skill}`)?.scrollIntoView({ block: 'center' });
  };
  draw();
  return actions(el, {
    band: (b) => { band = b.dataset.b; draw(); },
    toggle: (b) => { open.has(b.dataset.c) ? open.delete(b.dataset.c) : open.add(b.dataset.c); draw(); },
  });
}
