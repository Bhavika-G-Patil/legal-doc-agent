"""
schema.py

Encodes the reference Affidavit-in-Reply structure as data, not as
hard-coded document logic. This is what Stage 1 ("Template / Structure
Analysis") of the assignment produces: a reusable schema that the rest of
the pipeline (mapper, docgen, validator, evaluator) reads instead of
re-deriving the format from scratch each time.

The ten parts and the fixed phrases below were extracted from
`01_Affidavit_Format_Explained.pdf`. If a different reference document
were supplied for a second document type, only this file (and the
extractor's field list) would need to change -- the pipeline itself is
generic.
"""

# The ten required parts, in required order. Used by the validator's
# "required sections present" / "structure order" checks.
REQUIRED_SECTIONS = [
    "forum_heading",
    "jurisdiction",
    "case_number",
    "cause_title",
    "affidavit_title",
    "deponent_clause",
    "body_paragraphs",
    "prayer",
    "jurat",
    "verification",
]

# Not one of the "ten parts" proper, but expected by the assignment's
# "Expected Output" section (advocate / drafting block, exhibit reference).
ADDITIONAL_EXPECTED_ELEMENTS = [
    "exhibit_reference",
    "advocate_block",
]

# Fixed phrases the reference document uses verbatim. Template-fidelity
# scoring checks how many of these survive into the generated document.
FIXED_PHRASES = {
    "deponent_clause": [
        "above named",
        "do hereby solemnly affirm and state as under",
    ],
    "identity_and_perusal": [
        "am well acquainted with the facts and circumstances of the case",
        "I have perused the Petition and the documents annexed thereto",
        "competent to affirm this Affidavit in Reply",
    ],
    "blanket_denial": [
        "At the outset, I deny each and every allegation, contention and submission",
        "save and except those specifically admitted herein",
        "misconceived, devoid of merits and is liable to be dismissed in limine",
    ],
    "preliminary_position": [
        "has suppressed material facts",
        "strictly in accordance with law and after following due procedure",
        "No legal, constitutional or fundamental right",
    ],
    "substantive_answer": [
        "With reference to the averments made in the Petition",
        "I say that",
    ],
    "closing": [
        "In the premises aforesaid",
        "deserves to be dismissed with costs",
    ],
    "prayer": [
        "I therefore respectfully pray that this Hon'ble Court may be pleased to",
        "grant such other and further reliefs as this Hon'ble Court may deem fit and proper",
    ],
    "verification": [
        "true and correct to my knowledge and belief",
        "nothing material has been concealed therefrom",
    ],
}

# Verb agreement pairs allowed between the deponent clause and the jurat.
VERB_AGREEMENT = {
    "solemnly affirm": "Solemnly affirmed",
    "swear and affirm": "Sworn",
}
