# Evaluation Report

**Overall Score: 99/100**

## Dimension Scores
- Entity Accuracy: 100/100 (weight 25)
- Completeness: 100/100 (weight 20)
- Structure: 100/100 (weight 20)
- Consistency: 100/100 (weight 15)
- Template Fidelity: 89/100 (weight 10)
- Hallucination Check: 100/100 (weight 10)

## Deterministic Checks
- [PASS] Respondent number consistency -- All self-referential occurrences read Respondent No. 2. (source: affidavit title, deponent clause, body, verification, advocate block)
- [PASS] Verification paragraph range -- Verification states 'paragraphs 1 to 7', matching the 7 body paragraphs actually present. (source: Verification section vs. body paragraphs)
- [PASS] Required sections present -- All required sections and expected elements are present. (source: generated document, whole-document scan)
- [PASS] Prayer lettering format -- Prayer uses lettered items ['a', 'b'], not numbered. (source: Prayer section)
- [PASS] Deponent/jurat verb agreement -- Deponent clause uses 'solemnly affirm'; jurat correctly uses 'Solemnly affirmed'. (source: Deponent clause vs. Jurat)
- [PASS] Hallucination check -- No proper nouns, dates or numbers appear in generated text that are absent from the source case facts. (source: all body paragraphs vs. extracted entities)

## Issues Detected
1. Fixed phrase not retained: "has suppressed material facts"
2. Fixed phrase not retained: "With reference to the averments made in the Petition"

## Scoring Method
Overall score is a weighted average of six dimensions: Entity Accuracy (25), Completeness (20), Structure (20), Consistency (15), Template Fidelity (10), Hallucination Check (10). Each dimension is scored 0-100 from the deterministic checks above (entity presence, required-section presence, section ordering, respondent-number/verb/verification-count consistency, retained fixed phrases, and unsupported-token detection), then combined by weight. No dimension score depends on an LLM judgement call.