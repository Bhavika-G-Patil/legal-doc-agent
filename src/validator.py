"""
validator.py

Deterministic validation checks -- none of these call an LLM. The
assignment requires at least three; this implements six, each returning a
structured result so the evaluator can turn them into scores and the UI
can show a pass/fail list with a source reference for each issue.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from docx import Document

from src.extractor import CaseEntities
from src.mapper import Paragraph
from src.schema import REQUIRED_SECTIONS, ADDITIONAL_EXPECTED_ELEMENTS, VERB_AGREEMENT


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    source: str  # where in the document this was checked


def _full_text(docx_path: str) -> str:
    doc = Document(docx_path)
    return "\n".join(p.text for p in doc.paragraphs)


def check_respondent_number_consistency(docx_path: str, ce: CaseEntities) -> CheckResult:
    """Checks that every *self-referential* mention of the answering respondent
    (affidavit title, deponent clause, body paragraphs, verification, advocate
    block) uses the same respondent number. The cause title legitimately lists
    other respondents (e.g. Respondent No.1) and is excluded -- that is a
    different party, not an inconsistency."""
    text = _full_text(docx_path)
    marker = "AFFIDAVIT IN REPLY ON BEHALF OF RESPONDENT NO."
    idx = text.find(marker)
    self_referential_text = text[idx:] if idx != -1 else text
    found = set(re.findall(r"Respondent No\.\s*(\d+)", self_referential_text, re.I))
    expected = {str(ce.respondent_number)}
    if found == expected:
        return CheckResult("Respondent number consistency", True,
                            f"All self-referential occurrences read Respondent No. "
                            f"{ce.respondent_number}.",
                            "affidavit title, deponent clause, body, verification, advocate block")
    return CheckResult("Respondent number consistency", False,
                        f"Found Respondent No. values {sorted(found)} in the affidavit's "
                        f"self-referential sections, expected only {sorted(expected)}.",
                        "affidavit title, deponent clause, body, verification, advocate block")


def check_verification_paragraph_count(docx_path: str, paragraphs: List[Paragraph]) -> CheckResult:
    text = _full_text(docx_path)
    m = re.search(r"contents of paragraphs 1 to (\d+)", text)
    actual = len(paragraphs)
    if not m:
        return CheckResult("Verification paragraph range", False,
                            "Could not find a 'paragraphs 1 to N' statement in Verification.",
                            "Verification section")
    stated = int(m.group(1))
    if stated == actual:
        return CheckResult("Verification paragraph range", True,
                            f"Verification states 'paragraphs 1 to {stated}', matching the "
                            f"{actual} body paragraphs actually present.",
                            "Verification section vs. body paragraphs")
    return CheckResult("Verification paragraph range", False,
                        f"Verification states 'paragraphs 1 to {stated}' but the body has "
                        f"{actual} paragraphs.",
                        "Verification section vs. body paragraphs")


SECTION_MARKERS = {
    "forum_heading": r"IN THE HIGH COURT",
    "jurisdiction": r"JURISDICTION",
    "case_number": r"NO\.\s*\d+\s*OF\s*\d+",
    "cause_title": r"\.\.\.Petitioner",
    "affidavit_title": r"AFFIDAVIT IN REPLY ON BEHALF",
    "deponent_clause": r"do hereby .* affirm and state as under",
    "body_paragraphs": r"^1\.\s+I ",
    "prayer": r"^PRAYER$",
    "jurat": r"^(Solemnly affirmed|Sworn) at",
    "verification": r"^VERIFICATION$",
    "exhibit_reference": r"EXHIBIT-",
    "advocate_block": r"Advocates for the Respondent",
}


def check_required_sections(docx_path: str) -> CheckResult:
    text = _full_text(docx_path)
    missing = []
    for section in REQUIRED_SECTIONS + ADDITIONAL_EXPECTED_ELEMENTS:
        pattern = SECTION_MARKERS.get(section)
        if not pattern:
            continue
        if not re.search(pattern, text, re.M):
            missing.append(section)
    if not missing:
        return CheckResult("Required sections present", True,
                            "All required sections and expected elements are present.",
                            "generated document, whole-document scan")
    return CheckResult("Required sections present", False,
                        f"Missing: {', '.join(missing)}.",
                        "generated document, whole-document scan")


def check_prayer_lettering(docx_path: str) -> CheckResult:
    text = _full_text(docx_path)
    prayer_match = re.search(r"PRAYER\n(.*?)\n\n", text, re.S)
    if not prayer_match:
        return CheckResult("Prayer lettering format", False,
                            "Prayer section not found.", "Prayer section")
    prayer_block = prayer_match.group(1)
    lettered = re.findall(r"^\(([a-z])\)", prayer_block, re.M)
    numbered = re.findall(r"^(\d+)\.", prayer_block, re.M)
    if lettered and not numbered:
        return CheckResult("Prayer lettering format", True,
                            f"Prayer uses lettered items {lettered}, not numbered.",
                            "Prayer section")
    return CheckResult("Prayer lettering format", False,
                        f"Prayer should use (a)(b)(c); found lettered={lettered}, "
                        f"numbered={numbered}.",
                        "Prayer section")


def check_verb_agreement(docx_path: str, ce: CaseEntities) -> CheckResult:
    text = _full_text(docx_path)
    expected_jurat_verb = VERB_AGREEMENT.get(ce.verification_verb)
    if not expected_jurat_verb:
        return CheckResult("Deponent/jurat verb agreement", False,
                            f"Unrecognised verification verb '{ce.verification_verb}'.",
                            "Deponent clause")
    if re.search(re.escape(expected_jurat_verb), text):
        return CheckResult("Deponent/jurat verb agreement", True,
                            f"Deponent clause uses '{ce.verification_verb}'; jurat correctly "
                            f"uses '{expected_jurat_verb}'.",
                            "Deponent clause vs. Jurat")
    return CheckResult("Deponent/jurat verb agreement", False,
                        f"Deponent clause uses '{ce.verification_verb}' but jurat does not "
                        f"contain the matching '{expected_jurat_verb}'.",
                        "Deponent clause vs. Jurat")


def check_hallucinations(paragraphs: List[Paragraph], ce: CaseEntities) -> CheckResult:
    """Heuristic hallucination check: every capitalised multi-word phrase, date,
    or number in the (possibly LLM-polished) paragraph text must trace back to
    the deterministic draft built directly from the extracted case facts. This
    catches an LLM inventing a new name, date, section or amount, without
    needing another LLM call to judge it."""
    source_text = " ".join(p.deterministic_text for p in paragraphs) + " " + \
        " ".join(b for pt in ce.reply_points for b in pt.bullets)
    source_tokens = set(re.findall(r"\b[A-Z][a-zA-Z']+\b|\b\d{1,4}\b", source_text))

    flagged = []
    for p in paragraphs:
        gen_tokens = set(re.findall(r"\b[A-Z][a-zA-Z']+\b|\b\d{1,4}\b", p.text))
        extra = gen_tokens - source_tokens - {"I", "With", "In", "The", "No",
                                               "Respondent", "Petition", "Petitioner"}
        if extra:
            flagged.append((p.number, sorted(extra)))

    if not flagged:
        return CheckResult("Hallucination check", True,
                            "No proper nouns, dates or numbers appear in generated text "
                            "that are absent from the source case facts.",
                            "all body paragraphs vs. extracted entities")
    detail = "; ".join(f"para {n}: {toks}" for n, toks in flagged)
    return CheckResult("Hallucination check", False,
                        f"Possible unsupported additions -- {detail}.",
                        "body paragraphs vs. extracted entities")


def run_all_checks(docx_path: str, ce: CaseEntities,
                    paragraphs: List[Paragraph]) -> List[CheckResult]:
    return [
        check_respondent_number_consistency(docx_path, ce),
        check_verification_paragraph_count(docx_path, paragraphs),
        check_required_sections(docx_path),
        check_prayer_lettering(docx_path),
        check_verb_agreement(docx_path, ce),
        check_hallucinations(paragraphs, ce),
    ]
