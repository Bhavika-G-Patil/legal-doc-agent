"""
llm_extractor.py

Optional LLM-assisted entity extraction.

The LLM converts case information into the SAME CaseEntities structure
used by the deterministic pipeline. If the LLM is unavailable or returns
invalid data, the caller can safely fall back to extract_entities().
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.extractor import CaseEntities, ReplyPoint

load_dotenv()


def llm_extract_entities(
    text: str,
    model: str = "gpt-5.6-luna",
) -> Optional[CaseEntities]:

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    client = OpenAI(api_key=api_key)

    instructions = """
You are an information extraction component for an Affidavit in Reply
document-generation pipeline.

Extract ONLY facts explicitly supplied in the case information.

Rules:
- Do not invent facts.
- Do not perform legal research.
- Do not add legal arguments.
- Preserve names, dates, case numbers and party names.
- Preserve the order of reply points.
- Preserve the wording of reply-point bullets as closely as possible.
- If information is missing, use an empty string.
- Return valid JSON only.

Return exactly this structure:

{
  "court": "",
  "jurisdiction": "",
  "proceeding_type": "",
  "case_number": "",
  "year": "",
  "petitioner": "",
  "respondent_1": "",
  "respondent_2": "",
  "respondent_number": 2,
  "deponent_name": "",
  "designation": "",
  "organisation": "",
  "address": "",
  "verification_verb": "",
  "prayer_bullets": [],
  "place": "",
  "date": "",
  "advocate_firm": "",
  "acting_for": "",
  "reply_points": [
    {
      "number": 1,
      "title": "",
      "move": "",
      "bullets": [],
      "exhibit": null,
      "source": ""
    }
  ]
}
"""

    try:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=text,
        )

        raw = response.output_text.strip()

        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]

        if raw.endswith("```"):
            raw = raw[:-3]

        data = json.loads(raw.strip())

        reply_points = [
            ReplyPoint(
                number=int(point.get("number", 0)),
                title=str(point.get("title", "")),
                move=str(point.get("move", "")),
                bullets=point.get("bullets", []),
                exhibit=point.get("exhibit") or None,
                source=point.get("source", "LLM extraction"),
            )
            for point in data.get("reply_points", [])
        ]

        return CaseEntities(
            court=data.get("court", ""),
            jurisdiction=data.get("jurisdiction", ""),
            proceeding_type=data.get("proceeding_type", ""),
            case_number=str(data.get("case_number", "")),
            year=str(data.get("year", "")),
            petitioner=data.get("petitioner", ""),
            respondent_1=data.get("respondent_1", ""),
            respondent_2=data.get("respondent_2", ""),
            respondent_number=int(data.get("respondent_number", 2)),
            deponent_name=data.get("deponent_name", ""),
            designation=data.get("designation", ""),
            organisation=data.get("organisation", ""),
            address=data.get("address", ""),
            verification_verb=data.get("verification_verb", ""),
            prayer_bullets=data.get("prayer_bullets", []),
            place=data.get("place", ""),
            date=data.get("date", ""),
            advocate_firm=data.get("advocate_firm", ""),
            acting_for=data.get("acting_for", ""),
            reply_points=reply_points,
            evidence={"extraction_method": "OpenAI LLM"},
        )

    except Exception as exc:
        print(f"LLM extraction failed: {exc}")
        return None
