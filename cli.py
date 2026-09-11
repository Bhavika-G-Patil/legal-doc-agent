"""
cli.py

Runs the full pipeline end to end from the command line, no UI needed:

    python cli.py [--case data/case_information.txt] [--out outputs/]
                  [--no-llm] [--inject-demo-error]

Writes outputs/generated_affidavit.docx and outputs/evaluation_report.md.
"""

import argparse
import os

from src.extractor import load_case_entities
from src.mapper import build_paragraphs
from src.docgen import generate_docx
from src.evaluator import evaluate


def main():
    ap = argparse.ArgumentParser(description="Legal Document Generation & Evaluation Agent")
    ap.add_argument("--case", default="data/case_information.txt")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--no-llm", action="store_true",
                     help="Skip the LLM polish step; use deterministic templates only.")
    ap.add_argument("--inject-demo-error", action="store_true",
                     help="Deliberately corrupt the output (respondent number + "
                          "verification count) to demonstrate the validation layer.")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"[1/5] Extracting entities from {args.case} ...")
    ce = load_case_entities(args.case)
    print(f"      -> {len(ce.reply_points)} reply points, "
          f"respondent No. {ce.respondent_number}")

    print("[2/5] Mapping + generating paragraphs "
          f"({'LLM-assisted' if not args.no_llm else 'deterministic only'}) ...")
    paragraphs = build_paragraphs(ce, use_llm=not args.no_llm)
    print(f"      -> {len(paragraphs)} body paragraphs")

    docx_path = os.path.join(args.out, "generated_affidavit.docx")
    print(f"[3/5] Assembling document -> {docx_path}")
    generate_docx(ce, paragraphs, docx_path, inject_demo_error=args.inject_demo_error)

    print("[4/5] Running deterministic validation + scoring ...")
    report = evaluate(docx_path, ce, paragraphs)

    report_path = os.path.join(args.out, "evaluation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    print(f"[5/5] Evaluation report -> {report_path}")
    print()
    print(f"Overall Score: {report.overall:.0f}/100")
    for c in report.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}")


if __name__ == "__main__":
    main()
