import io
import unittest

from docx import Document
from pypdf import PdfReader

from report_generator import create_pdf_report, create_report


class ReportGeneratorTests(unittest.TestCase):
    def test_report_includes_structured_difference_details(self):
        comparison_result = {
            "document_a_summary": "Original policy",
            "document_b_summary": "Updated policy",
            "similarities": ["Both documents describe leave policy."],
            "differences": [
                {
                    "title": "Notice period",
                    "category": "Change",
                    "severity": "High",
                    "description": "The required notice period increased.",
                    "document_a": "10 days",
                    "document_b": "30 days",
                }
            ],
            "key_details": [],
            "overall_conclusion": "The updated policy requires more notice.",
            "limitations": [],
            "risk_flags": [],
            "deadlines": [],
            "source_citations": [],
        }

        report_file = create_report(comparison_result, "old.pdf", "new.pdf")
        document = Document(io.BytesIO(report_file.getvalue()))
        report_text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        self.assertIn("Notice period (Change; High)", report_text)
        self.assertIn("The required notice period increased.", report_text)
        self.assertIn("Document A: 10 days", report_text)
        self.assertIn("Document B: 30 days", report_text)
        self.assertNotIn("titlecategoryseveritydescriptiondocument_adocument_b", report_text)

    def test_pdf_report_includes_findings_and_escapes_markup(self):
        comparison_result = {
            "document_a_summary": "Original policy",
            "document_b_summary": "Updated policy",
            "similarities": ["Both documents cover payment terms."],
            "differences": [
                {
                    "title": "Payment & notice <period>",
                    "category": "Change",
                    "severity": "High",
                    "description": "Notice increased from 10 to 30 days.",
                    "document_a": "10 days",
                    "document_b": "30 days",
                }
            ],
            "key_details": [],
            "overall_conclusion": "The notice period increased.",
            "limitations": ["The full agreement was not provided."],
            "risk_flags": ["A longer notice period may delay termination."],
            "deadlines": ["Give notice 30 days before termination."],
            "source_citations": [
                {
                    "finding": "Notice period",
                    "source": "Document B",
                    "quote": "Notice must be given 30 days in advance.",
                }
            ],
        }

        report_file = create_pdf_report(comparison_result, "old.pdf", "new.pdf")
        pdf_bytes = report_file.getvalue()
        extracted_text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf_bytes)).pages
        )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertIn("Payment & notice <period>", extracted_text)
        self.assertIn("Notice increased from 10 to 30 days.", extracted_text)
        self.assertIn("30 days before termination", extracted_text)
        self.assertIn("Notice must be given 30 days in advance.", extracted_text)


if __name__ == "__main__":
    unittest.main()
