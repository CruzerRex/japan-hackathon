// Small dependency-free SVG charts. Every chart renders from data passed in;
// nothing here contains hard-coded values.
import { html, raw, esc } from './ui.js';

export function stackedBars(rows, keys, { labelKey = 'label', height = 22, gap = 12, colors = {}, names = {} } = {}) {
  if (!rows.length) return html`<p class="muted small">No data yet.</p>`;
  const max = Math.max(1, ...rows.map((r) => keys.reduce((a, k) => a + (r[k] || 0), 0)));
  const W = 100;
  return html`<div class="hbars">
    ${rows.map((r) => {
      let x = 0;
      const total = keys.reduce((a, k) => a + (r[k] || 0), 0);
      return html`<div class="hbar-row">
        <div class="hbar-label" title="${r[labelKey]}">${r[labelKey]}</div>
        <div class="hbar-track" style="height:${height}px">
          ${keys.map((k) => {
            const w = ((r[k] || 0) / max) * W;
            const seg = w > 0 ? html`<span class="hbar-seg" style="left:${x}%;width:${w}%;background:${colors[k] || 'var(--accent)'}" title="${names[k] || k}: ${r[k]}"></span>` : '';
            x += w; return seg;
          })}
        </div>
        <div class="hbar-val mono">${total}</div>
      </div>`;
    })}
    <div class="legend">${keys.map((k) => html`<span><i style="background:${colors[k]}"></i>${names[k] || k}</span>`)}</div>
  </div>`;
}

export function donut(segments, { size = 132, stroke = 16, center = '', sub = '' } = {}) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = (size - stroke) / 2; const c = 2 * Math.PI * r;
  let off = 0;
  const arcs = total ? segments.filter((s) => s.value > 0).map((s) => {
    const len = (s.value / total) * c;
    const el = `<circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="${s.color}" stroke-width="${stroke}" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-off}" transform="rotate(-90 ${size / 2} ${size / 2})"><title>${esc(s.label)}: ${s.value}</title></circle>`;
    off += len; return el;
  }).join('') : `<circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="var(--line)" stroke-width="${stroke}"/>`;
  return html`<div class="donut">
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${segments.map((s) => `${s.label} ${s.value}`).join(', ')}">${raw(arcs)}
      <text x="50%" y="48%" text-anchor="middle" class="donut-c">${center}</text>
      <text x="50%" y="63%" text-anchor="middle" class="donut-s">${sub}</text></svg>
    <ul class="donut-legend">${segments.map((s) => html`<li><i style="background:${s.color}"></i>${s.label}<b class="mono">${s.value}</b></li>`)}</ul>
  </div>`;
}

export function scoreGauge(score, { threshold = 80, size = 150, label = 'score' } = {}) {
  const r = size / 2 - 12; const c = Math.PI * r; const v = Math.max(0, Math.min(100, score || 0));
  const col = v >= threshold ? 'var(--ok)' : v >= 50 ? 'var(--warn)' : 'var(--danger)';
  const tx = size / 2 + r * Math.cos(Math.PI - (threshold / 100) * Math.PI);
  const ty = size / 2 + 4 - r * Math.sin((threshold / 100) * Math.PI);
  return html`<svg class="gauge" width="${size}" height="${size / 2 + 26}" viewBox="0 0 ${size} ${size / 2 + 26}" role="img" aria-label="${label} ${v}">
    <path d="M12 ${size / 2 + 4} A ${r} ${r} 0 0 1 ${size - 12} ${size / 2 + 4}" fill="none" stroke="var(--line)" stroke-width="12" stroke-linecap="round"/>
    <path d="M12 ${size / 2 + 4} A ${r} ${r} 0 0 1 ${size - 12} ${size / 2 + 4}" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${(v / 100) * c} ${c}"/>
    <circle cx="${tx}" cy="${ty}" r="3.5" fill="var(--text)"><title>Pass threshold ${threshold}</title></circle>
    <text x="50%" y="${size / 2}" text-anchor="middle" class="gauge-v">${Math.round(v * 10) / 10}</text>
    <text x="50%" y="${size / 2 + 20}" text-anchor="middle" class="gauge-l">${label}</text></svg>`;
}

export function riskBars(skills, onclickAction = 'open-risk') {
  if (!skills.length) return html`<p class="muted small">No skills at risk.</p>`;
  return html`<div class="riskbars">${skills.map((s) => html`
    <button class="riskbar" data-action="${onclickAction}" data-code="${s.code}">
      <span class="riskbar-name">${s.name}<small class="mono">${s.code}</small></span>
      <span class="riskbar-track"><span class="riskbar-fill band-bg-${s.band}" style="width:${s.score}%"></span></span>
      <span class="riskbar-score mono">${s.score}</span>
    </button>`)}</div>`;
}

export function sparkline(values, { w = 120, h = 32 } = {}) {
  if (values.length < 2) return '';
  const max = 100; const step = w / (values.length - 1);
  const pts = values.map((v, i) => `${i * step},${h - (v / max) * (h - 4) - 2}`).join(' ');
  return html`<svg width="${w}" height="${h}" class="spark" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    ${values.map((v, i) => html`<circle cx="${i * step}" cy="${h - (v / max) * (h - 4) - 2}" r="2.5" fill="var(--accent)"/>`)}</svg>`;
}
