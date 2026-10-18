import { api } from '../api.js';
import { html, mount, $, actions, avatar, toastError, ic } from '../ui.js';
import { nm } from '../i18n.js';

export async function render(el, { go, reloadMe }) {
  let demo = { enabled: false, accounts: [] };
  try { demo = await api.get('/api/auth/demo-accounts'); } catch { /* server may be down */ }
  const main = demo.accounts.filter((a) => !a.org_name.includes('isolation'));
  const other = demo.accounts.filter((a) => a.org_name.includes('isolation'));
  mount(el, html`<div class="login">
    <section class="login-hero">
      <a class="brand"><span class="brand-mark">絆</span><span class="brand-text"><b>KIZUNA</b> FORGE</span></a>
      <h1>Preserve mastery. <em>Transfer skill.</em> Keep industry moving.</h1>
      <p class="lede">Japan's veteran engineers carry decades of tacit judgement that rarely reaches a manual. Kizuna Forge turns
        what an expert demonstrates and says into evidence-linked procedures, trains successors on them, and measures the result.</p>
      <div class="flow">${['Expert recording', 'Knowledge extraction', 'Evidence-backed graph', 'Interactive training',
        'Competency assessment', 'Expert validation', 'Organisational memory'].map((s, i) => html`${i ? html`<i>→</i>` : ''}<span>${s}</span>`)}</div>
      <div class="pillars">
        <div class="pillar"><b>Evidence-linked</b><small>Every instruction traces to what the expert showed, said or wrote — or is flagged as inference.</small></div>
        <div class="pillar"><b>Tacit knowledge</b><small>Sensory cues, decision points and mistakes become explicit, reviewable content.</small></div>
        <div class="pillar"><b>Closed loop</b><small>Capture → approval → training → assessment → sign-off → risk, in one system.</small></div>
        <div class="pillar"><b>Explainable risk</b><small>See why a skill is at risk of loss and exactly what reduces it.</small></div>
      </div>
    </section>
    <section class="login-panel">
      <div><h2>Sign in</h2><p class="muted">Use your company account.</p></div>
      <form id="login-form" autocomplete="on">
        <label class="field"><span>Email</span><input type="email" name="email" required autocomplete="username"></label>
        <label class="field"><span>Password</span><input type="password" name="password" required autocomplete="current-password"></label>
        <button class="btn btn-primary" type="submit">Sign in</button>
      </form>
      ${demo.enabled && main.length ? html`
        <div class="sep"></div>
        <div><h3>Explore the simulated demo</h3><p class="muted small">${main[0].org_name} is a fictional precision-machining SME.
          Pick a persona — each role sees different data and permissions.</p></div>
        <div class="persona-grid">${main.map((a) => html`<button class="persona" data-action="demo" data-id="${a.id}">
          ${avatar(a.name, 'sm')}<span><em class="role-tag">${a.role}</em><b>${nm(a.name, a.name_ja)}</b><small>${a.title}</small></span></button>`)}</div>
        ${other.length ? html`<p class="small muted">Tenant-isolation check: ${other.map((a) => html`<a href="#" data-action="demo" data-id="${a.id}">${a.name} (${a.org_name})</a>`)}</p>` : ''}` : ''}
    </section></div>`);
  const signedIn = async () => { await reloadMe(); go('#/overview'); };
  actions(el, {
    demo: async (b) => { await api.post('/api/auth/demo-login', { user_id: b.dataset.id }); await signedIn(); },
  });
  $('#login-form', el).addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try { await api.post('/api/auth/login', { email: f.get('email'), password: f.get('password') }); await signedIn(); }
    catch (err) { toastError(err); }
  });
}
