"""Selected technical rules for one live device. Stateless; no candidate dossier."""
from datetime import datetime, timezone
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from . import checks

# Provider-name heuristic inherited from the metadata demo, never a VPN proof.
HOSTING = re.compile(r'amazon|aws|google|microsoft|azure|digitalocean|ovh|hetzner|linode|akamai|vultr|choopa|m247|datacamp|leaseweb|contabo|scaleway|oracle|alibaba|tencent|hosting|server|cloud|vpn', re.I)


def validate(value):
    if not isinstance(value, dict):
        raise ValueError('Objet de mesures requis.')
    result = {}
    for key, maximum in {'camera':300, 'microphone':300, 'gpu_renderer':500,
                         'browser_timezone':100, 'declared_timezone':100,
                         'email':254, 'phone':80, 'country':2, 'ip':64, 'org':300}.items():
        item = value.get(key, '')
        if not isinstance(item, str) or len(item)>maximum:
            raise ValueError(f'Champ invalide : {key}.')
        result[key] = item.strip()
    for key, lower, upper in [('browser_utc_offset',-14,14), ('camera_changes',0,10000),
                              ('settings_changes',0,10000), ('ip_changes',0,10000)]:
        item = value.get(key, 0)
        if isinstance(item,bool) or not isinstance(item,(int,float)) or not math.isfinite(item) or not lower<=item<=upper:
            raise ValueError(f'Mesure invalide : {key}.')
        if key.endswith('changes') and item != int(item):
            raise ValueError('Un compteur doit être entier.')
        result[key] = item
    for key in ('active', 'camera_refused', 'network_enabled'):
        item=value.get(key, False)
        if not isinstance(item,bool): raise ValueError(f'Booléen requis : {key}.')
        result[key]=item
    times=value.get('rtt_ms', [])
    if not isinstance(times,list) or len(times)>6 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not 0<=n<=30000 for n in times):
        raise ValueError('Temps réseau invalides.')
    result['rtt_ms']=times
    if result['declared_timezone']:
        try: ZoneInfo(result['declared_timezone'])
        except (ZoneInfoNotFoundError, ValueError): raise ValueError('Fuseau déclaré inconnu.') from None
    return result


def evaluate(value):
    v=validate(value)
    s={'devices':{'video':[v['camera']] if v['active'] else [],
                  'audio':[v['microphone']] if v['active'] else []},
       'gpu_renderer':v['gpu_renderer'] if v['active'] else '',
       'browser_timezone':v['browser_timezone'], 'browser_utc_offset':v['browser_utc_offset'],
       'video_settings_changes':v['settings_changes'] if v['active'] else 0,
       'rtt_ms':v['rtt_ms'] if v['active'] and v['network_enabled'] else []}
    c={'interview_session':s, 'declared_location':{'country':v['country']},
       'email':v['email'], 'phone':v['phone'], 'full_name':''}
    rows=[]; signals=[]
    def add(code, title, ready, signal=None, detail='Aucun indice relevé par cette règle.'):
        if signal: signals.append(signal)
        rows.append({'code':code,'title':title,'state':'flag' if signal else 'observed' if ready else 'unavailable',
                     'detail':signal.evidence if signal else detail,'weight':signal.weight if signal else 0})
    active=v['active']
    add('I1','Caméra et micro',bool(v['camera'] or v['microphone']) and active,checks.check_virtual_camera(c),
        f"Caméra : {v['camera'] or 'nom indisponible'} · Micro : {v['microphone'] or 'non mesuré (désactivé)'}. Seuls les périphériques utilisés sont examinés.")
    add('L1','Changement de caméra',active,checks.Signal('L1_CAMERA_CHANGE',min(20,10*v['camera_changes']),f"Source caméra remplacée {v['camera_changes']:.0f} fois dans cette session.") if active and v['camera_changes'] else None,
        'Aucun remplacement de source observé.' if active else 'En attente de la caméra.')
    add('I3','Moteur graphique',bool(s['gpu_renderer']),checks.check_vm_gpu(c),s['gpu_renderer'] or 'Information non disponible.')
    network=active and v['network_enabled']
    reasons=[]
    if network and v['ip']:
        if HOSTING.search(v['org']): reasons.append("nom d’opérateur évoquant un hébergeur (heuristique à confirmer) : "+v['org'])
        if v['ip_changes']: reasons.append(f"IP publique changée {v['ip_changes']:.0f} fois")
    ip_signal=checks.Signal('I4_INTERVIEW_IP',min(25,len(reasons)*10),'; '.join(reasons)+'. Un VPN ne peut pas être confirmé ici.') if reasons else None
    add('I4','Adresse réseau',bool(network and v['ip']),ip_signal,
        (f"{v['ip']} · {v['org'] or 'opérateur inconnu'}. VPN non déterminé." if network and v['ip'] else 'Vérification réseau facultative, non disponible.'))
    latency=checks.check_latency(c)
    if latency: latency.evidence=latency.evidence.replace('Temps de réponse médian','Temps HTTP médian').replace('service réseau de référence','point Cloudflare de référence (pas le participant)')
    add('I5','Temps réseau',bool(s['rtt_ms']),latency,
        f"HTTP vers Cloudflare : {sorted(s['rtt_ms'])[len(s['rtt_ms'])//2]:.0f} ms (médiane). Ce n’est pas la latence de l’appel." if s['rtt_ms'] else 'Aucune mesure réseau récente.')
    tz=active and bool(v['declared_timezone'])
    if tz: c['declared_location']['utc_offset']=datetime.now(timezone.utc).astimezone(ZoneInfo(v['declared_timezone'])).utcoffset().total_seconds()/3600
    add('I2','Fuseau horaire',tz,checks.check_browser_timezone(c) if tz else None,
        f"Ordinateur : {v['browser_timezone']} · déclaré : {v['declared_timezone']}" if tz else 'Choisissez un fuseau déclaré pour comparer.')
    add('I6','Stabilité du flux',active,checks.check_video_settings(c),
        f"{v['settings_changes']:.0f} changement(s) de résolution ou de cadence déclarée." if active else 'En attente de la caméra.')
    add('C4','Caméra refusée',v['camera_refused'],checks.Signal('C4_CAMERA_REFUSED',5,'Refus de caméra déclaré manuellement. Signal faible ; une difficulté technique ou un choix personnel peut l’expliquer.') if v['camera_refused'] else None,
        'À renseigner manuellement ; une permission bloquée ne prouve pas un refus.')
    for code,title,key,fn in [('C10','Email jetable','email',checks.check_email),('C15','Forme de l’email','email',checks.check_email_pattern),('C12','Format du téléphone','phone',checks.check_phone_format),('C13','Plage VoIP','phone',checks.check_phone_virtual)]:
        add(code,title,bool(v[key]),fn(c) if v[key] else None,'Contrôle local sur un référentiel limité.' if v[key] else 'Coordonnée facultative non renseignée.')
    bonus=checks.combination_bonus(signals)  # Friend’s rule unchanged: 2 codes => 15, 3+ => 25.
    add('X1','Combinaison de signaux',bool(signals),bonus,'Bonus inchangé : +15 pour 2 signaux I1/I2/I3/I4/I5 ; +25 pour 3 ou plus.')
    return {'rows':rows,'points':min(100,sum(s.weight for s in signals)),
            'flag_count':sum(row['state']=='flag' and row['code']!='X1' for row in rows),
            'measured_count':sum(row['state']!='unavailable' and row['code']!='X1' for row in rows),
            'limit':'Points de règles exploratoires, pas une probabilité. Non combinés au score GenD PE.'}
