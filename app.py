import hashlib

import streamlit as st

from comparison import (
    analyze_document,
    ask_compared_documents,
    ask_document,
    compare_documents,
    transcribe_pdf_with_gemini,
)
from document_reader import MAX_TEXT_CHARACTERS, extract_text
from report_generator import create_report
from user_data import (
    get_avatar,
    get_all_history,
    get_host_summary,
    get_history,
    has_seen_workspace_reminder,
    initialize_database,
    mark_workspace_reminder_seen,
    save_avatar,
    save_comparison,
)
from workspace_state import clear_workspace_state


AVATAR_OPTIONS = {
    "Neon orb": "assets/avatar-neon-orb.svg",
    "Synth bot": "assets/avatar-synth-bot.svg",
    "Nova": "assets/avatar-nova.svg",
    "Prism": "assets/avatar-prism.svg",
    "Cyber eye": "assets/avatar-cyber-eye.svg",
    "Glitch": "assets/avatar-glitch.svg",
    "Rocket": "assets/avatar-rocket.svg",
    "Moon": "assets/avatar-moon.svg",
    "Flux": "assets/avatar-flux.svg",
}


class _UploadedFilePayload:
    """Small file-like adapter used by the cached extraction function."""

    def __init__(self, name: str, file_bytes: bytes):
        self.name = name
        self._file_bytes = file_bytes

    def getvalue(self) -> bytes:
        return self._file_bytes


def _uploaded_file_cache_key(uploaded_file, file_bytes: bytes) -> str:
    """Build a cheap per-session key without hashing the full file contents."""

    file_id = getattr(uploaded_file, "file_id", None)
    if file_id:
        return f"{file_id}:{uploaded_file.name}"
    return f"{uploaded_file.name}:{len(file_bytes)}"


def _comparison_cache_key(document_a_text: str, document_b_text: str) -> str:
    """Create a stable, user-local key without retaining document text in the key."""

    content = f"{document_a_text}\x00{document_b_text}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _get_cached_comparison(document_a_text: str, document_b_text: str):
    """Return a comparison cached in this browser session, if available."""

    cache = st.session_state.setdefault("_comparison_results_cache", {})
    return cache.get(_comparison_cache_key(document_a_text, document_b_text))


def _cache_comparison(document_a_text: str, document_b_text: str, result):
    """Store a bounded comparison cache for fast repeat analysis in this session."""

    cache = st.session_state.setdefault("_comparison_results_cache", {})
    cache[_comparison_cache_key(document_a_text, document_b_text)] = result
    while len(cache) > 5:
        cache.pop(next(iter(cache)))


def extract_text_cached(file_name: str, file_bytes: bytes, cache_key: str):
    """Cache document parsing in the current session without hashing file bytes."""

    extraction_cache = st.session_state.setdefault("_document_extraction_cache", {})
    if cache_key in extraction_cache:
        return extraction_cache[cache_key]

    result = extract_text(_UploadedFilePayload(file_name, file_bytes))
    extraction_cache[cache_key] = result
    return result


def transcribe_scanned_pdf_cached(pdf_bytes: bytes, cache_key: str) -> str:
    """Cache scanned-PDF OCR in the current session."""

    ocr_cache = st.session_state.setdefault("_document_ocr_cache", {})
    if cache_key in ocr_cache:
        return ocr_cache[cache_key]

    result = transcribe_pdf_with_gemini(pdf_bytes)
    ocr_cache[cache_key] = result
    return result


def get_host_emails() -> set[str]:
    """Return the signed-in host allowlist from Streamlit secrets."""
    app_settings = st.secrets.get("app", {})
    return {
        email.strip().lower()
        for email in app_settings.get("host_emails", [])
        if email.strip()
    }


