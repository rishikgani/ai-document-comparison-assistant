import unittest

from comparison import (
    COMPARISON_MODELS,
    COMPARISON_RETRY_ATTEMPTS,
    _is_model_unavailable_error,
    _is_retryable_error,
)


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


if __name__ == "__main__":
    unittest.main()
