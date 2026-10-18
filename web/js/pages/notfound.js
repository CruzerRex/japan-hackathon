import { html, mount } from '../ui.js';

export function render(el) {
  mount(el, html`<div class="card"><h2>Page not found</h2><p class="muted">That address does not exist.</p>
    <a class="btn btn-ghost" href="#/overview">Back to overview</a></div>`);
}
