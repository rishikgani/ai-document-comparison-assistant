"""Helpers for resetting temporary workspace state."""


WORKSPACE_STATE_KEYS = (
    "document_a",
    "document_b",
    "single_document",
    "question_document",
    "document_question_input",
    "selected_file_names",
    "selected_single_name",
    "selected_question_name",
    "comparison_result",
    "single_analysis_result",
    "document_chat",
    "suggested_question",
    "_document_extraction_cache",
    "_document_ocr_cache",
)


def clear_workspace_state(state) -> None:
    """Clear uploaded documents and generated results from a state mapping."""

    for key in WORKSPACE_STATE_KEYS:
        state.pop(key, None)
    state["analysis_mode"] = "Compare two documents"
