"""Génère un jeu de dossiers synthétiques : légitimes, frauduleux et réseaux de personas.

    python -m metadata.data.generate --out metadata/data/synthetic --seed 42

Écrit candidates.json (ce que voit le pipeline) et labels.json (vérité terrain,
lue uniquement par evaluate.py).

Les fraudes s'inspirent des signaux publiés par le FBI sur les faux informaticiens
à distance : refus de caméra, matériel envoyé chez un transitaire ou adresse qui
change juste après l'embauche, connexions depuis plusieurs pays, paiement en crypto,
coordonnées recyclées entre identités.

Attention : si l'équipe qui écrit les détecteurs écrit aussi les fraudes, les
résultats sont circulaires. Ce générateur sert au développement ; le jeu
d'évaluation final doit être produit à l'aveugle par un coéquipier.

Les noms sont tirés au hasard, indépendamment du statut fraude/légitime.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FIRST_NAMES = [
    "Camille", "Lucas", "Inès", "Thomas", "Sofia", "Jonas", "Lea", "Mateo", "Nora", "Hugo",
    "Amira", "Elias", "Julia", "Noah", "Chloé", "Karim", "Anna", "Leo", "Maya", "Paul",
    "Sara", "Adam", "Emma", "Yann", "Lina", "Ruben", "Zoé", "David", "Alice", "Omar",
    "Clara", "Nils", "Eva", "Tiago", "Ines", "Felix", "Rosa", "Malik", "Laura", "Victor",
]
LAST_NAMES = [
    "Martin", "Schmidt", "Silva", "Dubois", "Rossi", "Müller", "Garcia", "Bernard", "Weber",
    "Costa", "Lefèvre", "Fischer", "Santos", "Moreau", "Keller", "Ferreira", "Laurent", "Meyer",
    "Lopez", "Girard", "Wagner", "Almeida", "Roux", "Becker", "Fontaine", "Hoffmann", "Pereira",
    "Benali", "Novak", "Jansen", "Van Dijk", "Kowalski", "Haddad", "Andersen", "Moretti",
]
# Décalage UTC en octobre (heure d'été), pour éviter une dépendance à tzdata sous Windows.
LOCATIONS = [
    ("Paris", "FR", "Europe/Paris", 2), ("Lyon", "FR", "Europe/Paris", 2),
    ("Berlin", "DE", "Europe/Berlin", 2), ("Munich", "DE", "Europe/Berlin", 2),
    ("Zurich", "CH", "Europe/Zurich", 2), ("Geneva", "CH", "Europe/Zurich", 2),
    ("Lisbon", "PT", "Europe/Lisbon", 1), ("London", "UK", "Europe/London", 1),
    ("Madrid", "ES", "Europe/Madrid", 2), ("Amsterdam", "NL", "Europe/Amsterdam", 2),
]
PHONE_PREFIX = {"FR": "+33 6", "DE": "+49 15", "CH": "+41 7", "PT": "+351 9", "UK": "+44 7",
                "ES": "+34 6", "NL": "+31 6"}
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "proton.me", "yahoo.com", "gmx.de", "icloud.com"]
DISPOSABLE = ["tempmail.dev", "throwmail.io", "mailinator.com"]
FORWARDERS = json.loads(
    (Path(__file__).resolve().parent.parent / "reference" / "freight_forwarders.json").read_text(encoding="utf-8")
)["addresses"]
STREETS = ["rue des Lilas", "Hauptstrasse", "Rua Augusta", "High Street", "Calle Mayor",
           "Keizersgracht", "avenue Jean Jaurès", "Bahnhofstrasse", "Gran Vía", "Rua do Ouro"]
# Pays de connexion "autres" : seule l'incohérence avec le lieu déclaré compte, pas le pays lui-même.
OTHER_COUNTRIES = ["US", "CN", "RU", "AE", "SG", "TR", "MY", "TH", "BR", "KR"]

ROLES = ["Backend Engineer", "Full-Stack Developer", "DevOps Engineer", "Data Engineer",
         "Mobile Developer", "Frontend Engineer", "Site Reliability Engineer", "ML Engineer"]
COMPANIES = ["Nexora", "Bluepeak Labs", "Quantix", "Ardent Systems", "Veltio", "Kairo Tech",
             "Lumenwave", "Orbis Data", "Stratum IO", "Helixa", "Cobalt Forge", "Pivotal Nest",
             "Brightloop", "Sentra", "Mosaic Cloud", "Tidal Apps", "Northwind Digital", "Fyra"]
SCHOOLS = ["EPITA", "TU München", "EPFL", "Universidade de Lisboa", "Imperial College",
           "UPM Madrid", "TU Delft", "INSA Lyon", "KTH", "Politecnico di Milano"]
STACKS = [["Python", "Django", "PostgreSQL"], ["Go", "Kubernetes", "gRPC"], ["TypeScript", "React", "Node.js"],
          ["Java", "Spring", "Kafka"], ["Kotlin", "Android", "Firebase"], ["Rust", "Tokio", "Redis"],
          ["Scala", "Spark", "Airflow"], ["Terraform", "AWS", "Ansible"], ["Swift", "iOS", "Combine"],
          ["C#", ".NET", "Azure"], ["Elixir", "Phoenix", "PostgreSQL"], ["PyTorch", "MLflow", "Docker"]]
SUMMARY_OPENERS = [
    "Engineer who enjoys turning messy requirements into reliable services.",
    "I build products end to end and care a lot about maintainability.",
    "Pragmatic developer, happiest when shipping small increments.",
    "Background in physics, moved to software after a research internship.",
    "Former consultant who now prefers owning a product long term.",
    "I like observability, clear on-call runbooks and boring infrastructure.",
    "Curious generalist with a soft spot for developer tooling.",
    "Data-minded engineer who started as an analyst.",
    "Self-taught developer, open-source contributor on weekends.",
    "Team lead at heart, I mentor juniors and run design reviews.",
]
SUMMARY_MIDDLES = [
    "Recently migrated a monolith to services without downtime.",
    "Led the rewrite of a billing pipeline handling millions of events.",
    "Cut cloud costs by a third through right-sizing and caching.",
    "Built an internal platform used by forty engineers.",
    "Shipped a mobile app from zero to fifty thousand users.",
    "Introduced contract testing and halved integration bugs.",
    "Designed the data model of a marketplace from scratch.",
    "Ran the incident review process for two years.",
    "Automated release management across twelve repositories.",
    "Prototyped an ML ranking model that went to production.",
]
SUMMARY_CLOSERS = [
    "Looking for a remote-friendly team with a strong writing culture.",
    "Interested in climate, health or fintech products.",
    "Would love a role mixing hands-on work and mentoring.",
    "Keen to work on hard reliability problems.",
    "Searching for a product company rather than an agency.",
    "Happy to travel to the office once a month.",
]
DESC_TEMPLATES = [
    "Worked on {a} services in {s0} and {s1}; owned deployment with {s2}.",
    "Maintained {a} features, reviewed code and improved test coverage using {s0}.",
    "Built {a} APIs in {s0} backed by {s2}; on-call rotation member.",
    "Delivered {a} tooling with {s1} and {s0}, partnering with product managers.",
    "Scaled {a} workloads on {s2}, wrote design docs and runbooks.",
]
AREAS = ["payments", "search", "onboarding", "analytics", "notifications", "inventory",
         "authentication", "reporting", "pricing", "logistics", "messaging", "catalog"]

# Réseaux : un même opérateur réécrit son CV d'une identité à l'autre. Chaque membre
# reçoit une paraphrase différente : un contrôle par copier-coller ne suffit plus.
NETWORK_CV = [
    {
        "summaries": [
            "Senior full-stack engineer with 9 years delivering scalable web platforms for international "
            "clients. Expert in React, Node.js and cloud-native architectures. Available immediately "
            "for long-term remote contracts.",
            "Full-stack developer (9+ years) building large web platforms for clients worldwide. Deep "
            "expertise in React, Node.js and cloud-native design. Can start right away on a long remote contract.",
            "Experienced full-stack engineer: nearly a decade of scalable web products for global customers, "
            "specialised in React and Node.js on cloud-native stacks. Immediately available, remote only.",
        ],
        "descs": [
            "Developed scalable web platform features in React and Node.js for international clients; "
            "deployed cloud-native microservices on AWS.",
            "Built web platform modules with React and Node.js for clients abroad and shipped microservices to AWS.",
            "Delivered React/Node.js features for global customers and ran cloud-native services on AWS.",
        ],
        "stack": ["React", "Node.js", "AWS"],
    },
    {
        "summaries": [
            "Blockchain and backend developer with 8 years of experience building secure smart contracts "
            "and high-performance APIs. Strong in Solidity, Go and PostgreSQL. Open to remote "
            "freelance missions worldwide.",
            "Backend and blockchain engineer, 8 years writing audited smart contracts and fast APIs. "
            "Solidity, Go, PostgreSQL. Available for remote freelance work in any time zone.",
            "Eight years as a backend/Web3 developer: secure Solidity contracts, high-throughput Go services, "
            "PostgreSQL. Looking for fully remote freelance projects.",
        ],
        "descs": [
            "Built secure smart contracts in Solidity and high-performance Go APIs with PostgreSQL for DeFi startups.",
            "Wrote audited Solidity contracts and fast Go backends on PostgreSQL for decentralised finance clients.",
            "Implemented DeFi smart contracts in Solidity and Go services backed by PostgreSQL.",
        ],
        "stack": ["Solidity", "Go", "PostgreSQL"],
    },
    {
        "summaries": [
            "Mobile engineer with 7 years of experience shipping iOS and Android apps used by millions. "
            "Flutter and Kotlin specialist, comfortable with CI/CD and app store releases. Seeking "
            "full-time remote position.",
            "Seven years building iOS and Android applications with millions of users. Flutter and Kotlin "
            "expert, handles CI/CD and store publishing. Looking for a full-time remote role.",
        ],
        "descs": [
            "Shipped Flutter and Kotlin mobile apps used by millions; set up CI/CD and store releases.",
            "Released Flutter/Kotlin apps to millions of users and automated build pipelines and store submissions.",
        ],
        "stack": ["Flutter", "Kotlin", "Firebase"],
    },
    {
        "summaries": [
            "DevOps and cloud engineer, 6 years automating infrastructure with Terraform and Kubernetes on AWS "
            "and GCP. Security-minded, certified, available for remote contracts.",
            "Cloud/DevOps specialist with six years of Terraform, Kubernetes and multi-cloud automation (AWS, "
            "GCP). Strong security focus, open to remote contract work.",
        ],
        "descs": [
            "Automated AWS and GCP infrastructure with Terraform and managed Kubernetes clusters.",
            "Managed Kubernetes and wrote Terraform modules for multi-cloud environments on AWS and GCP.",
        ],
        "stack": ["Terraform", "Kubernetes", "AWS"],
    },
]
# Faux positif réaliste : deux légitimes sortis du même bootcamp, avec le même modèle de CV.
BOOTCAMP_CV = {
    "summary": "Junior web developer trained at Le Wagon after a first career in marketing. Built a full "
               "marketplace in a team of four during the bootcamp. Eager to learn, looking for a first role.",
    "desc": "Final bootcamp project: marketplace in Ruby on Rails with Stimulus and PostgreSQL, team of four.",
    "stack": ["Ruby on Rails", "Stimulus", "PostgreSQL"],
}
SYNONYMS = {"scalable": "highly scalable", "Expert": "Specialist", "Strong": "Skilled",
            "Available immediately": "Immediately available", "secure": "audited",
            "Seeking": "Looking for", "comfortable": "experienced", "millions": "several million users"}

FRAUD_SIGNALS = ["timeline_overlap", "young_profile", "camera_refused", "forwarder",
                 "address_change_after_hire", "multi_country_logins", "night_activity",
                 "crypto_payment", "disposable_email"]
# Bruit réaliste chez les légitimes : un seul signal faible, explicable.
LEGIT_NOISE = ["camera_refused", "young_profile", "moved_house", "one_trip_abroad",
               "late_worker"]


def _ym(d: date) -> str:
    return d.strftime("%Y-%m")


def _vary(text: str, rng: random.Random) -> str:
    for src, dst in SYNONYMS.items():
        if src in text and rng.random() < 0.5:
            text = text.replace(src, dst, 1)
    return text


def _experiences(rng, years, stack, overlap=False, network_desc=None):
    exps, end = [], date(2026, 8, 1)
    remaining = years * 12
    while remaining > 0:
        length = min(remaining, rng.randint(14, 40))
        start = end - timedelta(days=30 * length)
        if network_desc:
            desc = _vary(network_desc, rng)
        else:
            desc = rng.choice(DESC_TEMPLATES).format(a=rng.choice(AREAS), s0=stack[0], s1=stack[1], s2=stack[2])
        exps.append({"company": rng.choice(COMPANIES), "title": rng.choice(ROLES),
                     "start": _ym(start), "end": _ym(end) if exps else None, "description": desc})
        end = start - timedelta(days=rng.randint(0, 90))
        remaining -= length
    if overlap and len(exps) >= 2:
        # Deux postes à temps plein qui se chevauchent sur plus d'un an.
        exps[1]["end"] = _ym(date.fromisoformat(exps[0]["start"] + "-01") + timedelta(days=430))
    return exps


def _logins(rng, hired, utc_offset, home, mode, days=21):
    events = []
    for day in range(days):
        d = datetime.combine(hired + timedelta(days=day), datetime.min.time(), tzinfo=timezone.utc)
        if d.weekday() >= 5:
            continue
        for _ in range(rng.randint(2, 4)):
            if mode in ("night", "night_multi"):
                local_hour = rng.choice([0, 1, 2, 3, 4, 5, 23])  # journée de travail ~UTC+9
            elif mode == "late":
                local_hour = rng.choice([10, 14, 18, 21, 22, 23])
            else:
                local_hour = rng.randint(8, 18)
            ts = d + timedelta(hours=local_hour - utc_offset, minutes=rng.randint(0, 59))
            country = home
            if mode in ("multi", "night_multi"):
                country = rng.choice([home] + rng.sample(OTHER_COUNTRIES, 2))
            events.append({"ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "ip_country": country})
    if mode == "trip":
        for e in events[-4:]:
            e["ip_country"] = rng.choice(["IT", "GR", "US"])
    return events


def make_candidate(rng, cid, signals, network=None):
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    city, country, tzname, offset = rng.choice(LOCATIONS)
    applied = date(2026, 8, 1) + timedelta(days=rng.randint(0, 40))
    hired = applied + timedelta(days=rng.randint(10, 25))
    years = network["years"] if network else rng.randint(2, 12)

    if network:
        k = network["member"] % len(network["cv"]["summaries"])
        summary = _vary(network["cv"]["summaries"][k], rng)
        stack = network["cv"]["stack"]
        exps = _experiences(rng, years, stack, "timeline_overlap" in signals,
                            network["cv"]["descs"][k % len(network["cv"]["descs"])])
    elif "bootcamp" in signals:
        years, stack = 1, BOOTCAMP_CV["stack"]
        summary = _vary(BOOTCAMP_CV["summary"], rng)
        exps = _experiences(rng, years, stack, network_desc=BOOTCAMP_CV["desc"])
    else:
        stack = rng.choice(STACKS)
        summary = " ".join([rng.choice(SUMMARY_OPENERS), rng.choice(SUMMARY_MIDDLES), rng.choice(SUMMARY_CLOSERS)])
        exps = _experiences(rng, years, stack, "timeline_overlap" in signals)

    domain = rng.choice(DISPOSABLE) if "disposable_email" in signals else rng.choice(EMAIL_DOMAINS)
    email = f"{first.lower()}.{last.lower().replace(' ', '')}{rng.randint(1, 99)}@{domain}"
    phone = f"{PHONE_PREFIX.get(country, '+44 7')}{rng.randint(10_000_000, 99_999_999)}"
    if network and network.get("phone"):
        phone = network["phone"]

    acc_created = applied - timedelta(days=rng.randint(20, 120)) if "young_profile" in signals \
        else applied - timedelta(days=365 * rng.randint(max(1, years - 2), years + 3))
    handle = f"{first.lower()}-{last.lower().replace(' ', '')}-{rng.randint(100, 999)}"
    profiles = [{"platform": "linkedin", "url": f"https://linkedin.example/in/{handle}",
                 "created_at": acc_created.isoformat(),
                 "connections": rng.randint(5, 40) if "young_profile" in signals else rng.randint(150, 900)}]
    if rng.random() < 0.6:
        profiles.append({"platform": "github", "url": f"https://github.example/{handle}",
                         "created_at": (acc_created - timedelta(days=rng.randint(0, 400))).isoformat(),
                         "connections": rng.randint(0, 120)})

    home_addr = f"{rng.randint(1, 120)} {rng.choice(STREETS)}, {city}, {country}"
    shipping = [{"from": applied.isoformat(), "address": home_addr}]
    if "forwarder" in signals:
        shipping = [{"from": applied.isoformat(), "address": network.get("address") if network and network.get("address") else rng.choice(FORWARDERS)}]
    if "address_change_after_hire" in signals or "moved_house" in signals:
        # Fraude : le matériel part chez un transitaire. Légitime : simple déménagement.
        new_addr = rng.choice(FORWARDERS) if "address_change_after_hire" in signals and rng.random() < 0.5 else \
            f"{rng.randint(1, 120)} {rng.choice(STREETS)}, {city}, {country}"
        shipping.append({"from": (hired + timedelta(days=rng.randint(1, 10))).isoformat(), "address": new_addr})

    if "crypto_payment" in signals:
        wallet = network.get("wallet") if network and network.get("wallet") else \
            "0x" + "".join(rng.choice("0123456789abcdef") for _ in range(40))
        payment = {"method": "crypto", "account": wallet}
    else:
        payment = {"method": "iban", "account": f"{country if country != 'UK' else 'GB'}{rng.randint(10, 99)} "
                                                f"{rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}"}

    multi, night = "multi_country_logins" in signals, "night_activity" in signals
    mode = "night_multi" if multi and night else "multi" if multi else "night" if night else \
        "trip" if "one_trip_abroad" in signals else "late" if "late_worker" in signals else "normal"

    return {
        "id": cid,
        "applied_at": applied.isoformat(),
        "hired_at": hired.isoformat(),
        "full_name": f"{first} {last}",
        "email": email,
        "phone": phone,
        "declared_location": {"city": city, "country": country, "timezone": tzname, "utc_offset": offset},
        "cv": {
            "summary": summary,
            "years_experience": years,
            "experiences": exps,
            "education": [{"school": rng.choice(SCHOOLS), "degree": rng.choice(["MSc", "BSc", "Engineering degree"]),
                           "year": 2026 - years - rng.randint(0, 2)}],
            "skills": stack,
        },
        "profiles": profiles,
        "interview": {"camera_refused": "camera_refused" in signals},
        "payment": payment,
        "shipping_addresses": shipping,
        "activity": _logins(rng, hired, offset, country, mode),
    }


def generate(seed=42, n_legit=30, n_solo_fraud=10, network_sizes=(3, 3, 2, 2)):
    rng = random.Random(seed)
    specs = []  # (signals, network, label)
    # Légitimes : 40 % avec un signal bénin, 15 % avec deux, et une paire issue du même bootcamp.
    for i in range(n_legit):
        r = rng.random()
        sig = rng.sample(LEGIT_NOISE, 2) if r < 0.15 else [rng.choice(LEGIT_NOISE)] if r < 0.55 else []
        if i < 2:
            sig = ["bootcamp"]
        specs.append((sig, None, {"is_fraud": False, "network": None}))
    # Fraudes isolées : certaines ne laissent qu'un seul signal.
    for _ in range(n_solo_fraud):
        sig = rng.sample(FRAUD_SIGNALS, rng.choice([1, 2, 2, 3, 4]))
        specs.append((sig, None, {"is_fraud": True, "network": None}))
    # Réseaux : de 0 à 2 identifiants recyclés. Le dernier ne partage que des CV reformulés.
    for i, size in enumerate(network_sizes):
        n_shared = 0 if i == len(network_sizes) - 1 else rng.choice([1, 2])
        shared = rng.sample(["phone", "wallet", "address"], n_shared)
        net = {
            "id": f"N{i + 1}", "cv": NETWORK_CV[i % len(NETWORK_CV)], "years": rng.randint(6, 10),
            "phone": f"+44 7{rng.randint(100_000_000, 999_999_999)}" if "phone" in shared else None,
            "wallet": "0x" + "".join(rng.choice("0123456789abcdef") for _ in range(40)) if "wallet" in shared else None,
            "address": rng.choice(FORWARDERS) if "address" in shared else None,
        }
        for m in range(size):
            sig = rng.sample(["camera_refused", "multi_country_logins", "night_activity", "young_profile"], rng.randint(0, 2))
            if net["wallet"]:
                sig.append("crypto_payment")
            if net["address"]:
                sig.append("forwarder")
            specs.append((sig, {**net, "member": m}, {"is_fraud": True, "network": net["id"]}))

    rng.shuffle(specs)
    candidates, labels = [], {}
    for idx, (sig, net, label) in enumerate(specs, start=1):
        cid = f"C{idx:03d}"
        candidates.append(make_candidate(rng, cid, sig, net))
        labels[cid] = {**label, "injected_signals": sorted(sig)}
    return candidates, labels


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="metadata/data/synthetic")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    candidates, labels = generate(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    n_fraud = sum(l["is_fraud"] for l in labels.values())
    print(f"{len(candidates)} dossiers écrits dans {out} ({n_fraud} frauduleux).")


if __name__ == "__main__":
    main()
