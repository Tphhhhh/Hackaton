"""Jeu d'évaluation « blind » : 2 × 160 dossiers synthétiques, séparés en dev et test.

    python -m metadata.data.blind.generate_blind --seed 2026

Écrit sans reprendre les seuils ni les listes de référence du détecteur : les profils de
fraude viennent des alertes publiques (FBI IC3, alerte conjointe US / Corée du Sud / Japon,
DOJ), les cas honnêtes sont choisis pour piéger un détecteur trop sensible (expatriés,
déménagements, freelances, pseudos, VPN d'entreprise…). Les noms sont tirés d'un même
réservoir mixte, indépendamment du statut fraude. Aucune donnée réelle.

Règle d'usage : on règle le détecteur sur dev uniquement, test se mesure une seule fois.
"""
from __future__ import annotations

import argparse
import json
import random
import string
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FIRST = ["Camille", "Lucas", "Emma", "Hugo", "Léa", "Jonas", "Lena", "Lukas", "Sofia", "Mateo", "Lucía",
         "Giulia", "Marco", "Ana", "João", "Inês", "Sven", "Ingrid", "Björn", "Aino", "Mikael", "Olga", "Piotr",
         "Agnieszka", "Tomasz", "Ivan", "Yusuf", "Fatima", "Amina", "Omar", "Karim", "Leila", "Mehdi", "Aïcha",
         "Chinedu", "Ngozi", "Kwame", "Ama", "Wei", "Mei", "Hiroshi", "Yuki", "Min-jun", "Ji-woo", "Arjun",
         "Priya", "Rahul", "Ananya", "Thanh", "Linh", "Diego", "Valentina", "Camila", "Santiago", "Noah",
         "Olivia", "James", "Grace", "Siobhan", "Ciarán", "Zoé", "Théo", "Jürgen", "Søren", "Åsa", "Ramón",
         "Nadia", "Elif", "Emre", "Daniel", "Sarah", "Alexander", "Christopher", "Margaux", "Jean-Baptiste"]
LAST = ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Lefèvre", "Schmidt", "Rossi", "Bianchi",
        "García", "Fernández", "Silva", "Santos", "Costa", "Johansson", "Lindqvist", "Virtanen", "Kowalski",
        "Nowak", "Ivanova", "Petrov", "Yılmaz", "Demir", "Haddad", "Benali", "Mansour", "Okafor", "Mensah",
        "Diallo", "Ndiaye", "Wang", "Li", "Zhang", "Chen", "Tanaka", "Sato", "Kim", "Park", "Nguyen", "Tran",
        "Patel", "Sharma", "Singh", "Rodríguez", "López", "O'Brien", "Murphy", "De Jong", "Bakker", "Fischer",
        "Weber", "Wagner", "Becker", "Hoffmann", "Ricci", "Romano", "Ferreira", "Almeida", "Novak", "Horvat"]
UMLAUT_LAST = ["Müller", "Schäfer", "Jäger", "Größ", "Bäcker", "Köhler", "Lindström", "Sørensen", "Åberg"]
COMPOUND_LAST = ["Van Dijk", "Van der Berg", "García-López", "Mendes-Ribeiro", "Le Gall", "Saint-Clair",
                 "El Amrani", "Al-Rashid", "De la Cruz", "Da Silva"]

# Pays de résidence : (code, villes, fuseau, décalage UTC en octobre, préfixe IBAN, longueur IBAN)
COUNTRIES = {
    "FR": (["Paris", "Lyon", "Lille", "Nantes", "Toulouse"], "Europe/Paris", 2, 27),
    "DE": (["Berlin", "Munich", "Hamburg", "Cologne"], "Europe/Berlin", 2, 22),
    "NL": (["Amsterdam", "Rotterdam", "Utrecht"], "Europe/Amsterdam", 2, 18),
    "BE": (["Brussels", "Ghent", "Liège"], "Europe/Brussels", 2, 16),
    "ES": (["Madrid", "Barcelona", "Valencia"], "Europe/Madrid", 2, 24),
    "PT": (["Lisbon", "Porto"], "Europe/Lisbon", 1, 25),
    "IT": (["Milan", "Rome", "Turin"], "Europe/Rome", 2, 27),
    "CH": (["Zurich", "Geneva", "Lausanne"], "Europe/Zurich", 2, 21),
    "UK": (["London", "Manchester", "Edinburgh"], "Europe/London", 1, 22),
    "IE": (["Dublin", "Cork"], "Europe/Dublin", 1, 22),
    "PL": (["Warsaw", "Kraków"], "Europe/Warsaw", 2, 28),
    "SE": (["Stockholm", "Gothenburg"], "Europe/Stockholm", 2, 24),
}
RES_WEIGHTS = {"FR": 30, "DE": 12, "NL": 8, "BE": 6, "ES": 8, "PT": 5, "IT": 6, "CH": 5, "UK": 10, "IE": 4,
               "PL": 4, "SE": 2}
IBAN_CC = {"UK": "GB"}

STREETS = {"FR": ["rue des Lilas", "avenue Jean Jaurès", "rue de la République", "boulevard Voltaire"],
           "DE": ["Hauptstraße", "Bahnhofstraße", "Schillerstraße"], "NL": ["Keizersgracht", "Prinsengracht"],
           "BE": ["Rue Royale", "Veldstraat"], "ES": ["Calle Mayor", "Gran Vía"], "PT": ["Rua Augusta", "Rua do Ouro"],
           "IT": ["Via Roma", "Corso Vittorio Emanuele"], "CH": ["Bahnhofstrasse", "Rue du Rhône"],
           "UK": ["High Street", "Station Road"], "IE": ["Grafton Street", "Main Street"],
           "PL": ["ulica Marszałkowska", "ulica Floriańska"], "SE": ["Drottninggatan", "Kungsgatan"]}

