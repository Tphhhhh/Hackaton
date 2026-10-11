import { SIGNAL_LABELS, unavailableSignals } from './video-signals.js';

export function createSignalPanel({ onMicrophone }) {
  const panel = document.createElement('section');
  panel.id = 'video-signal-layers'; panel.setAttribute('aria-labelledby', 'signal-layers-title');
  panel.tabIndex = -1;
  panel.innerHTML = `<div class="signal-layers-heading"><h2 id="signal-layers-title">Signaux complémentaires</h2>
    <p class="signals-help">Cinq observations sur le flux <span class="signal-source-original">original</span><span class="signal-source-filtered">transformé</span>, mesurées sur dix secondes. Elles n’entrent pas dans le score.</p>
    <div class="signal-audio"><button id="layers-microphone" class="button secondary" type="button" disabled>Activer la cohérence voix / bouche</button>
    <p class="signals-help">Micro facultatif, sans enregistrement.</p></div></div>
    <div id="signal-layer-rows"></div>`;
  document.querySelector('.comparison-workspace').after(panel);
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
