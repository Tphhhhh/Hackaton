// Only explicit clicks send the selected File to the same-origin loopback engine.
export function connectLocalEngine({ api, getFile, button, cancelButton, status }) {
  let available = false;
  let modelName = 'GenD';
  let active = null;
  const refresh = () => {
    button.disabled = !available || !getFile() || !!active;
    cancelButton.hidden = !active;
    button.textContent = active ? 'Analyse en cours…' : `Analyser avec ${modelName}`;
  };
  const cancel = () => {
    if (!active) return;
    const job = active;
    active = null;
    job.controller.abort();
    fetch(`/api/analyze/${job.mediaId}`, { method: 'DELETE', headers: { 'X-Visio-Request': '1' }, keepalive: true }).catch(() => {});
    status.textContent = 'Analyse annulée. Le moteur libère ses ressources.';
    refresh();
  };
  window.addEventListener('visio:mediachange', () => { cancel(); refresh(); });
  window.addEventListener('pagehide', cancel);
  cancelButton.addEventListener('click', cancel);
  button.addEventListener('click', async () => {
    const media = api.getContext().media;
    const file = getFile();
    if (!available || active || !media || !file) return;
    const job = { mediaId: media.id, controller: new AbortController() };
    active = job;
    api.clearResult(); api.clearTracking(); api.clearMetadata();
    status.textContent = 'Analyse locale du clip et repérage des points du visage…';
    refresh();
    try {
      const suffix = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      const response = await fetch(`/api/analyze/${media.id}?suffix=${encodeURIComponent(suffix)}`, {
        method: 'POST', body: file, signal: job.controller.signal,
        headers: { 'Content-Type': 'application/octet-stream', 'X-Visio-Request': '1' },
      });
      const data = await response.json();
      if (active !== job || api.getContext().media?.id !== job.mediaId) return;
      if (!response.ok) throw new Error(data.error || 'Le moteur local est indisponible.');
      if (data.media_id !== job.mediaId) throw new Error('Résultat associé à un autre extrait.');
      const result = api.receiveResult(data.result, { mediaId: job.mediaId });
      if (!result.ok) throw new Error(result.errors.join(' '));
      if (data.tracking) {
        const tracking = api.receiveTracking(data.tracking);
        if (!tracking.ok) throw new Error(`Analyse reçue, suivi refusé : ${tracking.errors.join(' ')}`);
      }
      status.textContent = data.result.status === 'completed'
        ? 'Analyse terminée. Lancez la lecture pour voir les points détectés.'
        : 'Analyse incomplète : consultez le diagnostic affiché.';
    } catch (error) {
      if (active === job && error.name !== 'AbortError') status.textContent = error.message || 'Connexion au moteur interrompue.';
    } finally {
      if (active === job) { active = null; refresh(); }
    }
  });
  refresh();
  fetch('/api/status').then(response => response.ok ? response.json() : null).then(data => {
    available = data?.backend === 'gend';
    modelName = data?.model === 'gend_pe' ? 'GenD PE' : 'GenD';
    status.textContent = available
      ? `${modelName} local connecté. Choisissez un clip puis lancez l’analyse.`
      : 'Moteur local non connecté. Vous pouvez importer un résultat JSON.';
    refresh();
  }).catch(() => { status.textContent = 'Moteur local non connecté. Vous pouvez importer un résultat JSON.'; });
}
