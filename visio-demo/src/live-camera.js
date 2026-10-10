// Camera frames stay in memory. One frame at a time goes to the local worker.
export function startLiveCamera({ video, onState, onFrame, onError, onReady = () => {}, acquireMedia }) {
  let stopped = false;
  let stream;
  let worker;
  let frameHandle;
  let busy = false;
  let ready = false;
  let lastTime = -1;
  let lastSent = -Infinity;
  let watchdog;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearTimeout(watchdog);
    cancelAnimationFrame(frameHandle);
    worker?.terminate();
    stream?.getTracks().forEach(track => track.stop());
    video.pause();
    video.srcObject = null;
  };
  const fail = message => { if (!stopped) { stop(); onError(message); } };
  const armWatchdog = (message, delay = 30000) => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => fail(message), delay);
  };
  const tick = async now => {
    if (stopped) return;
    frameHandle = requestAnimationFrame(tick);
    if (!ready || busy || document.hidden || video.readyState < 2 || video.currentTime === lastTime || now - lastSent < 50) return;
    busy = true;
    lastTime = video.currentTime;
    lastSent = now;
    try {
      const bitmap = await createImageBitmap(video);
      if (stopped) { bitmap.close(); return; }
      armWatchdog('Le suivi ne répond plus. Relancez la caméra.', 15000);
      worker.postMessage({ type: 'frame', bitmap, timestamp: now }, [bitmap]);
    } catch { fail('Impossible de traiter les images de la caméra. Relancez la caméra.'); }
  };
  (async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Utilisez localhost ou une adresse HTTPS pour accéder à la caméra.');
      onState(acquireMedia ? 'Choisissez la fenêtre d’aperçu à partager…' : 'Autorisez l’accès à votre caméra dans le navigateur…');
      stream = await (acquireMedia ? acquireMedia() : navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } }));
      if (stopped) { stream.getTracks().forEach(track => track.stop()); return; }
      stream.getVideoTracks().forEach(track => {
        track.addEventListener('ended', () => fail('La caméra a été déconnectée. Rebranchez-la puis relancez-la.'));
        track.addEventListener('mute', () => { if (!stopped) { onFrame({ faces: [], timestamp: performance.now(), inferenceMs: 0 }); onState('Caméra momentanément interrompue…'); } });
      });
      video.srcObject = stream;
      armWatchdog('La caméra ne fournit pas d’image. Vérifiez sa disponibilité puis réessayez.');
      await video.play();
      if (stopped) return;
      onState(acquireMedia ? 'Flux partagé connecté · chargement du suivi facial…' : 'Caméra connectée · chargement du suivi facial…');
      worker = new Worker(new URL('./live-tracker.worker.js', import.meta.url), { type: 'module' });
      worker.onerror = () => fail('Le suivi facial n’a pas pu démarrer. Rechargez la page puis réessayez.');
      worker.onmessage = ({ data }) => {
        if (stopped) { data.bitmap?.close(); return; }
        if (data.type === 'ready') {
          clearTimeout(watchdog);
          ready = true;
          onReady(data);
          onState(acquireMedia ? 'Partage en direct · suivi actif' : 'Caméra en direct · suivi actif');
        } else if (data.type === 'result') {
          clearTimeout(watchdog);
          busy = false;
          onFrame(data);
        } else if (data.type === 'error') fail('Le suivi facial est indisponible. Rechargez la page pour relancer le modèle.');
      };
      worker.postMessage({ type: 'init', baseUrl: new URL(`${import.meta.env.BASE_URL}live-assets/`, location.href).href });
      armWatchdog('Le modèle de suivi n’a pas pu être chargé. Vérifiez les fichiers de l’application puis réessayez.');
      frameHandle = requestAnimationFrame(tick);
    } catch (error) {
      const messages = {
        NotAllowedError: 'Accès à la caméra refusé. Autorisez la caméra dans les paramètres du site puis réessayez.',
        NotFoundError: 'Aucune webcam détectée. Branchez une caméra puis réessayez.',
        NotReadableError: 'Caméra indisponible ou utilisée par une autre application. Libérez-la puis réessayez.',
        OverconstrainedError: 'Cette caméra ne prend pas en charge le format demandé.',
      };
      fail(messages[error.name] || error.message || 'Impossible de démarrer la caméra.');
    }
  })();
  return stop;
}
