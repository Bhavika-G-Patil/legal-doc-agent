"""
extractor.py

Stage 2 of the pipeline: Entity Extraction.

Reads `case_information.txt` (a plain-text rendering of the supplied
Case Information document) and produces the structured intermediate JSON
described in the assignment's "nice to have" section. Parsing is
field-label driven (regex on "Label: value" lines and "Point N - Title"
blocks), not hard-coded to this one case, so a differently-worded case
information file with the same field labels would still parse correctly.
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict


@dataclass
class ReplyPoint:
    number: int
    title: str
    move: str
    bullets: List[str]
    exhibit: str = None
    source: str = ""  # traceability: which line(s) this came from


@dataclass
class CaseEntities:
    court: str = ""
    jurisdiction: str = ""
    proceeding_type: str = ""
    case_number: str = ""
    year: str = ""
    petitioner: str = ""
    respondent_1: str = ""
    respondent_2: str = ""
    respondent_number: int = 2
    deponent_name: str = ""
    designation: str = ""
    organisation: str = ""
    address: str = ""
    verification_verb: str = ""
    prayer_bullets: List[str] = field(default_factory=list)
    place: str = ""
    date: str = ""
    advocate_firm: str = ""
    acting_for: str = ""
    reply_points: List[ReplyPoint] = field(default_factory=list)
    evidence: Dict[str, str] = field(default_factory=dict)  # field -> source line

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2)


FIELD_MAP = {
    "Court": "court",
    "Jurisdiction": "jurisdiction",
    "Proceeding Type": "proceeding_type",
    "Case Number": "case_number",
    "Year": "year",
    "Petitioner": "petitioner",
    "Respondent No. 1": "respondent_1",
    "Respondent No. 2": "respondent_2",
    "Name": "deponent_name",
    "Designation": "designation",
    "Organisation": "organisation",
    "Address": "address",
    "Verification verb": "verification_verb",
    "Place": "place",
    "Date": "date",
    "Advocate Firm": "advocate_firm",
    "Acting for": "acting_for",
}


def extract_entities(text: str) -> CaseEntities:
    ce = CaseEntities()

    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        label, _, value = line.partition(":")
        label, value = label.strip(), value.strip()
        if label in FIELD_MAP and value:
            attr = FIELD_MAP[label]
            setattr(ce, attr, value)
            ce.evidence[attr] = line

    # "Filed on behalf of: Respondent No. 2" -> respondent_number = 2
    m = re.search(r"Filed on behalf of:\s*Respondent No\.\s*(\d+)", text)
    if m:
        ce.respondent_number = int(m.group(1))

    # Reply points: "Point N - Title [MOVE:XXX][EXHIBIT:A]" followed by "- bullet" lines
    point_pattern = re.compile(
        r"^Point\s+(\d+)\s*-\s*(.+?)\s*\[MOVE:([A-Z_]+)\](?:\[EXHIBIT:([A-Za-z])\])?\s*$"
    )
    points = []
    current = None
    for line in text.splitlines():
        raw = line.rstrip()
        stripped = raw.strip()
        m = point_pattern.match(stripped)
        if m:
            if current:
                points.append(current)
            current = ReplyPoint(
                number=int(m.group(1)),
                title=m.group(2),
                move=m.group(3),
                bullets=[],
                exhibit=m.group(4),
                source=stripped,
            )
        elif current and stripped.startswith("-"):
            current.bullets.append(stripped.lstrip("- ").strip())
        elif current and stripped == "":
            continue
        elif current and stripped:
            # Any other non-blank line (e.g. a new section header like
            # "4. Prayer") closes the current reply point.
            points.append(current)
            current = None
    if current:
        points.append(current)
    ce.reply_points = points

    # Prayer bullets: lines under "4. Prayer" starting with "-"
    prayer_section = re.search(r"4\.\s*Prayer\s*\n(.*?)\n\s*\n", text, re.S)
    if prayer_section:
        for line in prayer_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                ce.prayer_bullets.append(line.lstrip("- ").strip())

    return ce


def load_case_entities(path: str) -> CaseEntities:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return extract_entities(text)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/case_information.txt"
    ce = load_case_entities(path)
    print(ce.to_json())
