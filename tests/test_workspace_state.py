import unittest

from workspace_state import WORKSPACE_STATE_KEYS, clear_workspace_state


class WorkspaceStateTests(unittest.TestCase):
    def test_clear_workspace_removes_temporary_state_and_resets_mode(self):
        state = {key: "temporary" for key in WORKSPACE_STATE_KEYS}
        state["analysis_mode"] = "Ask your document"
        state["profile_setting"] = "keep"

        clear_workspace_state(state)

        for key in WORKSPACE_STATE_KEYS:
            self.assertNotIn(key, state)
        self.assertEqual(state["analysis_mode"], "Compare two documents")
        self.assertEqual(state["profile_setting"], "keep")


if __name__ == "__main__":
    unittest.main()
