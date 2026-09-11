"""
docgen.py

Assembles the generated Affidavit in Reply into a .docx, following the
formatting rules extracted from 01_Affidavit_Format_Explained.pdf section 5
(bold/caps/centred headings, right-aligned status tags, lettered prayer,
etc.). This is pure formatting logic driven by the entities + paragraphs
passed in -- no case-specific facts are hard-coded here.
"""

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import List

import re

from src.extractor import CaseEntities
from src.mapper import Paragraph
from src.schema import VERB_AGREEMENT


def _as_prayer_clause(bullet: str) -> str:
    """Case-information prayer bullets are phrased declaratively (e.g.
    "Respondent No. 2 prays that the Writ Petition be dismissed with costs").
    A prayer clause needs the imperative form ("dismiss the Writ Petition with
    costs"). Reduce to the clause after 'prays that ' when present, otherwise
    use the bullet as given."""
    m = re.search(r"prays that (?:this Hon'ble Court (?:may )?)?(.+)", bullet, re.I)
    return m.group(1).strip() if m else bullet


def _heading(doc, text, bold=True, size=12):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(size)
    return p


def _para(doc, text, align=WD_ALIGN_PARAGRAPH.LEFT, bold=False):
    p = doc.add_paragraph()
    p.alignment = align
    r = p.add_run(text)
    r.bold = bold
    return p


def generate_docx(ce: CaseEntities, paragraphs: List[Paragraph], out_path: str,
                   inject_demo_error: bool = False) -> str:
    doc = Document()

    # 1. Forum heading
    _heading(doc, ce.court.upper())
    # 2. Jurisdiction
    _heading(doc, ce.jurisdiction.upper())
    # 3. Case number
    _heading(doc, f"{ce.proceeding_type} NO. {ce.case_number} OF {ce.year}".upper())
    doc.add_paragraph()

    # 4. Cause title
    p = doc.add_paragraph()
    p.add_run(f"{ce.petitioner}").bold = False
    tag = doc.add_paragraph()
    tag.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tag.add_run("...Petitioner")

    _heading(doc, "VERSUS", bold=False)

    r1 = doc.add_paragraph()
    r1.add_run(f"1. {ce.respondent_1}")
    tag1 = doc.add_paragraph()
    tag1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tag1.add_run("...Respondent No.1")

    r2 = doc.add_paragraph()
    r2.add_run(f"2. {ce.respondent_2}")
    tag2 = doc.add_paragraph()
    tag2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tag2.add_run(f"...Respondent No.{ce.respondent_number}")
    doc.add_paragraph()

    # 5. Affidavit title
    demo_resp_no = ce.respondent_number + 1 if inject_demo_error else ce.respondent_number
    _heading(doc, f"AFFIDAVIT IN REPLY ON BEHALF OF RESPONDENT NO. {demo_resp_no}")
    doc.add_paragraph()

    # 6. Deponent clause
    subj = (f"the {ce.designation} of the Respondent No.{ce.respondent_number} above named"
            if ce.organisation else f"the Respondent No.{ce.respondent_number} above named")
    _para(doc,
          f"I, {ce.deponent_name}, {ce.designation}, having office at {ce.address}, {subj}, "
          f"do hereby {ce.verification_verb} and state as under:")
    doc.add_paragraph()

    # 7. Numbered body paragraphs
    for para in paragraphs:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        num_run = p.add_run(f"{para.number}. ")
        num_run.bold = True
        p.add_run(para.text)
    doc.add_paragraph()

    # 8. Prayer
    _heading(doc, "PRAYER")
    _para(doc, "I therefore respectfully pray that this Hon'ble Court may be pleased to:")
    letters = "abcdefghijklmnop"
    prayer_items = ce.prayer_bullets or [f"dismiss the present {ce.proceeding_type} with costs"]
    for i, item in enumerate(prayer_items):
        p = doc.add_paragraph()
        lr = p.add_run(f"({letters[i]}) ")
        lr.bold = True
        p.add_run(_as_prayer_clause(item))
    p = doc.add_paragraph()
    lr = p.add_run(f"({letters[len(prayer_items)]}) ")
    lr.bold = True
    p.add_run("grant such other and further reliefs as this Hon'ble Court may deem fit "
               "and proper in the facts and circumstances of the case.")
    doc.add_paragraph()

    # 9. Jurat / attestation
    jurat_verb = VERB_AGREEMENT.get(ce.verification_verb, "Solemnly affirmed")
    _para(doc, f"{jurat_verb} at {ce.place}")
    _para(doc, f"On this {ce.date}")
    dep = doc.add_paragraph()
    dep.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    dep.add_run("DEPONENT").bold = False
    _para(doc, "Before Me")
    doc.add_paragraph()

    # 10. Verification
    _heading(doc, "VERIFICATION")
    body_count = len(paragraphs)
    verification_count = body_count - 1 if inject_demo_error else body_count
    _para(doc,
          f"I, {ce.deponent_name}, the Deponent above named, do hereby verify that the "
          f"contents of paragraphs 1 to {verification_count} and the Prayer above are true "
          f"and correct to my knowledge and belief and that nothing material has been "
          f"concealed therefrom.")
    _para(doc, f"Verified at {ce.place} on this {ce.date}.")
    dep2 = doc.add_paragraph()
    dep2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    dep2.add_run("DEPONENT")
    doc.add_paragraph()

    # Advocate / drafting block
    _para(doc, ce.advocate_firm.upper() if ce.advocate_firm else "")
    _para(doc, f"Advocates for the {ce.acting_for}." if ce.acting_for else "")

    doc.save(out_path)
    return out_path
