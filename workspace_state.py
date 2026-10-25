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
    "selected_view",
    "comparison_question_input",
    "comparison_result",
    "comparison_document_chat",
    "comparison_document_texts",
    "single_analysis_result",
    "document_chat",
    "suggested_question",
    "suggested_comparison_question",
    "difference_severity_filter",
    "difference_category_filter",
    "clear_comparison_chat",
    "_document_extraction_cache",
    "_document_ocr_cache",
)


def clear_workspace_state(state) -> None:
    """Clear uploaded documents and generated results from a state mapping."""

    for key in WORKSPACE_STATE_KEYS:
        state.pop(key, None)
    state["workspace_reset_id"] = state.get("workspace_reset_id", 0) + 1
    state["analysis_mode"] = "Compare two documents"
