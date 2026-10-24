'use strict';
function associationReviewActions(dossier){
 const rows=new Map();
 for(const link of dossier.candidate_source_links||[])rows.set(link.relationship_id,{id:link.relationship_id,label:'Candidate source context',detail:link.evidence_summary||'Unreviewed relationship',reassessment:false});
 for(const review of dossier.association_review_states||[])rows.set(review.relationship_id,{id:review.relationship_id,label:'Recorded source context',detail:review.requires_reassessment?'Source evidence changed; reassessment required.':'Reviewed context; identity remains unverified.',reassessment:review.requires_reassessment});
 if(!rows.size)return '<p>No candidate associations or recorded context reviews on this dossier.</p>';
 return table(['Context','Review state','Action'],[...rows.values()].map(row=>[
  esc(row.label),esc(row.detail),'<button data-association-review="'+esc(row.id)+'" '+(data.read_only?'disabled':'')+'>'+(row.reassessment?'Reassess association':'Review association')+'</button>'
 ]));
}
function bindAssociationReviews(identity){
 $('action-content').querySelectorAll('[data-association-review]').forEach(button=>{
  button.onclick=()=>openAssociationReview(button.dataset.associationReview,identity);
 });
}
async function openAssociationReview(relationshipId,returnIdentity){
 if(data.read_only)return;
 const ticket=modal('Review source association','<p role="status">Loading the current candidate and retained source evidence…</p>');
 try{
  const preview=await api('/api/investigation-review?relationship='+encodeURIComponent(relationshipId));
  if(ticket!==modalTicket||!$('action-dialog').open)return;
  const choices=preview.target_choices||[],summaries=preview.investigations||{};
  const summaryRows=choices.map(identity=>{
   const dossier=summaries[identity]||{},info=dossier.investigation||{};
   const sources=(dossier.source_membership||[]).map(s=>esc(s.source_family||'Unknown family')+' · '+esc(s.source_record_id||s.source_id)).join('<br>');
   return [esc(info.project_name||identity),sources||'No retained source context',esc(info.project_cluster_id||identity)];
  });
  const targetOptions=choices.map(identity=>{
   const info=summaries[identity]?.investigation||{},canonical=info.project_cluster_id===identity;
   return '<option value="'+esc(identity)+'" '+(canonical?'':'disabled')+'>'+esc(info.project_name||identity)+' · '+esc(identity)+(canonical?'':' · already grouped elsewhere')+'</option>';
  }).join('');
  $('action-content').innerHTML='<div class="association-review-preview"><p>This records reviewed source context. It does not verify project identity, current construction, or permission for outreach or bids. Original source records and evidence remain preserved.</p>'+
   table(['Investigation','Retained source records','Current shared investigation'],summaryRows)+
   choices.map(identity=>'<details><summary>Retained claims and evidence · '+esc(summaries[identity]?.investigation?.project_name||identity)+'</summary><pre data-review-evidence>'+esc(JSON.stringify({sources:summaries[identity]?.source_observations,evidence:summaries[identity]?.evidence,evidence_truncated:summaries[identity]?.evidence_truncated,sources_truncated:summaries[identity]?.sources_truncated,assessment:summaries[identity]?.evidence_assessment},null,2))+'</pre></details>').join('')+
   '<p>'+esc(preview.relationship.evidence_summary||'')+'</p><details><summary>Supporting and contradictory evidence</summary><pre>'+esc(JSON.stringify(preview.relationship,null,2))+'</pre></details>'+
   '<form id="association-review-form" class="form-grid">'+
   '<label>Decision<select name="decision" required><option value="">Choose a decision</option><option value="associate">Associate source context</option><option value="reject">Reject this association</option></select></label>'+
   '<label>Keep shared investigation<select name="target" required><option value="">Choose the shared investigation</option>'+targetOptions+'</select></label>'+
   field('reviewer','Reviewer (local audit name)',data.settings?.profile?.name||'','text',true)+field('reason','Review reason','','textarea',true)+
   '<label class="check"><input name="confirmed" type="checkbox" required>I reviewed the displayed evidence and confirm this decision.</label>'+
   '<button type="submit">Record association review</button></form><p id="association-review-result" role="status"></p>'+
   '<button id="association-review-reload">Reload current review preview</button> <button id="association-review-cancel">Return to investigation</button></div>';
  const form=$('association-review-form'),decision=form.elements.namedItem('decision'),target=form.elements.namedItem('target');
  form.elements.namedItem('reason').maxLength=4000;form.elements.namedItem('reviewer').maxLength=255;
  decision.onchange=()=>{target.disabled=decision.value==='reject';target.required=decision.value==='associate';if(target.disabled)target.value='';};
  $('association-review-reload').onclick=()=>openAssociationReview(relationshipId,returnIdentity);
  $('association-review-cancel').onclick=()=>openInvestigationDossier(returnIdentity);
  form.onsubmit=async event=>{
   event.preventDefault();
   const button=form.querySelector('button[type="submit"]');button.disabled=true;
   try{
    const result=await api('/api/investigation-review',{
     relationship_id:relationshipId,expected_identity:preview.expected_identity,
     decision:decision.value,target_id:decision.value==='associate'?target.value:null,
     reason:form.elements.namedItem('reason').value.trim(),
     operator_id:form.elements.namedItem('reviewer').value.trim(),
     caller_confirmation:form.elements.namedItem('confirmed').checked
    });
    if(ticket!==modalTicket||!$('action-dialog').open)return;
    modal('Association review recorded','<p>Your '+esc(result.decision)+' decision is recorded. Identity remains unverified and no commercial authority was granted.</p><button id="association-review-open">Open shared investigation</button> <button id="association-review-receipt">Download review receipt</button>');
    $('association-review-open').onclick=()=>openInvestigationDossier(result.target_id||returnIdentity);
    $('association-review-receipt').onclick=()=>download('investigation-association-review.json',result);
   }catch(error){
    if(ticket!==modalTicket||!$('action-dialog').open)return;
    $('association-review-result').textContent=error.message+' Reload the current preview before another attempt; a disconnected response may follow a committed review.';
   }
  };
 }catch(error){
  if(ticket!==modalTicket||!$('action-dialog').open)return;
  $('action-content').textContent='Review preview unavailable: '+error.message;
 }
}
