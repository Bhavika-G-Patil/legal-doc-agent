"""
evaluator.py

Turns the deterministic CheckResults into the evaluation report the
assignment requires: an overall score, per-dimension scores, an issue
list with sources, and an explanation of the scoring method.

Scoring scheme (weights sum to 100 -- one defensible scheme among many;
explained in the report itself, as the assignment requires):

    Entity Accuracy     25   -- required entity values found verbatim in the doc
    Completeness        20   -- required sections / expected elements present
    Structure           20   -- sections appear in the required order
    Consistency         15   -- respondent-number, verb-agreement,
                                 verification-count checks
    Template Fidelity   10   -- fixed phrases from the reference retained
    Hallucination        10   -- no unsupported additions detected
"""

import re
from dataclasses import dataclass
from typing import List, Dict

from docx import Document

from src.extractor import CaseEntities
from src.mapper import Paragraph
from src.validator import CheckResult, run_all_checks
from src.schema import REQUIRED_SECTIONS, ADDITIONAL_EXPECTED_ELEMENTS, FIXED_PHRASES

WEIGHTS = {
    "Entity Accuracy": 25,
    "Completeness": 20,
    "Structure": 20,
    "Consistency": 15,
    "Template Fidelity": 10,
    "Hallucination Check": 10,
}


def _full_text(docx_path: str) -> str:
    doc = Document(docx_path)
    return "\n".join(p.text for p in doc.paragraphs)


def _entity_accuracy(docx_path: str, ce: CaseEntities) -> (float, List[str]):
    text = _full_text(docx_path)
    fields = ["court", "jurisdiction", "petitioner", "respondent_1", "respondent_2",
              "deponent_name", "designation", "place"]
    missing = []
    for f in fields:
        val = getattr(ce, f)
        if val and val not in text and val.upper() not in text.upper():
            missing.append(f)
    score = 100 * (len(fields) - len(missing)) / len(fields)
    issues = [f"Entity '{f}' not found verbatim in generated document." for f in missing]
    return score, issues


def _completeness(section_check: CheckResult) -> (float, List[str]):
    total = len(REQUIRED_SECTIONS) + len(ADDITIONAL_EXPECTED_ELEMENTS)
    if section_check.passed:
        return 100.0, []
    missing = section_check.message.replace("Missing: ", "").rstrip(".").split(", ")
    score = 100 * (total - len(missing)) / total
    return score, [f"Missing expected element: {m}" for m in missing]


def _structure(docx_path: str) -> (float, List[str]):
    text = _full_text(docx_path)
    order_markers = [
        ("forum_heading", r"IN THE HIGH COURT"),
        ("jurisdiction", r"JURISDICTION\n"),
        ("case_number", r"NO\.\s*\d+\s*OF\s*\d+"),
        ("affidavit_title", r"AFFIDAVIT IN REPLY"),
        ("body_paragraphs", r"^1\.\s+I "),
        ("prayer", r"^PRAYER$"),
        ("jurat", r"(Solemnly affirmed|Sworn) at"),
        ("verification", r"^VERIFICATION$"),
    ]
    positions = []
    for name, pat in order_markers:
        m = re.search(pat, text, re.M)
        positions.append((name, m.start() if m else None))
    found = [p for p in positions if p[1] is not None]
    in_order = all(found[i][1] < found[i + 1][1] for i in range(len(found) - 1))
    if in_order and len(found) == len(positions):
        return 100.0, []
    issues = []
    if len(found) != len(positions):
        missing = [n for n, pos in positions if pos is None]
        issues.append(f"Sections not found for ordering check: {missing}")
    if not in_order:
        issues.append("Sections are present but not in the required order.")
    score = 100.0 if not issues else 70.0
    return score, issues


def _consistency(checks: List[CheckResult]) -> (float, List[str]):
    relevant = [c for c in checks if c.name in (
        "Respondent number consistency", "Deponent/jurat verb agreement",
        "Verification paragraph range")]
    passed = sum(1 for c in relevant if c.passed)
    score = 100 * passed / len(relevant) if relevant else 100.0
    issues = [f"{c.name}: {c.message}" for c in relevant if not c.passed]
    return score, issues


def _template_fidelity(docx_path: str) -> (float, List[str]):
    text = _full_text(docx_path)
    all_phrases = [p for group in FIXED_PHRASES.values() for p in group]
    found = [p for p in all_phrases if p.lower() in text.lower()]
    score = 100 * len(found) / len(all_phrases)
    missing = [p for p in all_phrases if p not in found]
    issues = [f"Fixed phrase not retained: \"{m}\"" for m in missing[:5]]
    return score, issues


def _hallucination(checks: List[CheckResult]) -> (float, List[str]):
    c = next(c for c in checks if c.name == "Hallucination check")
    return (100.0, []) if c.passed else (60.0, [c.message])


@dataclass
class EvaluationReport:
    overall: float
    dimension_scores: Dict[str, float]
    issues: List[str]
    checks: List[CheckResult]

    def to_markdown(self) -> str:
        lines = ["# Evaluation Report", ""]
        lines.append(f"**Overall Score: {self.overall:.0f}/100**")
        lines.append("")
        lines.append("## Dimension Scores")
        for dim, score in self.dimension_scores.items():
            lines.append(f"- {dim}: {score:.0f}/100 (weight {WEIGHTS[dim]})")
        lines.append("")
        lines.append("## Deterministic Checks")
        for c in self.checks:
            mark = "PASS" if c.passed else "FAIL"
            lines.append(f"- [{mark}] {c.name} -- {c.message} (source: {c.source})")
        lines.append("")
        lines.append("## Issues Detected")
        if self.issues:
            for i, issue in enumerate(self.issues, 1):
                lines.append(f"{i}. {issue}")
        else:
            lines.append("None.")
        lines.append("")
        lines.append("## Scoring Method")
        lines.append(
            "Overall score is a weighted average of six dimensions: Entity Accuracy (25), "
            "Completeness (20), Structure (20), Consistency (15), Template Fidelity (10), "
            "Hallucination Check (10). Each dimension is scored 0-100 from the deterministic "
            "checks above (entity presence, required-section presence, section ordering, "
            "respondent-number/verb/verification-count consistency, retained fixed phrases, "
            "and unsupported-token detection), then combined by weight. No dimension score "
            "depends on an LLM judgement call."
        )
        return "\n".join(lines)


def evaluate(docx_path: str, ce: CaseEntities, paragraphs: List[Paragraph]) -> EvaluationReport:
    checks = run_all_checks(docx_path, ce, paragraphs)
    section_check = next(c for c in checks if c.name == "Required sections present")

    entity_score, entity_issues = _entity_accuracy(docx_path, ce)
    completeness_score, completeness_issues = _completeness(section_check)
    structure_score, structure_issues = _structure(docx_path)
    consistency_score, consistency_issues = _consistency(checks)
    fidelity_score, fidelity_issues = _template_fidelity(docx_path)
    halluc_score, halluc_issues = _hallucination(checks)

    dims = {
        "Entity Accuracy": entity_score,
        "Completeness": completeness_score,
        "Structure": structure_score,
        "Consistency": consistency_score,
        "Template Fidelity": fidelity_score,
        "Hallucination Check": halluc_score,
    }
    overall = sum(dims[d] * WEIGHTS[d] for d in dims) / sum(WEIGHTS.values())

    issues = (entity_issues + completeness_issues + structure_issues +
              consistency_issues + fidelity_issues + halluc_issues)

    return EvaluationReport(overall=overall, dimension_scores=dims, issues=issues, checks=checks)
