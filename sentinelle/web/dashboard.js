import {$,esc,number,api,videoNote,factHTML,signalsHTML,toast} from './shared.js';
let rows=[],selected=new URLSearchParams(location.search).get('app'),busy=false;
const decisions={clear:'Validé après vérification',verify:'Vérification demandée',escalate:'Transmis pour revue',reject:'Refus après revue humaine'};
function choose(id){selected=id;history.replaceState(null,'',`/recruiter?app=${encodeURIComponent(id)}`);$('note').value='';render();}
function render(){
 const query=$('search').value.toLocaleLowerCase();const visible=rows.filter(r=>(r.name+' '+r.id).toLocaleLowerCase().includes(query));
 $('count').textContent=rows.length;
 $('list').innerHTML=visible.length?visible.map(r=>`<button class="candidate ${r.id===selected?'active':''}" data-id="${esc(r.id)}" aria-pressed="${r.id===selected}"><span class="candidate-row"><strong>${esc(r.name)}</strong><span class="candidate-score">${r.result.score}</span></span><small>${esc(r.city||'Lieu non renseigné')} · ${esc(r.id)}</small><span class="pill ${r.connection?.online?'live':r.demo?'demo':''}">${r.connection?.online?'Entretien en cours':r.demo?'Exemple synthétique':r.stage==='onboarding'?'Onboarding':'Candidature'}</span></button>`).join(''):'<p class="muted">Aucun dossier trouvé.</p>';
 const row=rows.find(r=>r.id===selected);$('empty').hidden=!!row;$('detail').hidden=!row;if(!row)return;
 $('name').textContent=row.name;$('identity').textContent=row.id;$('demo-label').hidden=!row.demo;
 $('location').textContent=[row.city,row.country,row.email].filter(Boolean).join(' · ');
 $('interview-link').href=`/entretien?app=${encodeURIComponent(row.id)}`;$('onboarding-link').href=`/onboarding?app=${encodeURIComponent(row.id)}`;
 $('dossier-score').textContent=`${row.result.score} / 100`;$('dossier-note').textContent=`${row.result.signals.length} signal(s) · coordonnées, parcours et liens entre dossiers`;
 const connection=row.connection,fresh=connection?.online;
 $('connection-score').textContent=fresh?`${connection.result.score} / 100`:'—';
 $('connection-note').textContent=fresh?'Mesures reçues · indices à contextualiser':connection?'Mesures anciennes · entretien interrompu':'En attente de l’entretien';
 $('video-score').textContent=row.video.score===null?'—':`${number(row.video.score*100)} / 100`;$('video-note').textContent=videoNote(row.video);
 $('signals').innerHTML=signalsHTML(row.result.signals,'Dossier')||'<p class="muted">Aucun signal sur les informations du dossier renseignées.</p>';
 $('connection-signals').innerHTML=fresh?signalsHTML(connection.result.signals,'Connexion'):'';
 const questions=[...new Set([...(row.result.explanation?.questions||[]),...(fresh?connection.result.explanation?.questions||[]:[]),...(row.video.score>=.5?['Pouvez-vous refaire une prise avec la caméra native, sans filtre, pour vérifier cet indice vidéo ?']:[])])];
 $('questions').innerHTML=questions.length?questions.map(q=>`<li>${esc(q)}</li>`).join(''):'<li>Aucune question spécifique proposée pour le moment.</li>';
 $('facts').innerHTML=factHTML(connection);
 $('linked').innerHTML=row.result.linked?.length?`<p class="muted">Liens avec le corpus synthétique : ${row.result.linked.map(x=>esc(x.name)+' ('+esc(x.id)+')').join(', ')}. Un lien ne prouve pas une fraude.</p>`:'<p class="muted">Aucun dossier lié.</p>';
 $('previous-decision').textContent=row.decision?`${decisions[row.decision.decision]||row.decision.decision} · ${row.decision.analyst} · ${row.decision.at}`:'Aucune décision enregistrée.';
}
async function refresh(){if(busy)return;busy=true;try{rows=await api('/api/sentinelle/overview');if(!rows.some(r=>r.id===selected))selected=rows[0]?.id;render();$('error').hidden=true;}catch(e){$('error').textContent=e.message;$('error').hidden=false;$('connection-score').textContent=$('video-score').textContent='—';$('connection-note').textContent=$('video-note').textContent='Connexion au serveur interrompue';}finally{busy=false;}}
async function demo(kind){const buttons=[$('demo-honest'),$('demo-fraud'),$('empty-demo')];buttons.forEach(b=>b.disabled=true);try{const r=await api('/api/sentinelle/demo',{kind});selected=r.id;await refresh();choose(r.id);toast('Exemple synthétique prêt. Vous pouvez ouvrir son entretien.');}catch(e){$('error').textContent=e.message;$('error').hidden=false;}finally{buttons.forEach(b=>b.disabled=false);}}
$('list').onclick=e=>{const b=e.target.closest('[data-id]');if(b)choose(b.dataset.id);};$('search').oninput=render;
$('demo-honest').onclick=()=>demo('honest');$('empty-demo').onclick=()=>demo('honest');$('demo-fraud').onclick=()=>demo('fraud');
$('decision-form').onsubmit=async e=>{e.preventDefault();$('save-decision').disabled=true;try{await api('/api/decision',{app_id:selected,decision:$('decision').value,analyst:$('analyst').value,note:$('note').value});toast('Décision enregistrée dans le journal local.');await refresh();}catch(e){$('error').textContent=e.message;$('error').hidden=false;}finally{$('save-decision').disabled=false;}};
await refresh();setInterval(refresh,2500);
