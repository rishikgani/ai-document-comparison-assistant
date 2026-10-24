from io import BytesIO

from docx import Document


def create_report(comparison_result, document_a_name, document_b_name):
    """Create a Word report from the comparison result."""

    report = Document()

    report.add_heading(
        "AI Document Comparison Report",
        level=0,
    )

    report.add_paragraph(
        f"Document A: {document_a_name}"
    )

    report.add_paragraph(
        f"Document B: {document_b_name}"
    )

    report.add_heading("Document A summary", level=1)
    report.add_paragraph(
        comparison_result["document_a_summary"]
    )

    report.add_heading("Document B summary", level=1)
    report.add_paragraph(
        comparison_result["document_b_summary"]
    )

    report.add_heading("Similarities", level=1)

    for similarity in comparison_result["similarities"]:
        report.add_paragraph(
            similarity,
            style="List Bullet",
        )

    report.add_heading("Differences", level=1)

    for difference in comparison_result["differences"]:
        if isinstance(difference, dict):
            title = difference.get("title", "Document change")
            category = difference.get("category", "Change")
            severity = difference.get("severity", "Medium")
            description = difference.get(
                "description",
                "No explanation provided.",
            )
            document_a = difference.get(
                "document_a",
                "Not found in the provided text.",
            )
            document_b = difference.get(
                "document_b",
                "Not found in the provided text.",
            )

            report.add_paragraph(
                f"{title} ({category}; {severity})",
                style="List Bullet",
            )
            report.add_paragraph(description)
            report.add_paragraph(f"Document A: {document_a}")
            report.add_paragraph(f"Document B: {document_b}")
        else:
            report.add_paragraph(
                str(difference),
                style="List Bullet",
            )

    report.add_heading("Key details", level=1)

    for detail in comparison_result["key_details"]:
        report.add_paragraph(
            f"Field: {detail.get('field', 'Unknown')}",
            style="List Bullet",
        )
        report.add_paragraph(
            f"Document A: {detail.get('document_a', 'Not found')}"
        )
        report.add_paragraph(
            f"Document B: {detail.get('document_b', 'Not found')}"
        )

    report.add_heading("Overall conclusion", level=1)
    report.add_paragraph(
        comparison_result["overall_conclusion"]
    )

    report.add_heading("Limitations", level=1)

    for limitation in comparison_result["limitations"]:
        report.add_paragraph(
            limitation,
            style="List Bullet",
        )

    report.add_heading("Risk flags", level=1)
    for risk in comparison_result.get("risk_flags", []):
        report.add_paragraph(risk, style="List Bullet")

    report.add_heading("Deadlines", level=1)
    for deadline in comparison_result.get("deadlines", []):
        report.add_paragraph(deadline, style="List Bullet")

    report.add_heading("Source citations", level=1)
    for citation in comparison_result.get("source_citations", []):
        report.add_paragraph(
            f"{citation.get('finding', 'Finding')} ({citation.get('source', 'Source')})",
            style="List Bullet",
        )
        report.add_paragraph(f"\"{citation.get('quote', 'Quote unavailable')}\"")

    output = BytesIO()
    report.save(output)
    output.seek(0)

    return output
