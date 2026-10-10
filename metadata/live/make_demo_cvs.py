"""Génère les deux CV PDF de la démo (candidate honnête, fraudeur) à partir de `demo_example`.

    pip install reportlab
    python -m metadata.live.make_demo_cvs      # écrit metadata/live/demo_cvs/*.pdf

Les PDF sont commités : la démo n'a pas besoin de reportlab. On ne les régénère que si
les dossiers synthétiques changent (le CV du fraudeur recycle un membre de réseau).
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from .applications import demo_example

OUT = Path(__file__).resolve().parent / "demo_cvs"
COUNTRY = {"fr": {"FR": "France", "NL": "Pays-Bas"}, "en": {"FR": "France", "NL": "Netherlands"}}
LABELS = {"fr": ("PROFIL", "EXPÉRIENCE", "FORMATION", "COMPÉTENCES", "aujourd'hui"),
          "en": ("SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS", "present")}

INK, MUTED, BRAND = HexColor("#0f1b2d"), HexColor("#5b6b80"), HexColor("#1f4fd8")
NAME = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=INK)
HEAD = ParagraphStyle("head", fontName="Helvetica", fontSize=13, leading=18, textColor=BRAND)
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=9.5, leading=13, textColor=MUTED)
SECTION = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=BRAND,
                         spaceBefore=12)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
ROLE = ParagraphStyle("role", parent=BODY, fontName="Helvetica-Bold", spaceBefore=6)


def _month(ym: str, now: str) -> str:
    return f"{ym[5:7]}/{ym[:4]}" if ym else now


def build(ex: dict, lang: str, path: Path) -> None:
    profil, experience, formation, competences, now = LABELS[lang]
    links = [u.replace("https://", "") for u in (ex["linkedin_url"], ex["github_url"]) if u]
    story = [
        Paragraph(f"{ex['first_name']} {ex['last_name']}", NAME),
        Paragraph(ex["headline"], HEAD),
        Paragraph(f"{ex['email']} · {ex['phone']} · {ex['city']}, {COUNTRY[lang][ex['country']]}", SMALL),
        Paragraph(" · ".join(links), SMALL),
        Spacer(1, 4),
        HRFlowable(width="100%", color=HexColor("#dfe5ee"), thickness=0.8),
        Paragraph(profil, SECTION), Paragraph(ex["summary"], BODY),
        Paragraph(experience, SECTION),
    ]
    for e in ex["experiences"]:
        story += [Paragraph(f"{e['title']} — {e['company']}", ROLE),
                  Paragraph(f"{_month(e['start'], now)} – {_month(e['end'], now)}", SMALL),
                  Paragraph(e["description"], BODY)]
    story.append(Paragraph(formation, SECTION))
    for ed in ex["education"]:
        story.append(Paragraph(f"{ed['degree']} — {ed['school']}, {ed['year']}", BODY))
    story += [Paragraph(competences, SECTION), Paragraph(ex["skills"].replace(", ", " · "), BODY)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                      bottomMargin=18 * mm, title=f"CV {ex['first_name']} {ex['last_name']}",
                      author=f"{ex['first_name']} {ex['last_name']}").build(story)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for kind, lang in (("honest", "fr"), ("fraud", "en")):
        ex = demo_example(kind)
        path = OUT / f"CV_{ex['first_name']}_{ex['last_name']}.pdf"
        build(ex, lang, path)
        print(path)


if __name__ == "__main__":
    main()
