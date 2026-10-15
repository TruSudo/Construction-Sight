'use strict';
let verificationKeys = [], verificationIndex = 0;
function openVerificationQueue() {
  verificationKeys = baseRows().filter(r => !r.hidden && !r.do_not_contact && !r.site_verified && r.project_type !== 'infrastructure' && r.fit_band !== 'low').sort((a,b) => (b.fit_band === 'high') - (a.fit_band === 'high') || (b.sourced_contacts?.[0]?.reliability_score || 0) - (a.sourced_contacts?.[0]?.reliability_score || 0) || b.security_fit - a.security_fit).map(r => r.source_key);
  verificationIndex = 0;
  renderVerification();
}
function renderVerification() {
  const key = verificationKeys[verificationIndex], lead = data.rows.find(r => r.source_key === key);
  if (!lead) { modal('Site verification queue', '<p>No remaining eligible sites in this scope.</p>'); return; }
  const previous = lead.site_verification || {};
  modal(`Verify site · ${verificationIndex + 1} / ${verificationKeys.length}`, `
    <h3>${esc(lead.SITE_NAME)}</h3>
    <p>${esc(lead.SITE_ADDRESS)} · ${esc(lead.SITE_CITY)}, ${esc(lead.SITE_COUNTY)} County</p>
    <p>Reported coordinates: ${esc(lead.SITE_LATITUDE)}, ${esc(lead.SITE_LONGITUDE)} · Fit ${esc(lead.security_fit)}</p>
    <p>Check an independent permit, parcel record or site visit evidence against this physical site. Source statements and contact authority remain unverified separately. Saving this review never sends outreach.</p>
    ${previous.stale ? '<p role="alert">The captured site changed after its previous review. Check it again.</p>' : ''}
    <form id="site-review-form" class="form-grid">
      ${field('source','Independent evidence URL',previous.source || '','url',true)}
      ${field('note','What did you check? Address, identity and any limits',previous.note || '','textarea',true)}
      <label class="check"><input id="site-review-checked" type="checkbox" required> I independently checked this physical site</label>
      <button type="submit">Save verified site and next</button>
    </form>
    <p id="site-review-result" role="status"></p>
    <button id="verify-previous" ${verificationIndex ? '' : 'disabled'}>Previous (K)</button>
    <button id="verify-next">Skip / next (J)</button>
    <p>J/K move through sites when you are outside a form field. Verification requires the checked form and Save.</p>`);
  $('verify-previous').onclick = () => { verificationIndex--; renderVerification(); };
  $('verify-next').onclick = () => { verificationIndex++; renderVerification(); };
  bindForm('site-review-form', async f => {
    if (!$('site-review-checked').checked) throw Error('Check the physical site before saving');
    await api(keyPath('site-review', key), {verified:true, source:f.source, note:f.note});
    await reload();
    verificationIndex++;
    renderVerification();
  });
}
document.addEventListener('keydown', e => {
  if (!$('action-dialog').open || !$('site-review-form') || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.ctrlKey || e.metaKey || e.altKey) return;
  const button = e.key.toLowerCase() === 'j' ? $('verify-next') : e.key.toLowerCase() === 'k' ? $('verify-previous') : null;
  if (button && !button.disabled) { e.preventDefault(); button.click(); }
});
