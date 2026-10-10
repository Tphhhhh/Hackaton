import {$,number,api,videoNote,factHTML,signalsHTML,toast} from './shared.js';
const appId=new URLSearchParams(location.search).get('app');
let candidate,token=null,epoch=0,stream=null,collecting=false,joined=false,network=false,lastNetwork=0,net={ip:{},rtt_ms:[]};
let frameWindow,baseFetch,resizeObserver,rotation=Promise.resolve();
const error=message=>{$('error').textContent=message;$('error').hidden=!message;};
async function rotate(){
 const myEpoch=++epoch;const old=token;token=null;
 if(old)api('/api/sentinelle/close',{token:old}).catch(()=>{});
 if(!joined)return;
 const source=$('source').value;
 try{const r=await (rotation=rotation.catch(()=>{}).then(()=>api('/api/sentinelle/interview',{app_id:appId,source})));
  if(myEpoch!==epoch){api('/api/sentinelle/close',{token:r.token}).catch(()=>{});return;}token=r.token;
 }catch(e){error(e.message);}
}
function endBinding(){epoch++;const old=token;token=null;if(old)api('/api/sentinelle/close',{token:old}).catch(()=>{});}
function installBridge(){
 if(!joined||!$('visio').contentWindow.document.getElementById('filter-portrait'))return;
 frameWindow=$('visio').contentWindow;
 baseFetch=frameWindow.fetch.bind(frameWindow);
 frameWindow.fetch=(input,init)=>{
  const path=new URL(typeof input==='string'?input:input.url,frameWindow.location.href).pathname;
  if(path==='/api/live/score'&&token){const headers=new Headers(init?.headers);headers.set('X-Sentinelle-Interview',token);return baseFetch(input,{...init,headers});}
  return baseFetch(input,init);
 };
 const media=frameWindow.navigator.mediaDevices,original=media.getUserMedia.bind(media);
 media.getUserMedia=async options=>{const acquired=await original(options);stream=acquired;return acquired;};
 const doc=frameWindow.document;
 // Listen to lifecycle events without changing Visio's code, controls or inference.
 doc.addEventListener('click',e=>{
  const id=e.target.closest('button')?.id;
  if(id==='stop-camera'){endBinding();$('tracking-status').textContent='Caméra arrêtée';}
  if(['start-camera','toggle-filter','connect-external','disconnect-external'].includes(id))rotate();
 },true);
 doc.getElementById('filter-portrait').addEventListener('change',rotate,true);
 doc.querySelectorAll('[data-mode]').forEach(el=>el.addEventListener('click',()=>{if(el.dataset.mode!=='live')endBinding();},true));
 resizeObserver?.disconnect();resizeObserver=new ResizeObserver(()=>{$('visio').style.height=Math.max(1000,doc.documentElement.scrollHeight)+'px';});resizeObserver.observe(doc.body);
}
function gpu(){try{const gl=document.createElement('canvas').getContext('webgl');const ext=gl.getExtension('WEBGL_debug_renderer_info');const name=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);gl.getExtension('WEBGL_lose_context')?.loseContext();return name;}catch{return '';}}
const renderer=gpu();
async function networkInfo(){
 const result={ip:{},rtt_ms:[]};
 const ipTask=(async()=>{try{const r=await fetch('https://api.ipify.org?format=json',{signal:AbortSignal.timeout(2500)});if(!r.ok)return;const {ip}=await r.json();if(typeof ip!=='string'||!/^[a-fA-F0-9:.]+$/.test(ip))return;result.ip.address=ip;
  const geo=await fetch(`https://ipapi.co/${encodeURIComponent(ip)}/json/`,{signal:AbortSignal.timeout(2500)});if(!geo.ok)return;const g=await geo.json();if(typeof g.country_code==='string')result.ip.country=g.country_code==='GB'?'UK':g.country_code;
  result.ip.org=String(g.org||'');result.ip.type=/amazon|google|microsoft|azure|digitalocean|ovh|hetzner|hosting|cloud|vpn/i.test(result.ip.org)?'datacenter':'unknown';
 }catch{}})();
 const rttTask=(async()=>{for(let i=0;i<3;i++){const start=performance.now();try{await fetch(`https://www.cloudflare.com/cdn-cgi/trace?sentinelle=${Date.now()}-${i}`,{mode:'no-cors',cache:'no-store',signal:AbortSignal.timeout(2000)});result.rtt_ms.push(Math.round(performance.now()-start));}catch{}}})();
 await Promise.all([ipTask,rttTask]);return result;
}
async function snapshot(){
 if(!joined||!token||collecting)return;
 const track=stream?.getVideoTracks()[0];if(!track||track.readyState!=='live')return;
 collecting=true;const binding=token;
 try{
  if(network&&Date.now()-lastNetwork>30000){net=await networkInfo();lastNetwork=Date.now();}
  if(binding!==token||!joined)return;
  const devices=await frameWindow.navigator.mediaDevices.enumerateDevices();const settings=track.getSettings();
  const value={devices:{video:track.label?[track.label]:[],audio:devices.filter(d=>d.kind==='audioinput'&&d.label).map(d=>d.label)},
    gpu_renderer:renderer,browser_timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,browser_utc_offset:-new Date().getTimezoneOffset()/60,
    video_settings:Object.fromEntries(['width','height','frameRate'].filter(k=>Number.isFinite(settings[k])).map(k=>[k,Math.round(settings[k])])),
    ip:network?net.ip:{},rtt_ms:network?net.rtt_ms:[]};
  if(binding!==token)return;
  await api('/api/sentinelle/snapshot',{token:binding,snapshot:value});
  if(binding===token)$('tracking-status').textContent='Entretien relié · mesures techniques actives';
 }catch(e){if(binding===token)error(e.message);}finally{collecting=false;}
}
async function refresh(){
 if(!joined)return;
 try{const row=(await api('/api/sentinelle/overview')).find(r=>r.id===appId);if(!row)return;
  $('dossier-score').textContent=`${row.result.score} / 100`;
  $('connection-score').textContent=row.connection?.online?`${row.connection.result.score} / 100`:'—';
  $('connection-note').textContent=row.connection?.online?'Indices techniques · causes légitimes possibles':'Mesure absente ou trop ancienne';
  $('video-score').textContent=row.video.score===null?'—':`${number(row.video.score*100)} / 100`;
  $('video-note').textContent=videoNote(row.video);
  $('export').disabled=!token||row.video.status!=='ready'||row.video.source!=='original';
  $('facts').innerHTML=factHTML(row.connection);$('signals').innerHTML=row.connection?.online?signalsHTML(row.connection.result.signals,'Connexion'):'';
 }catch(e){error(e.message);$('connection-score').textContent=$('video-score').textContent='—';$('video-note').textContent='Connexion au serveur interrompue';$('export').disabled=true;}
}
$('agree').onchange=()=>{$('join').disabled=!$('agree').checked||!candidate;};
$('join').onclick=async()=>{
 $('join').disabled=true;network=$('network').checked;joined=true;await rotate();if(!token){joined=false;$('join').disabled=false;return;}
 $('consent').hidden=true;$('room').hidden=false;$('visio').onload=installBridge;$('visio').src='/?sentinelle=1';refresh();
};
$('source').onchange=async()=>{await rotate();await refresh();if($('source').value==='filtered')toast('Flux transformé associé pour la démo. L’export candidat est désactivé.');};
$('export').onclick=async()=>{try{const result=await api('/api/sentinelle/export',{token});toast(`Bilan conservé : ${number(result.score*100)} / 100, ${result.samples} images. Ce bilan est daté, pas un score en direct.`);}catch(e){error(e.message);}};
$('leave').onclick=()=>{joined=false;endBinding();stream?.getTracks().forEach(t=>t.stop());resizeObserver?.disconnect();$('visio').src='about:blank';location.href=`/recruiter?app=${encodeURIComponent(appId)}`;};
window.addEventListener('pagehide',()=>{joined=false;stream?.getTracks().forEach(t=>t.stop());if(token)fetch('/api/sentinelle/close',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Visio-Request':'1'},body:JSON.stringify({token})}).catch(()=>{});});
try{
 if(!appId)throw new Error('Ouvrez un entretien depuis un dossier de la console RH.');candidate=await api('/api/applications/'+encodeURIComponent(appId));
 $('welcome').textContent=`Bonjour ${candidate.first_name||''}, préparons votre entretien.`;$('candidate-name').textContent=candidate.name;$('candidate-id').textContent=candidate.id;
 $('back').href=$('console-link').href=`/recruiter?app=${encodeURIComponent(appId)}`;
}catch(e){error(e.message);$('consent').hidden=true;}
setInterval(snapshot,5000);setInterval(refresh,1500);
