// Display indices, not calibrated probabilities. High confidence is green.
const valid = value => Number.isFinite(value) && value>=0 && value<=100;
export function confidenceLevel(score) {
  return valid(score) ? Math.floor(score/20) : null;
}
export function confidenceScore(videoRisk, metadataPenalty) {
  return valid(videoRisk) && valid(metadataPenalty) ? Math.max(0,100-videoRisk-metadataPenalty) : null;
}

export function createAnalysisConsole({ onSource = () => {} } = {}) {
  const $=id=>document.getElementById(id);
  const format=n=>n===null?'—':n.toLocaleString('fr-FR',{maximumFractionDigits:1});
  let selected='original', metadata=null;
  const video={original:null,filtered:null};
  function bars(id,score) {
    const group=$(id),level=confidenceLevel(score);
    group.dataset.tone=level===null?'unknown':level>=4?'positive':level===3?'medium':'warning';
    group.setAttribute('aria-label',level===null?'Analyse indisponible':`${level} sur 5, indice de confiance`);
    group.setAttribute('aria-valuetext',level===null?'Non mesuré':`${level} sur 5`);
    if(level===null)group.removeAttribute('aria-valuenow');else group.setAttribute('aria-valuenow',String(level));
    [...group.children].forEach((bar,i)=>bar.dataset.filled=String(level!==null&&i<level));
    $(`${id}-value`).textContent=level===null?'— / 5':`${level} / 5`;
  }
  function render() {
    const current=video[selected];
    const visual=current?.score ?? null;
    const penalty=metadata?.points ?? null;
    const visualConfidence=visual===null?null:100-visual;
    const overall=confidenceScore(visual,penalty);
    bars('console-video-bars',visualConfidence);bars('console-meta-bars',penalty===null?null:100-penalty);
    $('console-video-quality').textContent=visual===null?'Non vérifiable':'Image exploitable';
    $('console-video-score').textContent=`${format(visualConfidence)} / 100`;
    $('console-meta-score').textContent=penalty===null?'—':penalty===0?'Aucun point retiré':`−${format(penalty)} points`;
    $('console-video-state').textContent=visual===null?'En attente d’une image analysable':selected==='original'?'Flux original · GenD PE':'Flux transformé · GenD PE';
    $('console-video-detail').textContent=current?.note?.replace('Score lissé · brut :','Indices GenD bruts :') || 'Aucun résultat vidéo disponible.';
    $('console-meta-state').textContent=metadata?`${metadata.measured_count} contrôles · ${penalty===0?'aucune pénalité':format(penalty)+' points retirés'}`:'Vérifications de l’appareil en attente';
    $('console-overall-score').textContent=overall===null?'En attente':format(overall);
    $('console-overall-score').dataset.tone=overall===null?'unknown':overall>=80?'positive':overall>=60?'medium':'warning';
    $('console-overall-state').textContent=overall===null ? visual===null?'En attente de l’analyse vidéo':'En attente des métadonnées'
      : `Vidéo ${format(visualConfidence)} − pénalité ${format(penalty)}`;
    $('console-formula').textContent='Score vidéo (100 − indices GenD PE) moins les points d’alerte métadonnées, avec un minimum de 0. Aucune alerte n’ajoute de points.';
    for(const key of ['original','filtered']) $(`console-source-${key}`).setAttribute('aria-pressed',String(selected===key));
  }
  for(const key of ['original','filtered']) $(`console-source-${key}`).addEventListener('click',()=>{selected=key;render();onSource(key);});
  render();
  return {
    video(key,score,note) {video[key]={score:score===null?null:score*100,note};render();},
    metadata(data) {metadata=data?.measured_count>0&&valid(data.points)?data:null;render();},
  };
}
