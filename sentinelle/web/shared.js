export const $=id=>document.getElementById(id);
export const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number=value=>Number.isFinite(value)?value.toLocaleString('fr-FR',{maximumFractionDigits:1}):'—';
export async function api(path,payload){
 const r=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Visio-Request':'1'},body:JSON.stringify(payload)});
 const data=await r.json();if(!r.ok)throw new Error(data.error||'Le serveur est indisponible.');return data;
}
export function videoNote(v){
 if(v?.status==='ready')return `${v.transformed_demo?'Flux transformé · démonstration':'Flux original'} · médiane de ${v.samples} images récentes`;
 if(v?.status==='collecting')return `Mesure en cours · ${v.samples}/3 images minimum`;
 return v?.status==='stopped'?'Entretien arrêté · aucune mesure en direct':'En attente d’images exploitables et récentes';
}
export function facts(session){
 const s=session?.snapshot;if(!s)return [['Entretien','Aucune mesure reçue']];
 const r=s.rtt_ms?.length?[...s.rtt_ms].sort((a,b)=>a-b):[];
 return [['Caméra',s.devices?.video?.join(', ')||'Non accessible'],['Micro · nom uniquement',s.devices?.audio?.join(', ')||'Non accessible · aucune capture audio'],['Rendu graphique',s.gpu_renderer||'Non accessible'],['Fuseau de l’ordinateur',s.browser_timezone||'Non accessible'],['IP publique',s.ip?.address||'Vérification réseau non disponible'],['Pays / réseau',s.ip?.country?`${s.ip.country} · ${s.ip.org||'opérateur inconnu'}`:'Non disponible'],['Temps de réponse réseau',r.length?`${number(r[Math.floor(r.length/2)])} ms · ne mesure pas la distance`:'Non mesuré'],['Vidéo',s.video_settings?.width?`${s.video_settings.width} × ${s.video_settings.height} · ${s.video_settings.frameRate||'?'} images/s`:'En attente de la caméra']];
}
export function factHTML(session){return facts(session).map(([a,b])=>`<div class="fact"><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('');}
export function signalsHTML(signals,label){return (signals||[]).map(s=>`<div class="signal"><p>${esc(s.evidence)}</p><small>${esc(label)} · ${esc(s.code)} · ${esc(s.weight)} points</small></div>`).join('');}
export function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,5000);}