def extract_document_with_ocr_fallback(uploaded_file, defer_vision=False):
    """Extract text normally, then use Gemini vision for scanned PDFs."""

    file_bytes = uploaded_file.getvalue()
    cache_key = _uploaded_file_cache_key(uploaded_file, file_bytes)
    try:
        return extract_text_cached(uploaded_file.name, file_bytes, cache_key)
    except ValueError as error:
        is_pdf = uploaded_file.name.lower().endswith(".pdf")
        is_scanned_pdf = "No readable text was found in this PDF" in str(error)
        if not (is_pdf and is_scanned_pdf):
            raise

        if defer_vision:
            return {
                "text": "",
                "unit_label": "Visual PDF",
                "unit_count": "Scanned pages",
                "character_count": 0,
                "file_type": "Scanned PDF",
                "pdf_bytes": file_bytes,
            }

        with st.status(
            f"AI is reading scanned pages in {uploaded_file.name}...",
            expanded=True,
        ) as ocr_status:
            render_detective_loader()
            st.write(":material/visibility: Inspecting the scanned page images")
            st.write(":material/text_snippet: Recovering readable document text")
            st.caption("This may take a little longer because the PDF has no embedded text.")
            ocr_text = transcribe_scanned_pdf_cached(file_bytes, cache_key)
            if len(ocr_text) > MAX_TEXT_CHARACTERS:
                raise ValueError(
                    f"The scanned PDF produced too much text ({len(ocr_text):,} characters). "
                    f"Please split it into smaller files. The limit is {MAX_TEXT_CHARACTERS:,} characters."
                )
            ocr_status.update(
                label="Scanned pages ready",
                state="complete",
                expanded=False,
            )
        return {
            "text": ocr_text,
            "unit_label": "OCR characters",
            "unit_count": len(ocr_text.splitlines()),
            "character_count": len(ocr_text),
            "file_type": "Scanned PDF",
        }