# Réexpéditeurs inventés. Les deux premiers reprennent des adresses de transitaires « connues »
# sous une autre graphie (comme le ferait un fraudeur qui recopie l'adresse à sa façon).
FORWARDERS = [
    "Hafenstraße 45 / Lager 9 / 20457 Hamburg / Germany",
    "12 Logistics Park Road, Unit 4, Newark NJ 07114, USA",
    "1180 Commerce Blvd, Unit 12, Linden, NJ 07036, US",
    "Zone Logistique Nord, Entrepôt 4, 93290 Tremblay-en-France, FR",
    "7 Freight Terminal Way, Bay 3, Dover, DE 19901, US",
    "Unit 5, Heathrow Cargo Centre, Hounslow TW6 3XA, UK",
    "Pakketpunt 22, Hal B, 1118 BG Schiphol, NL",
    "4410 Airport Rd, Suite 120, Charlotte, NC 28208, US",
]
PAYEE_WORDS = ["Northwind", "Brightline", "Harbor", "BlueRidge", "Atlas", "Crestview", "Ironwood", "Silverline",
               "Redfern", "Oakmont", "Summit", "Clearwater", "Granite", "Bayside", "Pinehurst", "Kingsway"]
PAYEE_KIND = ["Consulting LLC", "Services Ltd", "Staffing Inc", "Payroll LLC", "Outsourcing Ltd", "Trading Co"]


def third_party(rng) -> str:
    """Titulaire tiers : société écran ou particulier (chaque fraude indépendante a le sien)."""
    if rng.random() < 0.65:
        return f"{rng.choice(PAYEE_WORDS)} {rng.choice(PAYEE_WORDS)} {rng.choice(PAYEE_KIND)}"
    return f"{rng.choice(string.ascii_uppercase)}. {rng.choice(LAST)}"
COMPANIES = ["Northwind Labs", "Brightpath", "Kestrel Data", "Alder & Co", "Lumen Systems", "Tidewater",
             "Quanta Retail", "Helio Pay", "Corvid Security", "Basalt Cloud", "Fennel Health", "Marlin Bank",
             "Orbit Logistics", "Pinecone AI", "Saffron Media", "Vireo Mobility", "Juniper Insurance",
             "Granite Telecom", "Cobalt Games", "Meridian Energy"]
ROLES = ["Backend Engineer", "Senior Backend Engineer", "Data Engineer", "DevOps Engineer", "Site Reliability Engineer",
         "Full-Stack Developer", "Security Engineer", "Machine Learning Engineer", "Mobile Developer", "Platform Engineer"]
STACKS = [["Go", "PostgreSQL", "Kafka", "Kubernetes"], ["Python", "Django", "AWS", "Terraform"],
          ["Java", "Spring", "Oracle", "Jenkins"], ["TypeScript", "React", "Node.js", "GraphQL"],
          ["Scala", "Spark", "Airflow", "GCP"], ["Rust", "gRPC", "Redis", "Linux"], ["Kotlin", "Swift", "Firebase"]]
VERBS = ["Built", "Designed", "Maintained", "Migrated", "Led", "Scaled", "Automated", "Rewrote", "Owned", "Shipped"]
OBJECTS = ["the payment API", "a real-time pricing service", "the data platform", "CI/CD pipelines",
           "the authentication service", "an event-driven order system", "internal developer tooling",
           "the mobile backend", "a fraud scoring pipeline", "the observability stack", "customer data exports"]
OUTCOMES = ["cutting latency by 40%", "serving 2M requests a day", "with 99.95% uptime", "for 30 engineers",
            "reducing cloud costs by a third", "across 4 countries", "handling 10k events per second", ""]

REAL_CAMS = ["FaceTime HD Camera", "Integrated Webcam", "Logitech C920", "HP HD Camera", "Logitech Brio"]
REAL_MICS = ["MacBook Pro Microphone", "Microphone Array (Realtek Audio)", "Jabra Evolve2 65", "AirPods Pro"]
BENIGN_VIRTUAL = ["NVIDIA Broadcast", "Logi Capture", "Camo"]           # flou / fond virtuel légitimes
SUSPECT_CAMS = ["OBS Virtual Camera", "ManyCam Virtual Webcam", "XSplit VCam", "DeepFaceLive Cam"]
SUSPECT_MICS = ["VB-Audio Virtual Cable", "Voicemod Virtual Audio Device"]
REAL_GPUS = ["ANGLE (Apple, Apple M2, OpenGL 4.1)", "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)",
             "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11)",
             "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)"]
VM_GPUS = ["Google SwiftShader", "llvmpipe (LLVM 15.0.7, 256 bits)", "VMware SVGA 3D", "VirtualBox Graphics Adapter"]
# Fuseaux d'un opérateur distant : seule l'incohérence avec le fuseau déclaré est observable.
REMOTE = [("Asia/Shanghai", 8), ("Asia/Vladivostok", 10), ("Asia/Dubai", 4), ("Asia/Bangkok", 7),
          ("America/New_York", -4), ("Asia/Singapore", 8)]
REMOTE_IP = ["CN", "RU", "AE", "TH", "SG", "MY", "US", "HK"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "proton.me", "yahoo.com", "gmx.de", "icloud.com", "free.fr",
                 "orange.fr", "web.de", "tutanota.com", "hotmail.com"]
FAKE_DISPOSABLE = ["mailinator.com", "yopmail.com", "guerrillamail.com", "temp-mail.org"]


def strip(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def translit(s: str, rng) -> str:
    """Translittération d'un nom pour un email : « Müller » -> « mueller » ou « muller »."""
    low = s.lower()
    if rng.random() < 0.6:
        low = low.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "ø": "oe", "å": "aa"}))
    return "".join(ch for ch in strip(low) if ch.isalnum() or ch in "-")


