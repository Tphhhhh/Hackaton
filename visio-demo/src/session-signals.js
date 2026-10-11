import './session-signals.css';

const $ = id => document.getElementById(id);
const node = (tag, text, cls) => { const n=document.createElement(tag); n.textContent=text; if(cls)n.className=cls; return n; };
const mean = a => a.reduce((s,x)=>s+x,0)/a.length;
const spread = a => a.length ? Math.sqrt(mean(a.map(x=>(x-mean(a))**2))) : 0;

export function createSessionSignals({ onMetadata = () => {}, onAudio = () => {}, onMicrophone = () => {} } = {}) {
  const panel=document.createElement('aside'); panel.id='session-panel'; panel.setAttribute('aria-label','Signaux techniques de cet appareil'); panel.tabIndex=-1;
  panel.innerHTML=`
    <div class="console-header"><div class="signals-heading"><div><p class="signals-kicker">LES INDICES, EN PERSPECTIVE</p><h2>Analyse de session</h2></div><span id="signals-dot" class="signals-dot"></span></div>
    <div class="console-source-field"><p class="console-source-label" id="console-source-label">Flux analysé</p>
    <div class="console-source" role="group" aria-labelledby="console-source-label"><button id="console-source-original" aria-pressed="true">Original</button><button id="console-source-filtered" aria-pressed="false">Transformé</button></div></div></div>
    <div class="console-result"><div class="console-overall"><span>Score global · confiance</span><div><strong id="console-overall-score">—</strong><span> / 100</span></div><p id="console-overall-state">En attente des analyses</p></div>
    <p class="console-legend"><span>0 · Inquiétant</span><span>100 · Rassurant</span></p>
    <p class="console-scale-help">Plus le score est élevé, plus les indices sont rassurants. Ce n’est pas une preuve d’authenticité.</p></div>
    <section class="console-group" aria-labelledby="console-video-title">
      <div class="console-group-heading"><h3 id="console-video-title">Analyse vidéo</h3><span id="console-video-bars-value">— / 5</span></div>
      <div id="console-video-bars" class="console-bars" role="meter" aria-valuemin="0" aria-valuemax="5" aria-label="Analyse vidéo indisponible"><i></i><i></i><i></i><i></i><i></i></div>
      <p id="console-video-state" class="signals-help">En attente d’une image analysable</p>
      <details class="console-detail"><summary>Étudier l’analyse vidéo</summary>
        <dl class="console-facts"><div><dt>Score vidéo · confiance</dt><dd id="console-video-score">— / 100</dd></div><div><dt>Qualité de l’image</dt><dd id="console-video-quality">Non vérifiable</dd></div><div><dt>Manipulations recherchées</dt><dd>Échange et animation du visage</dd></div><div><dt>Méthode</dt><dd>GenD PE · score lissé</dd></div></dl>
        <p id="console-video-detail" class="signals-help">Aucun résultat vidéo disponible.</p>
        <p class="signals-help">Le moteur vérifie qu’un seul visage est exploitable, puis examine ses pixels. Ces contrôles n’ont pas de scores séparés.</p>
        <p id="live-score-status" class="signals-help" role="status">En attente de la caméra</p>
      </details>
    </section>
    <section class="console-group" aria-labelledby="console-meta-title">
      <div class="console-group-heading"><h3 id="console-meta-title">Métadonnées</h3><span id="console-meta-bars-value">— / 5</span></div>
      <div id="console-meta-bars" class="console-bars" role="meter" aria-valuemin="0" aria-valuemax="5" aria-label="Métadonnées indisponibles"><i></i><i></i><i></i><i></i><i></i></div>
      <p id="console-meta-state" class="signals-help">Vérifications de l’appareil en attente</p>
      <details id="console-metadata-details" class="console-detail"><summary>Étudier les métadonnées</summary>
        <dl class="console-facts"><div><dt>Pénalité appareil</dt><dd id="console-meta-score">— / 100</dd></div></dl>
        <p class="signals-help"><span id="signals-count">—</span> <span id="signals-caption">En attente de mesures</span></p>
        <p id="signals-state" class="signals-help" role="status">Activez la caméra pour démarrer.</p>
        <h4 class="console-category">Caméra et environnement</h4><div id="signals-rows"></div>
        <h4 class="console-category">Réseau et lieu déclaré</h4><div id="signals-network-rows"></div>
        <h4 class="console-category">Combinaison des indices</h4><div id="signals-combination-rows"></div>
    <details class="signals-section"><summary>Vérifications facultatives</summary>
      <label class="signals-check"><input id="signals-network" type="checkbox">Vérifier le réseau</label>
      <p class="signals-help">Contacte ipify, ipapi.co et Cloudflare, qui voient votre IP. Aucun envoi de vidéo. VPN non confirmé.</p>
      <p id="signals-network-state" class="signals-help">Désactivé</p>
      <label>Fuseau déclaré<select id="signals-timezone"><option value="">Non renseigné</option><option value="Europe/Paris">Paris</option><option value="Europe/London">Londres</option><option value="America/New_York">New York</option><option value="America/Los_Angeles">Los Angeles</option><option value="Africa/Casablanca">Casablanca</option><option value="Asia/Kolkata">Kolkata</option><option value="Asia/Tokyo">Tokyo</option></select></label>
      <p class="signals-help">Le fuseau du lieu déclaré, jamais l’origine de la personne.</p>
      <label>Email (facultatif)<input id="signals-email" type="email" maxlength="254" autocomplete="off" placeholder="nom@exemple.fr"></label>
      <label>Téléphone international (facultatif)<input id="signals-phone" type="tel" maxlength="80" autocomplete="off" placeholder="+33…"></label>
      <label class="signals-check"><input id="signals-refused" type="checkbox">Refus de caméra déclaré</label>
      <p class="signals-help">Signal faible, renseigné manuellement. Aucun dossier ni inscription.</p>
      <div id="signals-contact-rows"></div>
    </details>
    <details class="signals-section"><summary>Observations du navigateur</summary>
      <p class="signals-help">Mesures expérimentales sans points de risque.</p>
      <dl id="signals-observations" class="signals-observations"></dl>
      <button id="signals-mic" class="button secondary wide" disabled>Mesurer le microphone</button>
      <p class="signals-help">Facultatif. Volume, réglages et cohérence avec la bouche, sans enregistrement ni reconnaissance vocale. Un son propre ne prouve pas une voix synthétique.</p>
      <button id="signals-motion" class="text-button" disabled>Mesurer le mouvement du mobile</button>
      <p class="signals-help">Permission éventuelle. L’immobilité ne prouve pas un émulateur.</p>
    </details>
    <details class="signals-section"><summary>Défis guidés</summary>
      <p class="signals-help">Chronomètre et confirmation manuelle. Le modèle ne vérifie pas l’exécution de ces défis.</p>
      <label>Exercice<select id="signals-challenge"><option value="head">Tournez la tête</option><option value="hand">Passez la main devant le visage</option><option value="code">Lisez un code à voix haute</option><option value="response">Temps de réponse à une question</option><option value="interrupt">Test d’interruption</option></select></label>
      <p id="signals-prompt" class="signals-help">Choisissez un exercice.</p>
      <div class="signals-actions"><button id="signals-start-challenge" class="button secondary" disabled>Démarrer</button><button id="signals-confirm" class="text-button" disabled>Action observée</button></div>
      <p id="signals-challenge-result" role="status" class="signals-help">Aucun défi réalisé.</p>
    </details>
    <details class="signals-section"><summary>Comprendre les indices</summary><p id="signals-points" class="signals-help">Les règles seront détaillées après la première mesure.</p><p class="signals-help">X1 conserve le bonus de combinaison du module métadonnées. Il n’élimine pas les faux positifs. VPN, webcam virtuelle ou rendu logiciel peuvent avoir des usages légitimes.</p><p class="signals-help">Les métadonnées concernent ce navigateur, pas l’ordinateur d’un participant distant. La comparaison d’IP WebRTC est indisponible : cette démo n’établit pas d’appel WebRTC.</p></details>
      </details>
    </section>
    <details class="console-detail console-method"><summary>Calcul du score global</summary><p id="console-formula" class="signals-help"></p></details>
    <p class="console-footnote">Indice exploratoire, pas une probabilité. Métadonnées communes aux deux vues ; contrôles incomplets visibles dans les détails.</p>`;
  $('live-summary').before(panel);
  let stream=null, video=null, generation=0, interval, frameId, frames=[], lastPresentation, previousCamera, previousSettings;
  let cameraChanges=0, settingsChanges=0, gpu='', deviceError='', controls=[], interactions={moves:0,keys:0,pastes:0}, keyTimes=[];
  let activeRequest=null, revision=0, debounce, networkPending=false, networkEpoch=0, networkControllers=new Set(), network={ip:'',org:'',rtt_ms:[]}, lastIP='', ipChanges=0, networkAt=0;
  let mic=null, audioContext=null, analyser=null, audioData=null, audioError='', audioPending=false, audioTimer;
  let motion=[], motionPending=false, motionListening=false, motionMessage='Non mesuré', challengeStart=null, challengeTimer;
  const rows=new Map();
  let metadataExpiry;
  const clearResult=message=>{
    clearTimeout(metadataExpiry); onMetadata(null);
    $('signals-count').textContent='—'; $('signals-caption').textContent='En attente de mesures';
    $('signals-rows').replaceChildren(); $('signals-contact-rows').replaceChildren(); $('signals-network-rows').replaceChildren(); $('signals-combination-rows').replaceChildren(); rows.clear(); $('signals-state').textContent=message;
    $('signals-points').textContent='Aucun résultat actif.';
  };
  function observation(label,value) { $('signals-observations').append(node('dt',label),node('dd',value)); }
  function renderObservations() {
    $('signals-observations').replaceChildren();
    const automated=navigator.webdriver===true || /Headless/i.test(navigator.userAgent);
    observation('Automatisation',stream ? (automated?'Indicateur déclaré par le navigateur. Peut aussi être un outil de test.':'Aucun indicateur exposé. Un automate peut le masquer.') : 'En attente');
    observation('Cadence observée',frames.length>=20 ? `${(1000/mean(frames)).toFixed(1)} i/s · variation ${spread(frames).toFixed(1)} ms. Cadence d’affichage, influencée par la charge.` : 'Échantillons insuffisants');
    observation('Réglages caméra',stream ? (controls.length?controls.join(', '):'Exposition / mise au point / balance des blancs non exposées. Dépend aussi du navigateur.') : 'En attente');
    observation('Interactions locales',stream ? `${interactions.moves} mouvements · ${interactions.keys} frappes · ${interactions.pastes} collages. Aucun contenu conservé.${keyTimes.length>2?` Variation des intervalles : ${spread(keyTimes).toFixed(0)} ms.`:''} L’absence d’interaction ne prouve rien.` : 'Non mesurées');
    let audio=audioError || 'Microphone désactivé';
    if(analyser && mic) {
      analyser.getFloatTimeDomainData(audioData);
      const rms=Math.sqrt(mean(Array.from(audioData,x=>x*x)));
      const settings=mic.getAudioTracks()[0]?.getSettings()||{};
      audio=`Volume instantané : ${Math.max(-100,20*Math.log10(rms||1e-5)).toFixed(0)} dBFS · réduction du bruit : ${settings.noiseSuppression===undefined?'inconnue':settings.noiseSuppression?'active':'inactive'}. Aucune détection de voix synthétique.`;
    }
    observation('Audio',audio);
    observation('Mouvement mobile',motion.length ? `${motion.length} échantillons · dispersion ${spread(motion).toFixed(3)} m/s². Aucun verdict.` : motionMessage);
    observation('IP WebRTC','Non disponible : aucun appel WebRTC dans cette démo.');
  }
  function stopMic() {
    clearInterval(audioTimer); onMicrophone(false, !!stream);
    mic?.getTracks().forEach(t=>t.stop()); mic=null; analyser=null; audioData=null;
    audioContext?.close().catch(()=>{}); audioContext=null;
    $('signals-mic').textContent='Mesurer le microphone';
  }
  function cancelNetwork() {
    networkEpoch++; networkControllers.forEach(c=>c.abort()); networkControllers.clear(); networkPending=false;
    network={ip:'',org:'',rtt_ms:[]}; networkAt=0; lastIP=''; ipChanges=0;
  }
  function stop() {
    generation++; revision++; activeRequest?.abort(); activeRequest=null; clearInterval(interval); clearTimeout(debounce);
    if(video && frameId!==undefined) video.cancelVideoFrameCallback?.(frameId);
    frameId=undefined; stream=null; video=null; frames=[]; lastPresentation=undefined; previousCamera=undefined; previousSettings=undefined;
    cameraChanges=0; settingsChanges=0; interactions={moves:0,keys:0,pastes:0};keyTimes=[];lastKey=undefined;
    controls=[]; gpu='';deviceError='';stopMic();audioError='';audioPending=false;
    cancelNetwork(); window.removeEventListener('devicemotion',onMotion);motionListening=false;motionPending=false;motion=[];motionMessage='Non mesuré';
    clearInterval(challengeTimer);challengeStart=null;
    $('signals-challenge-result').textContent='Aucun défi actif.';
    $('signals-prompt').textContent='Choisissez un exercice.';
    for(const id of ['signals-mic','signals-motion','signals-start-challenge','signals-confirm']) $(id).disabled=true;
    $('signals-dot').classList.remove('active');$('signals-network-state').textContent=$('signals-network').checked?'En attente de la caméra':'Désactivé';
    clearResult('Session arrêtée · mesures effacées.');renderObservations();
  }
  function capture() {
    const track=stream?.getVideoTracks()[0];
    if(!track || track.readyState==='ended') return null;
    const settings=track.getSettings?.() || {}, camera=settings.deviceId || track.id;
    if(previousCamera!==undefined && previousCamera!==camera) cameraChanges++;
    previousCamera=camera;
    const signature=JSON.stringify([settings.width,settings.height,settings.frameRate===undefined?null:Math.round(settings.frameRate*10)/10]);
    if(previousSettings!==undefined && previousSettings!==signature) settingsChanges++;
    previousSettings=signature;
    try { const caps=track.getCapabilities?.()||{};controls=['exposureMode','focusMode','whiteBalanceMode'].filter(key=>key in caps).map(key=>({exposureMode:'exposition',focusMode:'mise au point',whiteBalanceMode:'balance des blancs'})[key]); } catch { controls=[]; }
    return track;
  }
  async function analyze() {
    const own=++revision, gen=generation; activeRequest?.abort(); activeRequest=new AbortController();
    const track=capture();
    const payload={active:!!track,camera:track?.label||'',microphone:mic?.getAudioTracks()[0]?.label||'',gpu_renderer:gpu,
      browser_timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'',browser_utc_offset:-new Date().getTimezoneOffset()/60,
      declared_timezone:$('signals-timezone').value,email:$('signals-email').value.trim(),phone:$('signals-phone').value.trim(),
      camera_refused:$('signals-refused').checked,camera_changes:cameraChanges,settings_changes:settingsChanges,
      network_enabled:$('signals-network').checked,...network,ip_changes:ipChanges};
    try {
      const response=await fetch('/api/session/analyze',{method:'POST',headers:{'Content-Type':'application/json','X-Visio-Request':'1'},body:JSON.stringify(payload),signal:activeRequest.signal});
      if(!response.ok) throw new Error('Mesures techniques indisponibles.');
      const data=await response.json();if(gen!==generation||own!==revision)return;
      clearTimeout(metadataExpiry); onMetadata(track ? data : null);
      if(track) metadataExpiry=setTimeout(()=>clearResult('Mesures expirées · en attente de nouvelles vérifications.'),8000);
      $('signals-state').textContent=track?'Mesures actualisées · '+new Date().toLocaleTimeString('fr-FR'):deviceError||'Vérifications facultatives uniquement.';
      $('signals-count').textContent=String(data.flag_count);
      $('signals-caption').textContent=`point${data.flag_count>1?'s':''} à vérifier · ${data.measured_count} contrôles renseignés`;
      $('signals-points').textContent=`${data.points} points d’alerte, retirés du score vidéo dans le score global. Ce n’est pas une probabilité.`;
      for(const row of data.rows) {
        let item=rows.get(row.code);
        if(!item) { const detail=node('details','', 'signal-row'), summary=node('summary',''), title=node('span',row.title), state=node('span',''), text=node('p','');summary.append(title,state);detail.append(summary,text);$(row.code.startsWith('C')?'signals-contact-rows':row.code==='X1'?'signals-combination-rows':['I2','I4','I5'].includes(row.code)?'signals-network-rows':'signals-rows').append(detail);item={detail,state,text};rows.set(row.code,item); }
        item.detail.dataset.state=row.state;
        item.state.textContent=row.state==='flag'?'À vérifier':row.state==='observed'?'Aucun indice':'Non vérifié';
        item.text.textContent=`${row.code} · ${row.detail}${row.weight?' (+'+row.weight+' points)':''}`;
      }
    } catch(error) { if(error.name==='AbortError'||gen!==generation||own!==revision)return;clearResult('Mesures indisponibles · réessayez dans un instant.'); }
  }
  async function external(url, options={}) {
    const controller=new AbortController();networkControllers.add(controller);const timeout=setTimeout(()=>controller.abort(),3500);
    try{return await fetch(url,{...options,signal:controller.signal,credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store'});}
    finally{clearTimeout(timeout);networkControllers.delete(controller);}
  }
  async function checkNetwork() {
    if(!stream || !$('signals-network').checked || networkPending)return;
    networkPending=true;const epoch=networkEpoch,gen=generation;
    $('signals-network-state').textContent='Mesure réseau en cours…';
    const current=()=>gen===generation&&epoch===networkEpoch&&$('signals-network').checked&&!!stream;
    const result={ip:'',org:'',rtt_ms:[]};
    try {
      await Promise.all([
        (async()=>{const response=await external('https://api.ipify.org?format=json');if(!response.ok)throw new Error();const data=await response.json();if(!current())return;
          if(typeof data.ip!=='string'||!/^[0-9a-f:.]{3,64}$/i.test(data.ip))throw new Error();result.ip=data.ip;
          try{const geo=await external(`https://ipapi.co/${encodeURIComponent(data.ip)}/json/`);if(geo.ok){const info=await geo.json();result.org=String(info.org||'').slice(0,300);}}catch{}
        })().catch(()=>{}),
        (async()=>{for(let i=0;i<3&&current();i++){const start=performance.now();try{await external(`https://www.cloudflare.com/cdn-cgi/trace?t=${Date.now()}-${i}`,{mode:'no-cors'});result.rtt_ms.push(Math.round(performance.now()-start));}catch{}}})(),
      ]);
      if(!current())return;
      if(result.ip){if(lastIP&&lastIP!==result.ip)ipChanges++;lastIP=result.ip;}
      network=result;networkAt=Date.now();
      $('signals-network-state').textContent=result.ip&&result.rtt_ms.length?'Actualisé · prochaine mesure dans 30 s':result.ip||result.rtt_ms.length?'Mesure partielle · service réseau indisponible':'Services réseau indisponibles · aucun résultat déduit';
      await analyze();
    } finally {if(current())networkPending=false;}
  }
  function onMotion(e) {
    const a=e.accelerationIncludingGravity;
    if(a && [a.x,a.y,a.z].every(Number.isFinite)){motion.push(Math.hypot(a.x,a.y,a.z));if(motion.length>100)motion.shift();}
  }
  function observeFrame(now,metadata) {
    if(!stream || !video)return;
    const t=metadata.presentationTime??now;
    if(lastPresentation!==undefined&&t>lastPresentation){frames.push(t-lastPresentation);if(frames.length>90)frames.shift();}
    lastPresentation=t;frameId=video.requestVideoFrameCallback(observeFrame);
  }
  function start(s,v) {
    stop();stream=s;video=v;$('signals-refused').checked=false;
    try {const canvas=document.createElement('canvas'),gl=canvas.getContext('webgl');if(gl){const ext=gl.getExtension('WEBGL_debug_renderer_info');gpu=String(gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER));gl.getExtension('WEBGL_lose_context')?.loseContext();}}catch{}
    $('signals-dot').classList.add('active');
    onMicrophone(false, true);
    for(const id of ['signals-mic','signals-motion','signals-start-challenge']) $(id).disabled=false;
    if(video.requestVideoFrameCallback)frameId=video.requestVideoFrameCallback(observeFrame);
    interval=setInterval(()=>{if(!capture()){stop();return;}renderObservations();analyze();if($('signals-network').checked&&!networkPending&&Date.now()-networkAt>30000)checkNetwork();},2500);
    analyze();renderObservations();if($('signals-network').checked)checkNetwork();
  }
  let lastKey;
  window.addEventListener('pointermove',e=>{if(stream&&e.isTrusted)interactions.moves++;},{passive:true});
  window.addEventListener('keydown',e=>{if(!stream||!e.isTrusted||e.repeat)return;interactions.keys++;const now=performance.now();if(lastKey!==undefined){keyTimes.push(now-lastKey);if(keyTimes.length>50)keyTimes.shift();}lastKey=now;});
  window.addEventListener('paste',e=>{if(stream&&e.isTrusted)interactions.pastes++;});
  for(const id of ['signals-timezone','signals-email','signals-phone','signals-refused']) $(id).addEventListener('input',()=>{clearTimeout(debounce);revision++;activeRequest?.abort();debounce=setTimeout(analyze,350);});
  $('signals-network').addEventListener('change',()=>{cancelNetwork();$('signals-network-state').textContent=$('signals-network').checked?'En attente de la caméra':'Désactivé';analyze();if($('signals-network').checked)checkNetwork();});
  $('signals-mic').addEventListener('click',async()=>{
    if(mic){stopMic();renderObservations();analyze();return;}if(!stream||audioPending)return;
    audioPending=true;audioError='';const gen=generation;$('signals-mic').disabled=true;onMicrophone(false,false);
    try {
      const acquired=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
      if(gen!==generation||!stream){acquired.getTracks().forEach(t=>t.stop());return;}
      mic=acquired;audioContext=new AudioContext();await audioContext.resume();
      if(gen!==generation||!mic)return;
      analyser=audioContext.createAnalyser();analyser.fftSize=2048;audioData=new Float32Array(analyser.fftSize);audioContext.createMediaStreamSource(mic).connect(analyser);
      onMicrophone(true, true);
      audioTimer=setInterval(()=>{
        if(!analyser || audioContext?.state!=='running' || document.hidden)return;
        analyser.getFloatTimeDomainData(audioData);
        onAudio(performance.now(),Math.sqrt(mean(Array.from(audioData,x=>x*x))));
      },50);
      mic.getTracks().forEach(t=>t.addEventListener('ended',()=>{if(gen===generation){stopMic();renderObservations();analyze();}}));
      $('signals-mic').textContent='Arrêter le microphone';
    } catch {if(gen===generation){stopMic();audioError='Microphone indisponible ou permission refusée. Aucun indice déduit.';}}
    finally{if(gen===generation){audioPending=false;$('signals-mic').disabled=!stream;onMicrophone(!!mic,!!stream);renderObservations();analyze();}}
  });
  $('signals-motion').addEventListener('click',async()=>{
    if(!stream||motionPending||motionListening)return;const gen=generation;motionPending=true;
    try {
      if(!window.DeviceMotionEvent)throw new Error();
      if(typeof DeviceMotionEvent.requestPermission==='function'&&await DeviceMotionEvent.requestPermission()!=='granted')throw new Error();
      if(gen!==generation||!stream)return;
      window.addEventListener('devicemotion',onMotion);motionListening=true;motionMessage='En écoute · aucune donnée de capteur reçue';
    } catch {if(gen===generation)motionMessage='Capteur indisponible ou permission refusée';}
    finally{if(gen===generation){motionPending=false;renderObservations();}}
  });
  $('signals-start-challenge').addEventListener('click',()=>{
    if(!stream)return;clearInterval(challengeTimer);challengeStart=performance.now();
    const code=String(crypto.getRandomValues(new Uint32Array(1))[0]%9000+1000);
    const prompts={head:'Demandez : « Tournez la tête à gauche, puis à droite. »',hand:'Demandez : « Passez une main devant votre visage. »',code:`Demandez : « Lisez le code ${code}. »`,response:'Lancez le chronomètre à la fin de votre question. Confirmez au début de la réponse.',interrupt:'Interrompez la personne au lancement du chronomètre. Confirmez lorsqu’elle réagit.'};
    $('signals-prompt').textContent=prompts[$('signals-challenge').value];$('signals-confirm').disabled=false;
    const update=()=>{$('signals-challenge-result').textContent=`En cours · ${((performance.now()-challengeStart)/1000).toFixed(1)} s`;};update();challengeTimer=setInterval(update,100);
  });
  $('signals-confirm').addEventListener('click',()=>{if(challengeStart===null)return;clearInterval(challengeTimer);$('signals-challenge-result').textContent=`Action confirmée manuellement après ${((performance.now()-challengeStart)/1000).toFixed(1)} s. Aucune validation automatique.`;challengeStart=null;$('signals-confirm').disabled=true;});
  $('signals-challenge').addEventListener('change',()=>{clearInterval(challengeTimer);challengeStart=null;$('signals-confirm').disabled=true;$('signals-challenge-result').textContent='Aucun défi actif.';});
  renderObservations();
  return {start,stop,toggleMicrophone(){ $('signals-mic').click(); },unavailable(message){deviceError=message;$('signals-state').textContent=message;}};
}
