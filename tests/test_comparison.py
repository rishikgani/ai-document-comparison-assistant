import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comparison import (
    COMPARISON_MODELS,
    COMPARISON_RETRY_ATTEMPTS,
    _is_model_unavailable_error,
    _is_retryable_error,
    _normalize_response_text,
    _validate_comparison_result,
    compare_documents,
)


def _valid_comparison_result():
    return {
        "document_a_summary": "Original policy.",
        "document_b_summary": "Updated policy.",
        "similarities": [],
        "differences": [
            {
                "title": "Notice period",
                "category": "Change",
                "severity": "Medium",
                "description": "The notice period changed.",
                "document_a": "10 days",
                "document_b": "30 days",
            }
        ],
        "key_details": [
            {
                "field": "Notice period",
                "document_a": "10 days",
                "document_b": "30 days",
            }
        ],
        "overall_conclusion": "The notice period increased.",
        "limitations": [],
        "risk_flags": [],
        "deadlines": [],
        "source_citations": [
            {
                "finding": "Notice period",
                "quote": "Notice must be given 30 days in advance.",
                "source": "Document B",
            }
        ],
    }


class ComparisonRetryTests(unittest.TestCase):
    def test_retries_temporary_gemini_unavailable_errors(self):
        self.assertTrue(_is_retryable_error(RuntimeError("503 UNAVAILABLE")))
        self.assertTrue(_is_retryable_error(RuntimeError("429 RESOURCE_EXHAUSTED")))
        self.assertTrue(_is_retryable_error(RuntimeError("DEADLINE_EXCEEDED")))

    def test_does_not_retry_configuration_errors(self):
        self.assertFalse(_is_retryable_error(RuntimeError("invalid API key")))

    def test_skips_models_that_are_not_available_to_the_account(self):
        self.assertTrue(_is_model_unavailable_error(RuntimeError("404 NOT_FOUND")))
        self.assertTrue(_is_model_unavailable_error(RuntimeError("model is no longer available")))

    def test_has_a_documented_fallback_model(self):
        self.assertEqual(
            COMPARISON_MODELS,
            ("gemini-3.5-flash-lite", "gemini-3.8-flash"),
        )
        self.assertEqual(COMPARISON_RETRY_ATTEMPTS, 2)

    def test_normalizes_markdown_json_responses(self):
        self.assertEqual(
            _normalize_response_text("```json\n{\"answer\": \"ok\"}\n```"),
            '{"answer": "ok"}',
        )
        self.assertEqual(
            _normalize_response_text("  ```\n{\"status\": \"ready\"}\n```  "),
            '{"status": "ready"}',
        )

    def test_validates_comparison_result_fields_and_types(self):
        result = _valid_comparison_result()

        self.assertIs(_validate_comparison_result(result), result)

    def test_rejects_incomplete_or_malformed_comparison_results(self):
        incomplete_result = _valid_comparison_result()
        del incomplete_result["overall_conclusion"]
        malformed_difference = _valid_comparison_result()
        malformed_difference["differences"][0]["severity"] = "Urgent"
        malformed_citation = _valid_comparison_result()
        malformed_citation["source_citations"][0]["source"] = "Document C"

        for result in ([], incomplete_result, malformed_difference, malformed_citation):
            with self.subTest(result=result):
                with self.assertRaisesRegex(RuntimeError, "unexpected structure"):
                    _validate_comparison_result(result)

    def test_retries_temporary_api_errors_and_validates_the_response(self):
        client = Mock()
        client.models.generate_content.side_effect = [
            RuntimeError("503 UNAVAILABLE"),
            SimpleNamespace(text=json.dumps(_valid_comparison_result())),
        ]
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("comparison._get_client", return_value=client),
            patch("comparison.time.sleep"),
        ):
            result = compare_documents("old policy", "new policy")

        self.assertEqual(client.models.generate_content.call_count, 2)
        self.assertEqual(result["overall_conclusion"], "The notice period increased.")

    def test_rejects_malformed_json_from_the_api(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text="not json")
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("comparison._get_client", return_value=client),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid comparison response"):
                compare_documents("old policy", "new policy")


if __name__ == "__main__":
    unittest.main()
