"""
app.py

Streamlit UI for the Legal Document Generation & Evaluation Agent.
Run with: streamlit run app.py
"""

import os
import io
import streamlit as st

from src.extractor import extract_entities
from src.mapper import build_paragraphs
from src.docgen import generate_docx
from src.evaluator import evaluate

st.set_page_config(page_title="Legal Document Generation Agent", layout="wide")

st.title("Legal Document Generation & Evaluation Agent")
st.caption("Affidavit in Reply -- reference-driven generation with deterministic validation")

with st.sidebar:
    st.header("1. Case Information")
    default_path = os.path.join(os.path.dirname(__file__), "data", "case_information.txt")
    with open(default_path, encoding="utf-8") as f:
        default_text = f.read()

    source = st.radio("Input source", ["Use bundled sample case", "Paste / edit case information"])
    if source == "Paste / edit case information":
        case_text = st.text_area("Case information (same field format as the sample)",
                                  value=default_text, height=300)
    else:
        case_text = default_text
        with st.expander("View sample case information"):
            st.code(default_text, language="text")

    st.header("2. Generation options")
    use_llm = st.checkbox(
        "Use LLM to polish paragraph wording (requires ANTHROPIC_API_KEY)",
        value=bool(os.environ.get("ANTHROPIC_API_KEY")),
    )
    if use_llm and not os.environ.get("ANTHROPIC_API_KEY"):
        st.info("No ANTHROPIC_API_KEY set -- falling back to deterministic templates "
                 "(this is the 'pre-run / cached' demo mode).")

    st.header("3. Demo")
    inject_error = st.checkbox(
        "Inject a demo error (mismatched respondent number + verification count)",
        value=False,
        help="Use this to show the validation layer catching a real mistake.",
    )

    run = st.button("Generate Affidavit", type="primary")

if run:
    with st.spinner("Extracting entities..."):
        ce = extract_entities(case_text)

    if not ce.reply_points:
        st.error("Could not parse any reply points from the case information. Check the "
                  "field format against the sample.")
        st.stop()

    with st.spinner("Mapping and generating paragraphs..."):
        paragraphs = build_paragraphs(ce, use_llm=use_llm)

    out_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    docx_path = os.path.join(out_dir, "generated_affidavit.docx")

    with st.spinner("Assembling document..."):
        generate_docx(ce, paragraphs, docx_path, inject_demo_error=inject_error)

    with st.spinner("Running validation + scoring..."):
        report = evaluate(docx_path, ce, paragraphs)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Generated Affidavit")
        st.write(f"**{len(paragraphs)} body paragraphs** mapped from "
                 f"**{len(ce.reply_points)} reply points**.")
        with open(docx_path, "rb") as f:
            st.download_button("Download generated_affidavit.docx", f,
                                file_name="generated_affidavit.docx")
        with st.expander("Preview paragraph text", expanded=True):
            for p in paragraphs:
                st.markdown(f"**{p.number}.** {p.text}")

    with col2:
        st.subheader("Evaluation Report")
        score_color = "green" if report.overall >= 85 else (
            "orange" if report.overall >= 60 else "red")
        st.markdown(f"### Overall Score: :{score_color}[{report.overall:.0f}/100]")

        for dim, score in report.dimension_scores.items():
            st.progress(min(int(score), 100), text=f"{dim}: {score:.0f}/100")

        st.markdown("#### Deterministic checks")
        for c in report.checks:
            icon = "✅" if c.passed else "❌"
            st.markdown(f"{icon} **{c.name}** -- {c.message}")
            st.caption(f"Source: {c.source}")

        st.markdown("#### Issues Detected")
        if report.issues:
            for i, issue in enumerate(report.issues, 1):
                st.markdown(f"{i}. {issue}")
        else:
            st.markdown("None.")

        report_md = report.to_markdown()
        st.download_button("Download evaluation_report.md", report_md,
                            file_name="evaluation_report.md")
else:
    st.info("Set your options in the sidebar and click **Generate Affidavit**.")
    st.markdown("""
    **What this does:**
    1. Reads the reference affidavit's structure (encoded in `src/schema.py`, extracted from
       the supplied format document).
    2. Extracts entities and reply points from the case information (`src/extractor.py`).
    3. Maps reply points to numbered paragraphs and generates their text, deterministically
       or with optional LLM polishing (`src/mapper.py`).
    4. Assembles a formatted `.docx` following the reference structure (`src/docgen.py`).
    5. Runs deterministic validation checks -- no LLM involved -- and produces a scored
       evaluation report (`src/validator.py`, `src/evaluator.py`).
    """)