def digits(rng, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


# --- Téléphones ----------------------------------------------------------------------------

def national(rng, cc: str) -> tuple[str, str]:
    """(indicatif, numéro national valide) pour un mobile du pays."""
    if cc == "FR": return "33", rng.choice("67") + digits(rng, 8)
    if cc == "UK": return "44", "7" + rng.choice("1234589") + digits(rng, 8)
    if cc == "DE": return "49", "1" + rng.choice(["51", "52", "57", "60", "62", "70", "76"]) + digits(rng, rng.choice([7, 8]))
    if cc == "NL": return "31", "6" + digits(rng, 8)
    if cc == "BE": return "32", "4" + rng.choice("789") + digits(rng, 7)
    if cc == "ES": return "34", rng.choice("67") + digits(rng, 8)
    if cc == "PT": return "351", "9" + rng.choice("1236") + digits(rng, 7)
    if cc == "IT": return "39", "3" + rng.choice("2345") + digits(rng, rng.choice([7, 8]))
    if cc == "CH": return "41", "7" + rng.choice("5689") + digits(rng, 7)
    if cc == "IE": return "353", "8" + rng.choice("35679") + digits(rng, 7)
    if cc == "PL": return "48", rng.choice("5678") + digits(rng, 8)
    if cc == "SE": return "46", "7" + rng.choice("0236") + digits(rng, 7)
    if cc == "US": return "1", rng.choice(["212", "415", "646", "302", "786"]) + rng.choice("23456789") + digits(rng, 6)
    raise KeyError(cc)


def fmt_phone(rng, cc: str, nsn: str) -> str:
    style = rng.random()
    if style < 0.45:
        groups = [nsn[i:i + 2] for i in range(1, len(nsn), 2)]
        return f"+{cc} {nsn[0]} {' '.join(groups)}"
    if style < 0.75:
        return f"+{cc}{nsn}"
    if style < 0.88:
        return f"00{cc} {nsn[:4]} {nsn[4:]}"
    return f"+{cc} (0){nsn[:4]} {nsn[4:]}"


def phone_for(rng, cc: str) -> str:
    c, n = national(rng, cc)
    return fmt_phone(rng, c, n)


def voip_phone(rng) -> str:
    kind = rng.choice(["uk56", "uk70", "de32", "nl85", "nl87", "es51"])
    if kind == "uk56": return fmt_phone(rng, "44", "56" + digits(rng, 8))
    if kind == "uk70": return fmt_phone(rng, "44", "70" + digits(rng, 8))
    if kind == "de32": return fmt_phone(rng, "49", "32" + digits(rng, rng.choice([8, 9])))
    if kind == "nl85": return fmt_phone(rng, "31", "85" + digits(rng, 7))
    if kind == "nl87": return fmt_phone(rng, "31", "87" + digits(rng, 7))
    return fmt_phone(rng, "34", "51" + digits(rng, 7))


def broken_phone(rng, cc: str) -> str:
    c, n = national(rng, cc)
    n = n[:-1] if rng.random() < 0.5 else n + rng.choice(string.digits)
    return fmt_phone(rng, c, n)


# --- IBAN ----------------------------------------------------------------------------------

def iban(rng, cc: str) -> str:
    country = IBAN_CC.get(cc, cc)
    length = COUNTRIES[cc][3] if cc in COUNTRIES else {"LT": 20, "GB": 22}.get(country, 22)
    if country == "GB":
        bban = rng.choice(["NWBK", "BARC", "MONZ", "REVO"]) + digits(rng, length - 8)
    else:
        bban = digits(rng, length - 4)
    rearranged = bban + country + "00"
    num = int("".join(str(int(ch, 36)) for ch in rearranged))
    check = 98 - num % 97
    raw = f"{country}{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


# --- CV ------------------------------------------------------------------------------------

def ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def experiences(rng, years: float, applied: date, overlap_months: int = 0, stack=None, template=None):
    """Postes successifs couvrant `years` ans jusqu'à la candidature."""
    stack = stack or rng.choice(STACKS)
    n = max(1, min(5, round(years / rng.uniform(1.8, 3.2))))
    total = int(years * 12)
    cuts = sorted(rng.sample(range(6, max(7, total - 5)), n - 1)) if n > 1 and total > 12 else []
    bounds = [0] + cuts + [total]
    start0 = applied - timedelta(days=30 * total)
    exps = []
    for i in range(n):
        s = start0 + timedelta(days=30 * bounds[i])
        e = start0 + timedelta(days=30 * bounds[i + 1])
        if overlap_months and i < n - 1:
            e = e + timedelta(days=30 * overlap_months)
        desc = template[i % len(template)] if template else (
            f"{rng.choice(VERBS)} {rng.choice(OBJECTS)} in {rng.choice(stack)} {rng.choice(OUTCOMES)}".strip() + ".")
        exps.append({"company": rng.choice(COMPANIES), "title": rng.choice(ROLES), "start": ym(s),
                     "end": None if i == n - 1 else ym(e), "description": desc})
    return exps, stack


def summary(rng, claimed: int | None, stack) -> str:
    lead = rng.choice([
        "Backend engineer", "Software engineer", "Ingénieur·e logiciel", "Data engineer", "Développeur backend",
        "Platform engineer"])
    if claimed is None:
        return f"{lead} passionné par {stack[0]} et {stack[1]}, à l'aise en équipe produit."
    return rng.choice([
        f"{lead} with {claimed} years of experience building systems in {stack[0]} and {stack[1]}.",
        f"{lead} avec {claimed} ans d'expérience sur {stack[0]}, {stack[1]} et le cloud.",
        f"{claimed}+ years shipping production services ({', '.join(stack[:3])}).",
        f"{lead} depuis {claimed} ans, spécialisé·e {stack[0]} et architecture distribuée.",
    ])


# --- Emails et profils ---------------------------------------------------------------------

def honest_email(rng, first: str, last: str, style: str = "") -> str:
    f, l = translit(first, rng).replace("-", ""), translit(last, rng).replace(" ", "").replace("'", "")
    if "-" in l and rng.random() < 0.5:
        l = l.split("-")[0]
    l = l.replace("-", "")
    style = style or rng.choice(["f.l", "f.l", "fl", "f.lNN", "iL", "l.f", "f_l", "flYYYY", "iLNN"])
    nn, yyyy = rng.randint(1, 99), rng.randint(1975, 2001)
    local = {"f.l": f"{f}.{l}", "fl": f"{f}{l}", "f.lNN": f"{f}.{l}{nn}", "iL": f"{f[0]}{l}", "l.f": f"{l}.{f}",
             "f_l": f"{f}_{l}", "flYYYY": f"{f}{l}{yyyy}", "iLNN": f"{f[0]}.{l}{nn}"}[style]
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"


NICKNAMES = ["darkfalcon", "pixelwizard", "nightowl", "bluecactus", "mrsmoothjazz", "quietstorm", "lemonade",
             "kitesurfer", "trailrunner", "vinylcat", "ramenlover", "moonbiker"]


def privacy_email(rng, first: str, last: str) -> str:
    r = rng.random()
    if r < 0.5:
        return f"{rng.choice(NICKNAMES)}{rng.choice(['', str(rng.randint(1, 99))])}@{rng.choice(['proton.me', 'tutanota.com', 'gmail.com'])}"
    if r < 0.75:
        f, l = translit(first, rng), translit(last, rng).replace(" ", "")
        return f"{f[0]}{l[0]}{rng.randint(1975, 2001)}@proton.me"
    return f"hello@{translit(first, rng)}{translit(last, rng).replace(' ', '')}.dev"


PERSONA_HANDLES = ["superdev", "blockchain.guru", "fullstackpro", "codemaster", "seniordev.expert", "techninja",
                   "cloudking", "webstar"]
OTHER_NAMES = ["michael.brown", "james.wilson", "david.smith", "kevin.lee", "ryan.miller", "jason.taylor"]


def suspicious_email(rng, first: str, last: str) -> str:
    kind = rng.choice(["random_digits", "consonants", "persona", "other_name", "mixed"])
    dom = rng.choice(["gmail.com", "outlook.com", "proton.me", "hotmail.com"])
    if kind == "random_digits":
        return f"{translit(first, rng)[0]}{translit(last, rng)[0]}{digits(rng, rng.randint(6, 9))}@{dom}"
    if kind == "consonants":
        return f"{''.join(rng.choice('bcdfghjklmnpqrstvwxz') for _ in range(rng.randint(5, 7)))}.{digits(rng, 2)}@{dom}"
    if kind == "persona":
        return f"{rng.choice(PERSONA_HANDLES)}{digits(rng, rng.randint(2, 4))}@{dom}"
    if kind == "other_name":
        return f"{rng.choice(OTHER_NAMES)}.dev{digits(rng, 2)}@{dom}"
    return "".join(rng.choice(string.ascii_lowercase) + rng.choice(string.digits) for _ in range(4)) + f"@{dom}"


def slug(rng, first: str, last: str) -> str:
    f, l = strip(first.lower()).replace(" ", "-"), strip(last.lower()).replace(" ", "-").replace("'", "")
    return rng.choice([f"{f}-{l}-{rng.randint(10, 999)}{rng.choice('abcdef')}", f"{f}-{l}", f"{f}{l}", f"{f[0]}{l}"])


def profiles(rng, first, last, applied: date, years: float, young=False, unrelated=False, github=None):
    created = applied - timedelta(days=rng.randint(20, 150)) if young else \
        applied - timedelta(days=int(365 * rng.uniform(max(1.0, years * 0.5), years + 3)))
    s = rng.choice(["senior-dev-expert", "top-engineer-" + digits(rng, 4), "cloud-architect-pro",
                    "fullstack-" + digits(rng, 3)]) if unrelated else slug(rng, first, last)
    out = [{"platform": "linkedin", "url": f"https://linkedin.example/in/{s}", "created_at": created.isoformat(),
            "connections": rng.randint(5, 70) if young else rng.randint(120, 950)}]
    if github if github is not None else rng.random() < 0.55:
        handle = rng.choice([slug(rng, first, last).split("-")[0] + digits(rng, 2), rng.choice(NICKNAMES), s])
        gh_created = created - timedelta(days=rng.randint(0, 900)) if not young else created
        out.append({"platform": "github", "url": f"https://github.example/{handle}", "created_at": gh_created.isoformat(),
                    "connections": rng.randint(0, 300)})
    return out


# --- Activité et entretien ---------------------------------------------------------------

def logins(rng, hired: date, offset: int, home: str, n: int, abroad_share=0.0, abroad=None, night_share=0.0,
           operator_offset=None, trip=False):
    events = []
    trip_days = set()
    if trip:
        start = rng.randint(3, 15)
        trip_days = set(range(start, start + rng.randint(2, 4)))
        abroad = abroad or rng.choice(["ES", "IT", "PT", "US", "MA", "GR"])
    for _ in range(n):
        day = rng.randint(0, 20)
        d = hired + timedelta(days=day)
        if operator_offset is not None:
            local_h = rng.randint(9, 18)                       # journée de travail de l'opérateur
            utc_h = (local_h - operator_offset) % 24
        elif rng.random() < night_share:
            utc_h = (rng.choice([22, 23, 0, 1, 2]) - offset) % 24
        else:
            utc_h = (rng.randint(8, 19) - offset) % 24
        ts = datetime(d.year, d.month, d.day, utc_h, rng.randint(0, 59), tzinfo=timezone.utc)
        if trip and day in trip_days:
            country = abroad
        elif abroad and rng.random() < abroad_share:
            country = abroad if isinstance(abroad, str) else rng.choice(abroad)
        else:
            country = home
        events.append({"ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "ip_country": country})
    return sorted(events, key=lambda e: e["ts"])


def session(rng, home: str, tz: str, offset: int, **kw):
    s = {"devices": {"video": [rng.choice(REAL_CAMS)], "audio": [rng.choice(REAL_MICS)]},
         "device_changed_during_call": False, "browser_timezone": tz, "browser_utc_offset": offset,
         "gpu_renderer": rng.choice(REAL_GPUS),
         "ip": {"country": home, "type": rng.choice(["residential", "residential", "mobile"]),
                "org": rng.choice(["Orange", "Free", "Deutsche Telekom", "Vodafone", "KPN", "Movistar", "BT", "Swisscom"])},
         "ip_changed_during_call": False, "rtt_ms": [rng.randint(12, 55) for _ in range(6)],
         "video_settings_changes": rng.choice([0, 0, 0, 1])}
    if kw.get("benign_virtual"):
        s["devices"]["video"] = [rng.choice(BENIGN_VIRTUAL)]
    if kw.get("corporate_vpn"):
        s["ip"] = {"country": rng.choice([home, "DE", "NL", "IE"]), "type": rng.choice(["corporate", "datacenter"]),
                   "org": rng.choice(["Zscaler", "Cisco AnyConnect", "Palo Alto GlobalProtect"])}
        s["rtt_ms"] = [rng.randint(30, 90) for _ in range(6)]
    if kw.get("remote"):
        tzname, off = rng.choice(REMOTE)
        sneaky = rng.random() < 0.4                     # opérateur soigneux : fuseau du navigateur maquillé
        if not sneaky:
            s["browser_timezone"], s["browser_utc_offset"] = tzname, off
        n_flags = rng.randint(2, 4)
        flags = rng.sample(["ip", "latency", "vm", "virtual_cam", "ip_change"], n_flags)
        if "ip" in flags:
            s["ip"] = {"country": rng.choice(REMOTE_IP + [home]), "type": "datacenter",
                       "org": rng.choice(["M247", "DigitalOcean", "Choopa", "OVH", "Hetzner"])}
        if "latency" in flags:
            s["rtt_ms"] = [rng.randint(160, 340) for _ in range(6)]
        if "vm" in flags:
            s["gpu_renderer"] = rng.choice(VM_GPUS)
        if "virtual_cam" in flags:
            s["devices"]["video"] = [rng.choice(SUSPECT_CAMS)]
            if rng.random() < 0.4:
                s["devices"]["audio"] = [rng.choice(SUSPECT_MICS)]
        if "ip_change" in flags:
            s["ip_changed_during_call"] = True
        s["video_settings_changes"] = rng.choice([0, 1, 3, 4])
    return s


# --- Construction d'un dossier ----------------------------------------------------------

HONEST_MIX = {"standard": 27, "expat_phone": 8, "moved_house": 6, "freelancer_overlap": 6, "career_changer": 5,
              "bootcamp_template": 6, "traveller": 7, "night_owl": 6, "privacy_email": 7, "new_linkedin": 5,
              "camera_refused_once": 4, "corporate_vpn": 5, "virtual_background": 4, "sepa_iban_abroad": 5,
              "holder_variant": 5, "umlaut_name": 4, "compound_surname": 6}
FRAUD_MIX = {"laptop_farm": 8, "payroll_mule": 7, "contact_identity": 7, "remote_proxy": 6, "subtle": 5}
RINGS = [("phone", 4), ("money", 4), ("text", 3)]      # persona_network : 11 dossiers


def pick_country(rng) -> str:
    return rng.choices(list(RES_WEIGHTS), weights=list(RES_WEIGHTS.values()))[0]


def base(rng, archetype: str, ring=None):
    """Dossier honnête de base, que les archétypes modifient ensuite."""
    first = rng.choice(FIRST)
    last = rng.choice(UMLAUT_LAST if archetype == "umlaut_name" else COMPOUND_LAST if archetype == "compound_surname" else LAST)
    home = pick_country(rng)
    cities, tz, offset, _ = COUNTRIES[home]
    city = rng.choice(cities)
    applied = date(2026, 3, 1) + timedelta(days=rng.randint(0, 200))
    years = rng.uniform(1.5, 4) if archetype == "career_changer" else rng.uniform(3, 14)
    exps, stack = experiences(rng, years, applied)
    listed = years
    claimed = rng.choice([None, round(listed), round(listed), max(1, round(listed) + rng.choice([-1, 1]))])
    hired = applied + timedelta(days=rng.randint(18, 45)) if rng.random() < 0.78 else None
    residence = f"{rng.randint(1, 120)} {rng.choice(STREETS[home])}, {city}, {home}"
    c = {
        "id": "", "applied_at": applied.isoformat(), "hired_at": hired.isoformat() if hired else None,
        "full_name": f"{first} {last}",
        "email": honest_email(rng, first, last),
        "phone": phone_for(rng, home),
        "declared_location": {"city": city, "country": home, "timezone": tz, "utc_offset": offset},
        "cv": {"summary": summary(rng, claimed, stack), "years_experience": claimed or round(listed),
               "experiences": exps,
               "education": [{"school": rng.choice(["Université de Lyon", "TU München", "Politecnico di Milano",
                                                    "University of Leeds", "Universidade do Porto", "EPFL", "KTH",
                                                    "Le Wagon", "Ironhack", "Open University"]),
                              "degree": rng.choice(["MSc Computer Science", "BSc Software Engineering",
                                                    "Licence Informatique", "Bootcamp Web Development", "MEng"]),
                              "year": applied.year - int(years) - rng.randint(0, 2)}],
               "skills": stack},
        "profiles": profiles(rng, first, last, applied, years),
        "interview": {"camera_refused": False},
        "payment": {"method": "iban", "account": iban(rng, home), "holder": f"{first} {last}"} if hired
        else {"method": "iban", "account": "", "holder": ""},
        "shipping_addresses": [{"from": hired.isoformat(), "address": residence}] if hired else [],
        "activity": logins(rng, hired, offset, home, rng.randint(20, 60)) if hired else [],
    }
    if rng.random() < 0.6:
        c["interview_session"] = session(rng, home, tz, offset)
    c["_ctx"] = {"first": first, "last": last, "home": home, "tz": tz, "offset": offset, "applied": applied,
                 "hired": hired, "years": years, "stack": stack, "city": city}
    return c


def make_honest(rng, archetype: str, template=None):
    c = base(rng, archetype)
    x = c["_ctx"]
    notes = ""
    if archetype == "expat_phone":
        origin = rng.choice([k for k in COUNTRIES if k != x["home"]] + ["US"])
        c["phone"] = phone_for(rng, origin)
        notes = f"garde son numéro de {origin} après son installation"
    elif archetype == "moved_house" and x["hired"]:
        new = f"{rng.randint(1, 120)} {rng.choice(STREETS[x['home']])}, {x['city']}, {x['home']}"
        c["shipping_addresses"].append({"from": (x["hired"] + timedelta(days=rng.randint(5, 25))).isoformat(),
                                        "address": new})
        notes = "déménage juste après l'embauche"
    elif archetype == "freelancer_overlap":
        c["cv"]["experiences"], _ = experiences(rng, x["years"], x["applied"], overlap_months=rng.randint(2, 5),
                                                stack=x["stack"])
        notes = "missions freelance qui se chevauchent de quelques mois"
    elif archetype == "bootcamp_template":
        c["cv"]["experiences"], _ = experiences(rng, x["years"], x["applied"], stack=x["stack"], template=template)
        c["cv"]["summary"] = "Graduate of a full-stack bootcamp, passionate about clean code, testing and agile teams."
        notes = "CV écrit sur le modèle du bootcamp (texte commun à d'autres anciens)"
    elif archetype == "traveller" and x["hired"]:
        c["activity"] = logins(rng, x["hired"], x["offset"], x["home"], rng.randint(25, 60), trip=True)
        notes = "quelques jours de voyage après l'embauche"
    elif archetype == "night_owl" and x["hired"]:
        c["activity"] = logins(rng, x["hired"], x["offset"], x["home"], rng.randint(25, 60),
                               night_share=rng.uniform(0.12, 0.3))
        notes = "travaille parfois tard le soir"
    elif archetype == "privacy_email":
        c["email"] = privacy_email(rng, x["first"], x["last"])
        notes = "email pseudonyme ou à initiales, par souci de vie privée"
    elif archetype == "new_linkedin":
        c["profiles"] = profiles(rng, x["first"], x["last"], x["applied"], x["years"], young=True, github=True)
        notes = "a créé son LinkedIn récemment malgré une longue carrière"
    elif archetype == "camera_refused_once":
        c["interview"]["camera_refused"] = True
        notes = "caméra coupée pour cause de connexion faible"
    elif archetype == "corporate_vpn":
        c["interview_session"] = session(rng, x["home"], x["tz"], x["offset"], corporate_vpn=True)
        notes = "entretien passé depuis le VPN de son employeur actuel"
    elif archetype == "virtual_background":
        c["interview_session"] = session(rng, x["home"], x["tz"], x["offset"], benign_virtual=True)
        notes = "flou d'arrière-plan (logiciel de la carte graphique ou de la webcam)"
    elif archetype == "sepa_iban_abroad" and x["hired"]:
        bank = rng.choice(["LT", "BE", "DE"])
        c["payment"]["account"] = iban(rng, bank)
        notes = f"banque en ligne avec un IBAN {bank}, à son nom"
    elif archetype == "holder_variant" and x["hired"]:
        c["payment"]["holder"] = rng.choice([f"{x['first'][0]}. {x['last']}", f"{x['first']} A. {x['last']}",
                                             f"{x['last'].upper()} {x['first']}", f"M. {x['first']} {x['last']}"])
        notes = "titulaire du compte écrit avec une initiale ou un second prénom"
    elif archetype in ("umlaut_name", "compound_surname"):
        notes = "nom avec accents ou composé, email translittéré"
    # Bruit honnête : lignes fixes de box, fuseau mal réglé d'une heure, etc.
    if x["home"] == "FR" and rng.random() < 0.08:
        c["phone"] = fmt_phone(rng, "33", "9" + digits(rng, 8))
    return c, {"is_fraud": False, "network": None, "archetype": archetype, "notes": notes}


POST_HIRE = {"forwarder", "third_party", "crypto", "remote_activity"}


def apply_red_flags(rng, c, flags: list[str]) -> list[str]:
    """Applique les signaux ; ceux qui supposent une embauche sont ignorés sinon. Renvoie ceux appliqués."""
    x = c["_ctx"]
    hired = x["hired"]
    flags = sorted(flags, key=lambda f: f == "unrelated_slug")     # le profil final est celui-ci
    for f in flags:
        if f == "forwarder" and hired:
            fw = rng.choice(FORWARDERS)
            if rng.random() < 0.5:
                c["shipping_addresses"] = [{"from": hired.isoformat(), "address": fw}]
            else:
                c["shipping_addresses"].append({"from": (hired + timedelta(days=rng.randint(0, 12))).isoformat(),
                                                "address": fw})
        elif f == "third_party" and hired:
            c["payment"] = {"method": rng.choice(["iban", "iban", "wise", "payoneer"]),
                            "account": iban(rng, rng.choice(["UK", "NL", "DE"])), "holder": third_party(rng)}
        elif f == "crypto" and hired:
            c["payment"] = {"method": "crypto", "account": "T" + "".join(rng.choice(string.ascii_letters + string.digits)
                                                                          for _ in range(33)), "holder": ""}
        elif f == "voip":
            c["phone"] = voip_phone(rng)
        elif f == "foreign_phone":
            c["phone"] = phone_for(rng, rng.choice(["US", "UK", "PL", "NL"]))
        elif f == "broken_phone":
            c["phone"] = broken_phone(rng, x["home"])
        elif f == "odd_email":
            c["email"] = suspicious_email(rng, x["first"], x["last"])
        elif f == "disposable":
            c["email"] = c["email"].split("@")[0] + "@" + rng.choice(FAKE_DISPOSABLE)
        elif f == "young_profile":
            c["profiles"] = profiles(rng, x["first"], x["last"], x["applied"], x["years"], young=True)
        elif f == "unrelated_slug":
            c["profiles"] = profiles(rng, x["first"], x["last"], x["applied"], x["years"],
                                     young="young_profile" in flags or rng.random() < 0.6, unrelated=True)
        elif f == "overlap":
            c["cv"]["experiences"], _ = experiences(rng, x["years"], x["applied"], overlap_months=rng.randint(8, 20),
                                                    stack=x["stack"])
        elif f == "inflated":
            claim = round(x["years"]) + rng.randint(3, 6)
            c["cv"]["summary"] = summary(rng, claim, x["stack"])
            c["cv"]["years_experience"] = claim
        elif f == "camera_refused":
            c["interview"]["camera_refused"] = True
        elif f == "remote_session":
            c["interview_session"] = session(rng, x["home"], x["tz"], x["offset"], remote=True)
        elif f == "remote_activity" and hired:
            tzname, off = rng.choice(REMOTE)
            c["activity"] = logins(rng, hired, x["offset"], x["home"], rng.randint(25, 60),
                                   abroad_share=rng.uniform(0.3, 0.9), abroad=rng.sample(REMOTE_IP, 2),
                                   operator_offset=off if rng.random() < 0.7 else None)
    return [f for f in flags if hired or f not in POST_HIRE]


FRAUD_FLAGS = {
    "laptop_farm": (["forwarder"], ["young_profile", "foreign_phone", "voip", "odd_email", "inflated", "remote_activity",
                                    "camera_refused", "third_party"]),
    "payroll_mule": (["third_party", "crypto"], ["forwarder", "young_profile", "odd_email", "overlap", "foreign_phone",
                                                 "remote_session"]),
    "contact_identity": (["voip", "odd_email", "unrelated_slug", "broken_phone", "disposable"],
                         ["young_profile", "inflated", "forwarder", "remote_session"]),
    "remote_proxy": (["remote_session", "remote_activity"], ["camera_refused", "foreign_phone", "young_profile",
                                                             "overlap", "odd_email"]),
}
SUBTLE = ["voip", "young_profile", "odd_email", "foreign_phone", "forwarder", "inflated", "camera_refused"]


def make_fraud(rng, archetype: str):
    c = base(rng, archetype)
    if c["hired_at"] is None and rng.random() < 0.7:       # la plupart des fraudes vont jusqu'à l'embauche
        hired = c["_ctx"]["applied"] + timedelta(days=rng.randint(18, 40))
        c["_ctx"]["hired"] = hired
        c["hired_at"] = hired.isoformat()
        x = c["_ctx"]
        c["payment"] = {"method": "iban", "account": iban(rng, x["home"]), "holder": c["full_name"]}
        c["shipping_addresses"] = [{"from": hired.isoformat(),
                                    "address": f"{rng.randint(1, 120)} {rng.choice(STREETS[x['home']])}, {x['city']}, {x['home']}"}]
        c["activity"] = logins(rng, hired, x["offset"], x["home"], rng.randint(20, 60))
    if archetype == "subtle":
        flags = [rng.choice(SUBTLE)]
    else:
        core, extra = FRAUD_FLAGS[archetype]
        flags = rng.sample(core, rng.randint(1, min(2, len(core)))) + rng.sample(extra, rng.randint(1, 2))
    applied = apply_red_flags(rng, c, flags)
    notes = "signaux : " + (", ".join(applied) or "aucun observable (pas encore embauché)")
    return c, {"is_fraud": True, "network": None, "archetype": archetype, "notes": notes}


# Chaque réseau a son propre CV « source », reformulé d'une persona à l'autre.
PARAPHRASE_SETS = [
    [["Built and scaled the payment API in Go, handling 10k events per second.",
      "Designed and grew the payments API (Go), processing about 10,000 events each second.",
      "Payments API owner: Go service, scaled to ten thousand events per second.",
      "Developed the payment interface in Golang and scaled it to 10k events/s."],
     ["Migrated legacy services to Kubernetes and Terraform, cutting cloud costs by a third.",
      "Moved old services onto Kubernetes with Terraform, reducing the cloud bill by roughly 33%.",
      "Led the migration of legacy apps to Kubernetes/Terraform; cloud spend down one third.",
      "Ported legacy workloads to k8s using Terraform and lowered cloud costs by a third."]],
    [["Maintained a React Native app used by 400k riders, shipping weekly releases.",
      "Owned the React Native mobile app (400,000 users) with a release every week.",
      "Weekly releases of the rider app in React Native, 400k monthly users.",
      "Delivered new features every week on a React Native app with four hundred thousand riders."],
     ["Introduced end-to-end tests with Detox and halved crash rates.",
      "Set up Detox E2E testing, which cut the crash rate by 50%.",
      "Crash rate divided by two after rolling out Detox end-to-end tests.",
      "Added automated end-to-end testing (Detox); crashes dropped by half."]],
    [["Designed Spark pipelines ingesting 3 TB of clickstream data per day on GCP.",
      "Built daily Spark jobs on Google Cloud processing three terabytes of clickstream.",
      "Clickstream ingestion with Spark on GCP, about 3TB a day.",
      "Engineered GCP Spark pipelines for 3 terabytes of daily click data."],
     ["Orchestrated 200 Airflow DAGs and set up data quality alerts for analysts.",
      "Ran two hundred Airflow DAGs and added data-quality alerting for the analytics team.",
      "Airflow orchestration (200 DAGs) plus data quality monitoring for analysts.",
      "Managed about 200 DAGs in Airflow with automated quality checks for analysts."]],
    [["Hardened AWS accounts with SCPs and GuardDuty for a fintech handling card data.",
      "Secured the AWS estate of a card-payments fintech using SCPs and GuardDuty.",
      "AWS security for a fintech (card data): service control policies, GuardDuty.",
      "Locked down AWS for a payments start-up processing card data (SCP, GuardDuty)."],
     ["Ran quarterly penetration tests and fixed 120 findings with product teams.",
      "Coordinated pentests every quarter and remediated 120 issues alongside the product teams.",
      "Quarterly pentesting, 120 vulnerabilities closed together with product squads.",
      "Organised penetration tests each quarter and drove fixes for 120 findings."]],
]


def make_ring(rng, kind: str, size: int, ring_id: str, texts):
    out = []
    shared_phone = national(rng, rng.choice(["UK", "US", "NL"]))
    shared_iban = iban(rng, rng.choice(["UK", "NL", "DE"]))
    shared_wallet = "T" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(33))
    shared_fw = rng.choice(FORWARDERS)
    ring_payee = third_party(rng)
    stack = rng.choice(STACKS)
    ring_seed, anchor = rng.randint(0, 10**6), date(2026, 3, 1) + timedelta(days=rng.randint(0, 150))
    for k in range(size):
        c, lab = make_fraud(rng, "laptop_farm" if rng.random() < 0.5 else "payroll_mule")
        x = c["_ctx"]
        if not c["hired_at"]:
            hired = x["applied"] + timedelta(days=rng.randint(18, 40))
            x["hired"] = hired
            c["hired_at"] = hired.isoformat()
            c["payment"] = {"method": "iban", "account": iban(rng, x["home"]), "holder": c["full_name"]}
            c["shipping_addresses"] = [{"from": hired.isoformat(), "address": shared_fw}]
            c["activity"] = logins(rng, hired, x["offset"], x["home"], rng.randint(20, 60))
        # CV paraphrasé : mêmes postes, mêmes dates, autre formulation.
        exps, _ = experiences(random.Random(ring_seed), 7, anchor, stack=stack)
        for i, e in enumerate(exps):
            e["description"] = texts[i % len(texts)][k % 4]
        c["cv"]["experiences"] = exps
        c["cv"]["summary"] = summary(rng, rng.choice([7, 8, 9]), stack)
        c["cv"]["skills"] = stack
        if kind == "phone":
            c["phone"] = fmt_phone(rng, *shared_phone)
        elif kind == "money":
            if rng.random() < 0.6:
                c["payment"] = {"method": "iban", "account": shared_iban.replace(" ", "") if k % 2 else shared_iban,
                                "holder": ring_payee}
            else:
                c["payment"] = {"method": "crypto", "account": shared_wallet, "holder": ""}
            if rng.random() < 0.5:
                c["shipping_addresses"].append({"from": c["hired_at"], "address": shared_fw})
        lab.update({"network": ring_id, "archetype": "persona_network",
                    "notes": f"réseau {ring_id} ({kind}) ; " + lab["notes"]})
        out.append((c, lab))
    return out


def generate_split(seed: int, prefix: str):
    rng = random.Random(seed)
    rows = []
    templates = [[f"{rng.choice(VERBS)} {rng.choice(OBJECTS)} during the bootcamp final project.",
                  "Built a full-stack web app with React and Node.js in an agile team of four.",
                  "Wrote unit and integration tests, code reviews and CI with GitHub Actions."] for _ in range(3)]
    for arch, n in HONEST_MIX.items():
        for i in range(n):
            tpl = templates[i // 2 % 3] if arch == "bootcamp_template" else None
            rows.append(make_honest(rng, arch, tpl))
    for arch, n in FRAUD_MIX.items():
        for _ in range(n):
            rows.append(make_fraud(rng, arch))
    sets = rng.sample(PARAPHRASE_SETS, len(RINGS))
    for r, (kind, size) in enumerate(RINGS):
        rows += make_ring(rng, kind, size, f"NET-{r + 1}", sets[r])
    rng.shuffle(rows)
    # Une URL de profil ou une adresse email désigne un seul compte : deux personnes distinctes
    # ne peuvent pas avoir la même. Les doublons nés du tirage au sort reçoivent un suffixe.
    seen_urls, seen_emails = set(), set()
    for c, _ in rows:
        for pr in c["profiles"]:
            while pr["url"] in seen_urls:
                pr["url"] += digits(rng, 1)
            seen_urls.add(pr["url"])
        while c["email"] in seen_emails:
            local, dom = c["email"].split("@")
            c["email"] = f"{local}{digits(rng, 1)}@{dom}"
        seen_emails.add(c["email"])
    candidates, labels = [], {}
    for i, (c, lab) in enumerate(rows, 1):
        c["id"] = f"{prefix}{i:03d}"
        c.pop("_ctx", None)
        candidates.append(c)
        labels[c["id"]] = lab
    return candidates, labels


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args()
    root = Path(__file__).resolve().parent
    for split, seed, prefix in (("dev", args.seed, "B-D"), ("test", args.seed + 7919, "B-T")):
        cands, labels = generate_split(seed, prefix)
        (root / split).mkdir(exist_ok=True)
        (root / split / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
        (root / split / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{split}: {len(cands)} dossiers, {sum(v['is_fraud'] for v in labels.values())} frauduleux")


if __name__ == "__main__":
    main()
