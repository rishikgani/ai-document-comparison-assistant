import unittest

from demo_data import get_guided_demo


class GuidedDemoTests(unittest.TestCase):
    def test_citations_are_grounded_in_the_sample_documents(self):
        demo = get_guided_demo()
        sources = {
            "Document A": demo["document_a_text"],
            "Document B": demo["document_b_text"],
        }

        self.assertTrue(demo["comparison_result"]["differences"])
        for citation in demo["comparison_result"]["source_citations"]:
            self.assertIn(citation["quote"], sources[citation["source"]])

    def test_each_call_returns_independent_comparison_data(self):
        first = get_guided_demo()
        second = get_guided_demo()

        first["comparison_result"]["similarities"].append("temporary")

        self.assertNotIn(
            "temporary",
            second["comparison_result"]["similarities"],
        )


if __name__ == "__main__":
    unittest.main()
