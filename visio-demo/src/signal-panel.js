import { SIGNAL_LABELS, unavailableSignals } from './video-signals.js';

export function createSignalPanel({ onMicrophone }) {
  const panel = document.createElement('div');
  panel.id = 'video-signal-layers';
  panel.tabIndex = -1;
  panel.innerHTML = `<div class="signal-layers-heading"><h4>Indicateurs complémentaires</h4><span>Expérimental</span></div>
    <p class="signals-help">Flux <span class="signal-source-original">original</span><span class="signal-source-filtered">transformé</span> · 10 dernières secondes. Ces observations ne modifient pas le score.</p>
    <div id="signal-layer-rows"></div>
    <div class="signal-audio"><button id="layers-microphone" class="text-button" type="button" disabled>Activer la cohérence voix / bouche</button>
    <p class="signals-help">Micro local facultatif, sans enregistrement. Comparaison d’activité, sans lecture labiale.</p></div>`;
  document.getElementById('session-panel').after(panel);
  let selected = 'original';
  const results = { original: unavailableSignals(), filtered: unavailableSignals() };
  const rows = {};
  for (const [key, title] of Object.entries(SIGNAL_LABELS)) {
    const details = document.createElement('details'); details.className = 'signal-layer'; details.dataset.signal = key;
    const summary = document.createElement('summary');
    const name = document.createElement('span'); name.textContent = title;
    const value = document.createElement('strong');
    const explanation = document.createElement('p');
    summary.append(name, value); details.append(summary, explanation);
    panel.querySelector('#signal-layer-rows').append(details); rows[key] = { details, value, explanation };
  }
  const microphone = panel.querySelector('#layers-microphone');
  microphone.addEventListener('click', onMicrophone);
  function render() {
    panel.dataset.source = selected;
    for (const [key, data] of Object.entries(results[selected])) {
      const target = rows[key]; target.details.dataset.state = data.state;
      target.value.textContent = data.value; target.explanation.textContent = data.detail;
    }
  }
  render();
  return {
    select(key) { selected = key; render(); },
    update(key, data) { results[key] = data; if (selected === key) render(); },
    microphone(enabled, available) {
      microphone.disabled = !available;
      microphone.textContent = enabled ? 'Arrêter le microphone' : 'Activer la cohérence voix / bouche';
      microphone.setAttribute('aria-pressed', String(enabled));
    },
  };
}
