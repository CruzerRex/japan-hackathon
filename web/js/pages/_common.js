import { html, ic } from '../ui.js';

export function pageHead({ eyebrow = '', icon = '', title, sub = '', actions = '', crumb = '' }) {
  return html`<header class="ph">
    <div class="ph-text">
      ${crumb ? html`<a class="crumb" href="${crumb.href}">${ic('back', 14)} ${crumb.label}</a>` : ''}
      ${eyebrow ? html`<div class="eyebrow">${icon ? ic(icon, 14) : ''}${eyebrow}</div>` : ''}
      <h1>${title}</h1>${sub ? html`<p>${sub}</p>` : ''}
    </div>
    ${actions ? html`<div class="ph-actions">${actions}</div>` : ''}
  </header>`;
}

export const SOURCE_NAMES = {
  demonstration: 'Demonstrated', transcript: 'Said', expert_note: 'Written note', expert_edit: 'Expert-authored', inference: 'AI-inferred',
};
