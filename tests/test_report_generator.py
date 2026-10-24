import io
import unittest

from docx import Document

from report_generator import create_report


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


if __name__ == "__main__":
    unittest.main()