def render_detective_loader():
    """Render a small animated visual while a Gemini request is running."""

    st.markdown(
        """
        <div class="detective-loader" aria-label="Document Detective is analyzing">
            <span class="detective-icon">🔎</span>
            <span><strong>Document Detective</strong><br><span class="detective-dots">Following the clues</span></span>
            <span class="detective-scan"></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def normalize_difference(item):
    """Keep the results view compatible with older string-only AI responses."""

    if isinstance(item, dict):
        return {
            "title": item.get("title", "Document change"),
            "category": item.get("category", "Change"),
            "severity": item.get("severity", "Medium"),
            "description": item.get("description", "No explanation provided."),
            "document_a": item.get("document_a", "Not found in the provided text."),
            "document_b": item.get("document_b", "Not found in the provided text."),
        }

    return {
        "title": "Document change",
        "category": "Change",
        "severity": "Medium",
        "description": str(item),
        "document_a": "See the evidence section below.",
        "document_b": "See the evidence section below.",
    }


st.set_page_config(
    page_title="AI Document Comparison Assistant",
    page_icon="📄",
)

st.logo(
    "assets/doc-compare-mark.svg",
    size="medium",
    icon_image="assets/doc-compare-mark.svg",
)
st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 8% 0%, rgba(45, 212, 191, 0.08), transparent 25%),
            radial-gradient(circle at 94% 5%, rgba(59, 130, 246, 0.09), transparent 28%),
            #07111f;
        background-attachment: fixed;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stImage"] img[alt="Doc Compare logo"] {
        filter: drop-shadow(0 0 12px rgba(45, 212, 191, 0.18));
        margin: 0.25rem 0 1.25rem;
    }

    [data-testid="stImage"]:has(img[alt="Doc Compare logo"]) {
        display: flex;
        justify-content: center;
    }

    h1, h2, h3 {
        color: #e6edf5 !important;
        letter-spacing: -0.35px;
    }

    p, label, .stMarkdown {
        color: #b8c7d8;
    }

    [data-testid="stFileUploader"],
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(13, 27, 42, 0.82);
        border: 1px solid #1e3a50;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
    }

    .stButton > button,
    .stDownloadButton > button {
        background: #14b8a6;
        color: #03131a !important;
        border: 1px solid #5eead4;
        border-radius: 9px;
        font-weight: 600;
        transition: all 0.2s ease;
        box-shadow: 0 4px 14px rgba(20, 184, 166, 0.16);
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: #99f6e4;
        box-shadow: 0 6px 20px rgba(45, 212, 191, 0.28);
        transform: translateY(-1px);
    }

    [data-testid="stFileUploader"] section {
        background: rgba(7, 17, 31, 0.78);
        border: 1px dashed #2d6b7e;
        border-radius: 9px;
    }

    [data-testid="stSidebar"] {
        background: #081522;
        border-right: 1px solid #1e3a50;
    }

    hr {
        border-color: #1e3a50;
    }

    .detective-loader {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin: 0.35rem 0 0.75rem;
        padding: 0.75rem 0.9rem;
        border: 1px solid rgba(45, 212, 191, 0.28);
        border-radius: 10px;
        background: rgba(8, 21, 34, 0.72);
        color: #b8c7d8;
    }

    .detective-icon {
        font-size: 1.5rem;
        animation: detective-bob 1.4s ease-in-out infinite;
    }

    .detective-scan {
        flex: 1;
        height: 0.35rem;
        overflow: hidden;
        border-radius: 999px;
        background: #163047;
    }

    .detective-scan::after {
        display: block;
        width: 42%;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #14b8a6, #5eead4);
        content: "";
        animation: detective-scan 1.7s ease-in-out infinite;
    }

    .detective-dots::after {
        content: "...";
        display: inline-block;
        width: 1.2rem;
        overflow: hidden;
        vertical-align: bottom;
        animation: detective-dots 1.2s steps(4, end) infinite;
    }

    @keyframes detective-bob {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
    }

    @keyframes detective-scan {
        0% { transform: translateX(-120%); }
        100% { transform: translateX(280%); }
    }

    @keyframes detective-dots {
        0% { width: 0; }
        100% { width: 1.2rem; }
    }

    #MainMenu {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
with st.container(horizontal_alignment="center"):
    st.image(
        "assets/doc-compare-logo.svg",
        width=420,
        alt="Doc Compare logo",
    )

if not st.user.is_logged_in:
    hero_column, creator_column = st.columns([1.55, 1], gap="large")

    with hero_column:
        st.caption("AI-ASSISTED DOCUMENT REVIEW")
        st.title("Understand what changed.\nMove forward with confidence.", anchor=False)
        st.write(
            "Doc Compare helps you review two documents side by side, surface meaningful changes, "
            "and turn your findings into a clear report."
        )
        st.success(
            "Built for contracts, policies, proposals, requirements, and everyday document reviews.",
            icon=":material/verified:",
        )

    with creator_column:
        with st.container(border=True):
            st.caption("ABOUT THIS WORKSPACE")
            st.subheader("Simple, focused, useful", anchor=False)
            st.write(
                "Upload a source document and its counterpart. The workspace extracts the text, "
                "compares the content with Gemini, and organizes the results into practical sections."
            )
            st.divider()
            st.caption("ABOUT THE CREATOR")
            st.markdown("### Velugu Rishik Gani")
            st.caption("B.Tech graduate · AI and Python enthusiast")
            st.write(
                "I created Doc Compare to reduce the time people spend reading and understanding "
                "what documents are really saying. With a foundation in Python and artificial "
                "intelligence, I built this workspace to make document review faster, clearer, "
                "and more approachable."
            )

    st.header("What you can do", anchor=False, icon=":material/auto_awesome:")
    feature_columns = st.columns(3)
    features = [
        ("Compare clearly", "See summaries, similarities, and meaningful differences in one place.", ":material/compare_arrows:"),
        ("Find key details", "Review names, dates, amounts, requirements, and missing information.", ":material/manage_search:"),
        ("Take it with you", "Download a polished Word report for sharing or continued review.", ":material/download:") ,
    ]
    for feature_column, (title, description, icon) in zip(feature_columns, features):
        with feature_column:
            with st.container(border=True, height="stretch"):
                st.subheader(title, anchor=False, icon=icon)
                st.write(description)

    st.header("Get started", anchor=False, icon=":material/login:")
    st.caption("Sign in securely to open your private comparison workspace.")
    google_column, microsoft_column = st.columns(2)

    with google_column:
        with st.container(border=True):
            st.subheader("Google", anchor=False, icon=":material/account_circle:")
            st.write("Use your Google account to create an account or sign in.")
            if st.button(
                "Continue with Google",
                type="primary",
                width="stretch",
                icon=":material/login:",
            ):
                st.login("google")

    with microsoft_column:
        with st.container(border=True):
            st.subheader("Microsoft", anchor=False, icon=":material/business:")
            st.write("Use your Microsoft account to create an account or sign in.")
            if st.button(
                "Continue with Microsoft",
                width="stretch",
                icon=":material/login:",
            ):
                st.login("microsoft")

    st.info(
        "Your password is handled by Google or Microsoft. This app never sees or stores it. Uploaded files are not stored.",
        icon=":material/security:",
    )
    st.stop()

user_email = getattr(st.user, "email", "").strip().lower()
is_host = user_email in get_host_emails()
account_role = "Host" if is_host else "User"
initialize_database()

# Show this onboarding reminder once per account, even after the user returns
# in a new browser session. The button also works when another view is open.
if not has_seen_workspace_reminder(user_email):
    st.success(
        "You're signed in. You can start your document work in the workspace now.",
        icon=":material/check_circle:",
    )
    if st.button(
        "Open workspace",
        type="primary",
        icon=":material/arrow_forward:",
    ):
        st.session_state["selected_view"] = "Workspace"
    mark_workspace_reminder_seen(user_email)

selected_avatar = get_avatar(user_email)

with st.sidebar:
    st.image(AVATAR_OPTIONS[selected_avatar], width=52, alt="Profile avatar")
    st.caption(f"Signed in as {st.user.email}")
    if is_host:
        st.success("Host account", icon=":material/admin_panel_settings:")
    else:
        st.info("User account", icon=":material/person:")
    navigation_options = ["Workspace", "History", "Profile"]
    if is_host:
        navigation_options.append("Host dashboard")
    selected_view = st.segmented_control(
        "Navigation",
        navigation_options,
        default="Workspace",
        key="selected_view",
    )
    if st.button("Sign out", width="stretch", icon=":material/logout:"):
        st.logout()

if selected_view == "History":
    st.header("Comparison history", anchor=False, icon=":material/history:")
    st.caption("Your recent comparisons are private to your signed-in account.")
    history = get_history(user_email)

    if not history:
        st.info(
            "No comparisons yet. Your completed comparisons will appear here.",
            icon=":material/history_toggle_off:",
        )
    else:
        for record in history:
            with st.container(border=True):
                st.subheader(
                    f"{record['document_a']}  ↔  {record['document_b']}",
                    anchor=False,
                    icon=":material/compare_arrows:",
                )
                st.caption(record["created_at"].replace("T", " ") + " UTC")
                st.write(record["conclusion"])
    st.stop()

if selected_view == "Profile":
    st.header("Your profile", anchor=False, icon=":material/account_circle:")
    st.caption("Your identity comes from the provider you used to sign in.")

    profile_column, details_column = st.columns([1, 2])
    with profile_column:
        st.image(AVATAR_OPTIONS[selected_avatar], width=160, alt="Selected profile avatar")
        st.subheader(getattr(st.user, "name", "Signed-in user"), anchor=False)

        st.caption("Choose any avatar you like. Your selection is saved to your account.")

        avatar_items = list(AVATAR_OPTIONS.items())
        for start in range(0, len(avatar_items), 3):
            avatar_columns = st.columns(3)
            for avatar_column, (avatar_name, avatar_path) in zip(
                avatar_columns,
                avatar_items[start : start + 3],
            ):
                with avatar_column:
                    st.image(avatar_path, width=105, alt=f"{avatar_name} avatar")
                    if st.button(
                        avatar_name,
                        key=f"choose_avatar_{avatar_name}",
                        type="primary" if avatar_name == selected_avatar else "secondary",
                        width="stretch",
                    ):
                        save_avatar(user_email, avatar_name)
                        st.rerun()

    with details_column:
        with st.container(border=True):
            st.write(f"**Email**  {st.user.email}")
            st.write(f"**Account type**  {account_role}")
            st.write(f"**Comparisons saved**  {len(get_history(user_email))}")
            st.caption("Only comparison metadata and conclusions are saved. Uploaded files are not stored.")
    st.stop()

if selected_view == "Host dashboard" and is_host:
    st.header("Host dashboard", anchor=False, icon=":material/admin_panel_settings:")
    st.caption("A private overview of activity across all signed-in users.")

    summary = get_host_summary()
    user_metric, comparison_metric = st.columns(2)
    user_metric.metric("Users with comparisons", summary["users"])
    comparison_metric.metric("Total comparisons", summary["comparisons"])

    st.subheader("Recent activity", anchor=False, icon=":material/monitoring:")
    all_history = get_all_history()
    if not all_history:
        st.info("No user comparisons have been completed yet.", icon=":material/history_toggle_off:")
    else:
        for record in all_history:
            with st.container(border=True):
                st.caption(record["created_at"].replace("T", " ") + " UTC")
                st.markdown(
                    f"**{record['user_email']}** · {record['document_a']}  ↔  {record['document_b']}"
                )
                st.write(record["conclusion"])
    st.stop()

st.title("Document comparison workspace", anchor=False)

clear_column, _ = st.columns([1, 4])
with clear_column:
    st.button(
        "Clear workspace",
        on_click=clear_workspace_state,
        args=(st.session_state,),
        width="stretch",
        icon=":material/delete_sweep:",
        help="Remove uploaded files and generated results from this session.",
    )

st.caption(
    f"{account_role} workspace · A focused place for understanding what changed between two documents."
)

if is_host:
    st.info(
        "You are signed in as a host. Use the Host dashboard in the sidebar to review workspace activity.",
        icon=":material/admin_panel_settings:",
    )

analysis_mode = st.segmented_control(
    "Choose a workflow",
    ["Compare two documents", "Understand one document", "Ask your document"],
    default="Compare two documents",
    key="analysis_mode",
)

if analysis_mode == "Ask your document":
    st.header("Ask your document", anchor=False, icon=":material/forum:")
    st.write("Ask a focused question and get a direct answer supported by evidence from your document.")

    with st.container(border=True):
        st.subheader("Your document", anchor=False, icon=":material/article:")
        st.caption("Upload a PDF, DOCX, or TXT file.")
        question_document = st.file_uploader(
            "Choose a document",
            type=["pdf", "docx", "txt"],
            key="question_document",
            label_visibility="collapsed",
        )

    selected_question_name = question_document.name if question_document is not None else None
    if st.session_state.get("selected_question_name") != selected_question_name:
        st.session_state["selected_question_name"] = selected_question_name
        st.session_state.pop("document_chat", None)

    if question_document is not None:
        try:
            extracted_question = extract_document_with_ocr_fallback(
                question_document,
                defer_vision=True,
            )
            chat_history = st.session_state.setdefault("document_chat", [])
            if not chat_history:
                suggestion = st.pills(
                    "Try asking",
                    [
                        "What is this document about?",
                        "What deadlines are mentioned?",
                        "What action do I need to take?",
                    ],
                    label_visibility="collapsed",
                )
                if suggestion:
                    st.session_state["suggested_question"] = suggestion

            question = st.chat_input(
                "Ask a question about this document",
                disabled=question_document is None,
                key="document_question_input",
            )
            question = question or st.session_state.pop("suggested_question", None)

            if question:
                chat_history.append({"role": "user", "content": question})
                try:
                    with st.status("AI is searching your document...", expanded=True) as question_status:
                        render_detective_loader()
                        st.write(":material/manage_search: Looking for the relevant passage")
                        st.write(":material/format_quote: Preparing an evidence-backed answer")
                        answer = ask_document(
                            extracted_question["text"],
                            question.strip(),
                            pdf_bytes=extracted_question.get("pdf_bytes"),
                        )
                        chat_history.append({"role": "assistant", "content": answer})
                        question_status.update(
                            label="Answer found",
                            state="complete",
                            expanded=False,
                        )
                except RuntimeError as error:
                    chat_history.append({
                        "role": "assistant",
                        "content": {
                            "answer": str(error),
                            "confidence": "Unavailable",
                            "citations": [],
                        },
                    })

            for message in chat_history:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                    continue

                response = message["content"]
                with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                    st.write(response["answer"])
                    st.caption(f"Confidence: {response.get('confidence', 'Not specified')}")
                    citations = response.get("citations", [])
                    if citations:
                        with st.expander("Evidence", icon=":material/format_quote:"):
                            for citation in citations:
                                st.caption(citation.get("source", "Document"))
                                st.write(f"\"{citation.get('quote', 'Quote unavailable')}\"")
        except (ValueError, RuntimeError) as error:
            st.error(str(error))

    st.stop()

if analysis_mode == "Understand one document":
    st.header("Understand one document", anchor=False, icon=":material/menu_book:")
    st.write(
        "Upload one document to get a plain-language explanation, key points, "
        "important details, and suggested action items."
    )

    with st.container(border=True):
        st.subheader("Your document", anchor=False, icon=":material/article:")
        st.caption("Upload a PDF, DOCX, or TXT file to begin.")
        single_document = st.file_uploader(
            "Choose a document",
            type=["pdf", "docx", "txt"],
            key="single_document",
            label_visibility="collapsed",
        )

    selected_single_name = single_document.name if single_document is not None else None
    if st.session_state.get("selected_single_name") != selected_single_name:
        st.session_state["selected_single_name"] = selected_single_name
        st.session_state.pop("single_analysis_result", None)

    if single_document is not None:
        try:
            extracted_single = extract_document_with_ocr_fallback(
                single_document,
                defer_vision=True,
            )
            st.success(
                f"Ready to analyze: {single_document.name}",
                icon=":material/check_circle:",
            )

            overview_column, preview_column = st.columns(2)
            with overview_column:
                with st.container(border=True):
                    st.subheader("Document overview", anchor=False, icon=":material/analytics:")
                    metric_one, metric_two = st.columns(2)
                    metric_one.metric(extracted_single["unit_label"], extracted_single["unit_count"])
                    metric_two.metric("Characters", f"{extracted_single['character_count']:,}")

            with preview_column:
                with st.container(border=True):
                    st.subheader("What you’ll receive", anchor=False, icon=":material/auto_awesome:")
                    st.write("A plain-language explanation, key points, important details, action items, and limitations.")

            with st.expander("Preview document text", icon=":material/preview:"):
                if extracted_single["text"]:
                    st.text(extracted_single["text"][:3000])
                else:
                    st.caption("This scanned PDF will be read visually when analysis starts.")

            if st.button(
                "Understand this document",
                type="primary",
                width="stretch",
                icon=":material/bolt:",
            ):
                with st.status(
                    "AI is reading your document...",
                    expanded=True,
                ) as analysis_status:
                    render_detective_loader()
                    st.write(":material/visibility: Reading the document pages")
                    st.write(":material/manage_search: Identifying key points and important details")
                    st.caption("Tip: The clearer the document, the more precise the explanation.")
                    try:
                        single_result = analyze_document(
                            extracted_single["text"],
                            pdf_bytes=extracted_single.get("pdf_bytes"),
                        )
                        st.session_state["single_analysis_result"] = single_result
                        save_comparison(
                            user_email,
                            single_document.name,
                            "Single-document analysis",
                            single_result["plain_language_explanation"],
                        )
                        analysis_status.update(
                            label="Analysis complete",
                            state="complete",
                            expanded=False,
                        )
                        st.success("Document analysis completed successfully.")
                    except RuntimeError as error:
                        analysis_status.update(
                            label="Analysis needs attention",
                            state="error",
                            expanded=True,
                        )
                        st.error(str(error))
        except (ValueError, RuntimeError) as error:
            st.error(str(error))

    single_result = st.session_state.get("single_analysis_result")
    if single_result:
        st.header("Document explanation", anchor=False, icon=":material/insights:")
        st.info(single_result["plain_language_explanation"], icon=":material/lightbulb:")

        points_column, actions_column = st.columns(2)
        with points_column:
            with st.container(border=True, height="stretch"):
                st.subheader("Key points", anchor=False, icon=":material/check_circle:")
                for item in single_result["key_points"]:
                    st.markdown(f":material/check_circle: {item}")
        with actions_column:
            with st.container(border=True, height="stretch"):
                st.subheader("Action items", anchor=False, icon=":material/task_alt:")
                if single_result["action_items"]:
                    for item in single_result["action_items"]:
                        st.markdown(f":material/arrow_forward: {item}")
                else:
                    st.caption("No explicit action items were found.")

        with st.container(border=True):
            st.subheader("Important details", anchor=False, icon=":material/list_alt:")
            if single_result["important_details"]:
                st.table(single_result["important_details"])
            else:
                st.caption("No specific dates, amounts, names, or requirements were identified.")

        if single_result["limitations"]:
            with st.container(border=True):
                st.subheader("Limitations and missing information", anchor=False, icon=":material/info:")
                for item in single_result["limitations"]:
                    st.markdown(f":material/warning: {item}")

    st.stop()

st.header("Start a comparison", anchor=False, icon=":material/compare_arrows:")
st.write("Upload a source document and its counterpart to identify what changed and what stayed consistent.")

left_column, right_column = st.columns(2)

with left_column:
    with st.container(border=True):
        st.subheader("Document A", anchor=False, icon=":material/article:")
        st.caption("Your first reference document")
        document_a = st.file_uploader(
            "Choose a file",
            type=["pdf", "docx", "txt"],
            key="document_a",
            label_visibility="collapsed",
        )

with right_column:
    with st.container(border=True):
        st.subheader("Document B", anchor=False, icon=":material/article:")
        st.caption("The document you want to compare")
        document_b = st.file_uploader(
            "Choose a file",
            type=["pdf", "docx", "txt"],
            key="document_b",
            label_visibility="collapsed",
        )

st.caption("PDF, DOCX, and TXT supported · Files are processed for this session and are not stored.")

selected_file_names = (
    document_a.name if document_a is not None else None,
    document_b.name if document_b is not None else None,
)

if st.session_state.get("selected_file_names") != selected_file_names:
    st.session_state["selected_file_names"] = selected_file_names
    st.session_state.pop("comparison_result", None)
    st.session_state.pop("comparison_document_chat", None)
    st.session_state.pop("comparison_document_texts", None)

if document_a is not None or document_b is not None:
    selected_files = []
    if document_a is not None:
        selected_files.append(f"A · {document_a.name}")
    if document_b is not None:
        selected_files.append(f"B · {document_b.name}")
    st.success("Files ready: " + "  ·  ".join(selected_files), icon=":material/check_circle:")

if document_a is not None and document_b is not None:
    st.header("Ready for analysis", anchor=False, icon=":material/auto_awesome:")
    st.write(
        "Your files are ready. Text extraction and AI comparison will start only when you click the button."
    )

    if st.button(
        "Compare documents",
        type="primary",
        width="stretch",
        icon=":material/bolt:",
    ):
        with st.status(
            "Preparing your documents...",
            expanded=True,
        ) as comparison_status:
            render_detective_loader()
            try:
                st.write(":material/description: Reading both documents")
                comparison_input_a = extract_document_with_ocr_fallback(document_a)
                comparison_input_b = extract_document_with_ocr_fallback(document_b)
                comparison_status.update(
                    label="Documents ready; AI is comparing them...",
                    state="running",
                    expanded=True,
                )
                st.write(":material/compare_arrows: Checking similarities and differences")
                st.write(":material/priority_high: Looking for risks, deadlines, and evidence")
                document_a_text = comparison_input_a["text"]
                document_b_text = comparison_input_b["text"]
                st.session_state["comparison_document_texts"] = {
                    "document_a": document_a_text,
                    "document_b": document_b_text,
                }
                result = _get_cached_comparison(document_a_text, document_b_text)
                if result is None:
                    result = compare_documents(document_a_text, document_b_text)
                    _cache_comparison(document_a_text, document_b_text, result)
                else:
                    st.write(":material/bolt: Reusing the completed analysis for these documents")

                st.session_state["comparison_result"] = result
                save_comparison(
                    user_email,
                    document_a.name,
                    document_b.name,
                    result["overall_conclusion"],
                )
                comparison_status.update(
                    label="Comparison complete",
                    state="complete",
                    expanded=False,
                )
                st.success("Comparison completed successfully.")

            except (RuntimeError, ValueError) as error:
                comparison_status.update(
                    label="Comparison needs attention",
                    state="error",
                    expanded=True,
                )
                st.error(str(error))


comparison_result = st.session_state.get("comparison_result")

if comparison_result:
    st.header("Comparison results", anchor=False, icon=":material/insights:")
    st.caption("Move through the sections below to review the AI-generated findings.")

    summary_a, summary_b, similarities, differences, details, risks, evidence, conclusion = (
        st.tabs(
            [
                "Summary A",
                "Summary B",
                "Similarities",
                "Differences",
                "Key details",
                "Risks & deadlines",
                "Evidence",
                "Conclusion",
            ]
        )
    )

    with summary_a:
        st.write(comparison_result["document_a_summary"])

    with summary_b:
        st.write(comparison_result["document_b_summary"])

    with similarities:
        for item in comparison_result["similarities"]:
            st.markdown(f":material/check_circle: {item}")

    with differences:
        difference_items = [
            normalize_difference(item)
            for item in comparison_result.get("differences", [])
        ]

        if difference_items:
            severity_options = ["All severities", "High", "Medium", "Low"]
            selected_severity = st.segmented_control(
                "Filter by severity",
                severity_options,
                default="All severities",
                key="difference_severity_filter",
            )
            category_options = ["All categories"] + sorted(
                {item["category"] for item in difference_items}
            )
            selected_category = st.selectbox(
                "Filter by category",
                category_options,
                key="difference_category_filter",
            )

            filtered_items = [
                item
                for item in difference_items
                if (selected_severity == "All severities" or item["severity"] == selected_severity)
                and (selected_category == "All categories" or item["category"] == selected_category)
            ]
            st.caption(f"Showing {len(filtered_items)} of {len(difference_items)} findings.")

            for item in filtered_items:
                severity = item["severity"]
                if severity == "High":
                    with st.container(border=True):
                        st.error(f"High severity · {item['title']}", icon=":material/priority_high:")
                        st.caption(item["category"])
                        st.write(item["description"])
                        source_a, source_b = st.columns(2)
                        source_a.markdown(f"**Document A**\n\n{item['document_a']}")
                        source_b.markdown(f"**Document B**\n\n{item['document_b']}")
                elif severity == "Low":
                    with st.container(border=True):
                        st.info(f"Low severity · {item['title']}", icon=":material/info:")
                        st.caption(item["category"])
                        st.write(item["description"])
                        source_a, source_b = st.columns(2)
                        source_a.markdown(f"**Document A**\n\n{item['document_a']}")
                        source_b.markdown(f"**Document B**\n\n{item['document_b']}")
                else:
                    with st.container(border=True):
                        st.warning(f"Medium severity · {item['title']}", icon=":material/change_history:")
                        st.caption(item["category"])
                        st.write(item["description"])
                        source_a, source_b = st.columns(2)
                        source_a.markdown(f"**Document A**\n\n{item['document_a']}")
                        source_b.markdown(f"**Document B**\n\n{item['document_b']}")
        else:
            st.success("No meaningful differences were identified in the provided text.")

    with details:
        st.json(comparison_result["key_details"])

    with risks:
        st.subheader("Risk flags", anchor=False, icon=":material/warning:")
        risk_flags = comparison_result.get("risk_flags", [])
        if risk_flags:
            for item in risk_flags:
                st.warning(item, icon=":material/priority_high:")
        else:
            st.success("No specific risk flags were identified in the provided text.")

        st.subheader("Deadlines", anchor=False, icon=":material/event:")
        deadlines = comparison_result.get("deadlines", [])
        if deadlines:
            for item in deadlines:
                st.markdown(f":material/event: {item}")
        else:
            st.caption("No deadlines were identified.")

    with evidence:
        st.caption("Verify important findings against the original document text.")
        citations = comparison_result.get("source_citations", [])
        if citations:
            for citation in citations:
                with st.container(border=True):
                    st.markdown(
                        f"**{citation.get('finding', 'Finding')}** · "
                        f"{citation.get('source', 'Source')}"
                    )
                    st.write(f"\"{citation.get('quote', 'Quote unavailable')}\"")
        else:
            st.caption("No source citations were returned.")

    with conclusion:
        st.write(comparison_result["overall_conclusion"])

        if comparison_result["limitations"]:
            st.subheader("Limitations", anchor=False, icon=":material/info:")

            for limitation in comparison_result["limitations"]:
                st.markdown(f":material/warning: {limitation}")

    if document_a is not None and document_b is not None:
        st.header("Take the report with you", anchor=False, icon=":material/download:")
        st.write("Download a Word document containing the complete comparison.")

        report_file = create_report(
            comparison_result,
            document_a.name,
            document_b.name,
        )

        st.download_button(
            label="Download comparison report",
            data=report_file.getvalue(),
            file_name="comparison_report.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            type="primary",
            width="stretch",
            icon=":material/download:",
        )

    st.header("Ask both documents", anchor=False, icon=":material/forum:")
    st.write(
        "Ask questions about the comparison and get answers supported by evidence from Document A, Document B, or both."
    )

    comparison_texts = st.session_state.get("comparison_document_texts")
    if comparison_texts:
        chat_toolbar, clear_chat_column = st.columns([4, 1])
        with chat_toolbar:
            st.caption("The assistant only uses the two documents from this comparison.")
        with clear_chat_column:
            if st.button("Clear chat", key="clear_comparison_chat", width="stretch"):
                st.session_state.pop("comparison_document_chat", None)
                st.rerun()

        comparison_chat = st.session_state.setdefault("comparison_document_chat", [])
        if not comparison_chat:
            suggested_question = st.pills(
                "Try asking",
                [
                    "What changed between the documents?",
                    "Which document has the stricter deadline?",
                    "What risks appear only in Document B?",
                ],
                label_visibility="collapsed",
            )
            if suggested_question:
                st.session_state["suggested_comparison_question"] = suggested_question

        comparison_question = st.chat_input(
            "Ask a question about both documents",
            key="comparison_question_input",
        )
        comparison_question = comparison_question or st.session_state.pop(
            "suggested_comparison_question", None
        )

        if comparison_question:
            comparison_chat.append({"role": "user", "content": comparison_question})
            try:
                with st.status("AI is comparing the documents...", expanded=True) as chat_status:
                    render_detective_loader()
                    st.write(":material/compare_arrows: Checking both documents")
                    st.write(":material/format_quote: Preparing an evidence-backed answer")
                    answer = ask_compared_documents(
                        comparison_texts["document_a"],
                        comparison_texts["document_b"],
                        comparison_question.strip(),
                    )
                    comparison_chat.append({"role": "assistant", "content": answer})
                    chat_status.update(
                        label="Comparison answer found",
                        state="complete",
                        expanded=False,
                    )
            except RuntimeError as error:
                comparison_chat.append({
                    "role": "assistant",
                    "content": {
                        "answer": str(error),
                        "confidence": "Unavailable",
                        "citations": [],
                    },
                })

        for message in comparison_chat:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
                continue

            response = message["content"]
            with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                st.write(response["answer"])
                st.caption(f"Confidence: {response.get('confidence', 'Not specified')}")
                citations = response.get("citations", [])
                if citations:
                    with st.expander("Evidence", icon=":material/format_quote:"):
                        for citation in citations:
                            st.caption(citation.get("source", "Source"))
                            st.write(f"\"{citation.get('quote', 'Quote unavailable')}\"")
    else:
        st.info("Run the comparison first to unlock questions about both documents.")
