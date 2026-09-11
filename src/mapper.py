"""
mapper.py

Stage 3 (Content Mapping) + Stage 4 (Document Generation, text level).

Maps each ReplyPoint onto a numbered body paragraph, in the fixed move
order the reference document uses (Identity -> Blanket denial ->
Preliminary position -> Substantive answers -> Closing), and produces the
paragraph text.

Generation strategy:
- DETERMINISTIC (default, no API key needed): fills the fixed-phrase
  templates from schema.py with the extracted bullets. Fully
  reproducible -- this is what "pre-run / cached demo mode" in the README
  refers to.
- LLM-ASSISTED (if ANTHROPIC_API_KEY is set): asks the model to phrase the
  same bullets in the reference document's register, using the
  deterministic version as a grounding example. The deterministic
  version is *always* computed too, and is used downstream by the
  hallucination checker as the "source of truth" to diff the LLM output
  against.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

from src.extractor import CaseEntities, ReplyPoint


@dataclass
class Paragraph:
    number: int
    move: str
    source_point: Optional[int]
    text: str
    deterministic_text: str  # always populated; used for hallucination diffing


def _identity_paragraph(ce: CaseEntities, point: ReplyPoint) -> str:
    subj = f"the {ce.designation} of the Respondent No.{ce.respondent_number}" \
        if ce.organisation else f"the Respondent No.{ce.respondent_number}"
    return (
        f"I say that I am {subj} in the above {ce.proceeding_type} and am well "
        f"acquainted with the facts and circumstances of the case. I have perused "
        f"the Petition and the documents annexed thereto and am competent to "
        f"affirm this Affidavit in Reply."
    )


def _blanket_denial_paragraph(ce: CaseEntities, point: ReplyPoint) -> str:
    return (
        f"At the outset, I deny each and every allegation, contention and "
        f"submission made in the {ce.proceeding_type}, save and except those "
        f"specifically admitted herein. I say that the {ce.proceeding_type} is "
        f"misconceived, devoid of merits and is liable to be dismissed in limine."
    )


def _preliminary_position_paragraph(ce: CaseEntities, point: ReplyPoint) -> str:
    bullets = " ".join(point.bullets)
    return (
        f"I say that {bullets[0].lower() + bullets[1:] if bullets else ''} "
        f"The action complained of has been taken strictly in accordance with "
        f"law and after following due procedure. No legal, constitutional or "
        f"fundamental right of the Petitioner has been infringed."
    ).replace("  ", " ")


def _substantive_answer_paragraph(ce: CaseEntities, point: ReplyPoint) -> str:
    body = " ".join(point.bullets)
    text = (
        f"With reference to the averments made in the {ce.proceeding_type} "
        f"regarding {point.title.lower()}, I say that {body[0].lower() + body[1:]}"
    )
    if point.exhibit:
        text += (
            f" Hereto annexed and marked as EXHIBIT-'{point.exhibit}' is a true "
            f"copy of the said communication."
        )
    return text


def _closing_paragraph(ce: CaseEntities) -> str:
    return (
        f"In the premises aforesaid, I say that the {ce.proceeding_type} "
        f"deserves to be dismissed with costs."
    )


MOVE_HANDLERS = {
    "IDENTITY_AND_PERUSAL": _identity_paragraph,
    "BLANKET_DENIAL": _blanket_denial_paragraph,
    "PRELIMINARY_POSITION": _preliminary_position_paragraph,
    "SUBSTANTIVE_ANSWER": _substantive_answer_paragraph,
}


def build_deterministic_paragraphs(ce: CaseEntities) -> List[Paragraph]:
    paragraphs = []
    n = 1
    for point in ce.reply_points:
        handler = MOVE_HANDLERS.get(point.move)
        text = handler(ce, point) if handler else " ".join(point.bullets)
        paragraphs.append(Paragraph(number=n, move=point.move,
                                     source_point=point.number,
                                     text=text, deterministic_text=text))
        n += 1
    # Closing paragraph is always appended, mapped from no single point.
    closing = _closing_paragraph(ce)
    paragraphs.append(Paragraph(number=n, move="CLOSING", source_point=None,
                                 text=closing, deterministic_text=closing))
    return paragraphs


LLM_SYSTEM_PROMPT = """You redraft one paragraph of an Indian High Court \
Affidavit in Reply. Rules:
- Keep every fact, name, date, number and respondent designation EXACTLY as given. \
Do not invent, add, or drop any fact.
- Match the register of Indian court affidavits (formal, "I say that...", "the said...").
- Return ONLY the paragraph text, no numbering, no preamble, no markdown."""


def llm_rephrase(paragraph_text: str, point: ReplyPoint) -> Optional[str]:
    """Best-effort LLM polish of a deterministic paragraph. Returns None on any
    failure (missing key, network error, import error) so the caller can fall
    back to the deterministic text -- the pipeline must work with zero
    external dependencies."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        user_msg = (
            f"Source facts (do not add to these): {point.bullets}\n\n"
            f"Deterministic draft to improve:\n{paragraph_text}"
        )
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return out or None
    except Exception:
        return None


def build_paragraphs(ce: CaseEntities, use_llm: bool = True) -> List[Paragraph]:
    paragraphs = build_deterministic_paragraphs(ce)
    if not use_llm:
        return paragraphs
    for p in paragraphs:
        point = next((pt for pt in ce.reply_points if pt.number == p.source_point), None)
        if point is None:
            continue
        polished = llm_rephrase(p.deterministic_text, point)
        if polished:
            p.text = polished
    return paragraphs
