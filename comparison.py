import json
import os
import re
import time

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

COMPARISON_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
)
COMPARISON_RETRY_ATTEMPTS = 2


def _normalize_response_text(response_text):
    """Strip markdown fences and whitespace around JSON responses."""
    if response_text is None:
        return ""

    text = response_text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _get_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except (FileNotFoundError, KeyError):
            api_key = None
    return api_key


def _is_retryable_error(error):
    """Identify temporary Gemini failures that are safe to retry."""

    error_text = str(error).lower()
    return any(
        marker in error_text
        for marker in (
            "429",
            "500",
            "502",
            "503",
            "504",
            "unavailable",
            "resource_exhausted",
            "deadline_exceeded",
            "timed out",
        )
    )


def _is_model_unavailable_error(error):
    """Identify model-access errors so the next configured model can run."""

    error_text = str(error).lower()
    return "404" in error_text or "not_found" in error_text or "no longer available" in error_text


@st.cache_resource(show_spinner=False)
def _get_client(api_key):
    """Reuse one Gemini client per configured API key across reruns."""

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=180_000),
    )


def _json_config(max_output_tokens):
    """Keep model output structured and bounded for faster responses."""

    return types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
        max_output_tokens=max_output_tokens,
    )


def _validate_comparison_result(result):
    """Validate Gemini's comparison structure before the app renders or exports it."""

    def fail():
        raise RuntimeError(
            "Gemini returned a comparison response with an unexpected structure. "
            "Please try again."
        )

    def require_string_fields(item, fields):
        if not isinstance(item, dict):
            fail()
        for field in fields:
            if not isinstance(item.get(field), str) or not item[field].strip():
                fail()

    if not isinstance(result, dict):
        fail()

    require_string_fields(
        result,
        ("document_a_summary", "document_b_summary", "overall_conclusion"),
    )

    for field in ("similarities", "limitations", "risk_flags", "deadlines"):
        values = result.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            fail()

    differences = result.get("differences")
    if not isinstance(differences, list):
        fail()
    for difference in differences:
        if isinstance(difference, str) and difference.strip():
            continue
        require_string_fields(
            difference,
            ("title", "category", "severity", "description", "document_a", "document_b"),
        )
        if difference["category"].casefold() not in {
            "addition",
            "removal",
            "change",
            "contradiction",
        }:
            fail()
        if difference["severity"].casefold() not in {"high", "medium", "low"}:
            fail()

    key_details = result.get("key_details")
    if not isinstance(key_details, list):
        fail()
    for detail in key_details:
        require_string_fields(detail, ("field", "document_a", "document_b"))

    citations = result.get("source_citations")
    if not isinstance(citations, list):
        fail()
    for citation in citations:
        require_string_fields(citation, ("finding", "quote", "source"))
        if citation["source"] not in {"Document A", "Document B"}:
            fail()

    return result


def transcribe_pdf_with_gemini(pdf_bytes):
    """Extract text from a scanned PDF using Gemini's native PDF vision support."""

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found. Check your .env file.")

    client = _get_client(api_key)
    prompt = """
Transcribe all readable text from this PDF exactly as it appears.
Preserve the reading order and paragraph breaks where possible.
Do not summarize, interpret, or add information. Return only the transcribed text.
"""

    response = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt,
                ],
            )
            break
        except Exception as error:
            if not _is_retryable_error(error) or attempt == 2:
                raise RuntimeError(
                    "Gemini could not read this scanned PDF after retrying. "
                    "The AI service may be temporarily busy; please try again. "
                    f"Details: {type(error).__name__}: {error}"
                ) from error

            time.sleep(2**attempt)

    if response is None:
        raise RuntimeError("Gemini did not return scanned-PDF text.")

    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise RuntimeError("No readable text was found in this scanned PDF.")
    return text.strip()


def compare_documents(document_a_text, document_b_text):
    """Send both document texts to Gemini and return the comparison."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except (FileNotFoundError, KeyError):
            api_key = None

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found. Check your .env file."
        )

    client = _get_client(api_key)

    prompt = f"""
You are a careful document comparison assistant.

Compare Document A and Document B.

Rules:
1. Use only the text provided below.
2. Do not invent facts.
3. Keep Document A and Document B separate.
4. Identify important similarities.
5. Identify meaningful differences, additions, removals, and contradictions.
6. Compare dates, names, numbers, amounts, deadlines, and requirements.
7. If information is missing, write:
   "Not found in the provided text."
8. Return valid JSON only.

Return exactly this structure:

{{
  "document_a_summary": "Short summary of Document A",
  "document_b_summary": "Short summary of Document B",
  "similarities": [
    "Similarity supported by both documents"
  ],
  "differences": [
    {{
      "title": "Short name for the change",
      "category": "Addition, removal, change, or contradiction",
      "severity": "High, Medium, or Low",
      "description": "Plain-language explanation of what changed",
      "document_a": "Exact value or short quote from Document A",
      "document_b": "Exact value or short quote from Document B"
    }}
  ],
  "key_details": [
    {{
      "field": "Date, name, amount, or requirement",
      "document_a": "Value in Document A",
      "document_b": "Value in Document B"
    }}
  ],
  "overall_conclusion": "Neutral conclusion",
  "limitations": [
    "Any limitation or missing information"
  ],
  "risk_flags": [
    "Potential risk, obligation, contradiction, or issue supported by the documents"
  ],
  "deadlines": [
    "Important deadline or time-sensitive requirement supported by the documents"
  ],
  "source_citations": [
    {{
      "finding": "The finding this quote supports",
      "quote": "Exact short quote from the provided text",
      "source": "Document A or Document B"
    }}
  ]
}}

DOCUMENT A:
{document_a_text}

DOCUMENT B:
{document_b_text}
"""

    response = None
    last_error = None
    for model_index, model_name in enumerate(COMPARISON_MODELS):
        for attempt in range(COMPARISON_RETRY_ATTEMPTS):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=_json_config(max_output_tokens=4096),
                )
                break
            except Exception as error:
                last_error = error
                if _is_model_unavailable_error(error):
                    break
                if not _is_retryable_error(error):
                    raise RuntimeError(
                        "Gemini could not process the documents: "
                        f"{type(error).__name__}: {error}"
                    ) from error

                if attempt < COMPARISON_RETRY_ATTEMPTS - 1:
                    time.sleep(0.5 * (attempt + 1))

        if response is not None:
            break

    if response is None:
        if last_error is not None:
            raise RuntimeError(
                "Gemini could not process the documents after trying the "
                "primary and fallback models. The AI service may be busy; "
                "please try again. "
                f"Details: {type(last_error).__name__}: {last_error}"
            ) from last_error
        raise RuntimeError("Gemini did not return a comparison response.")

    response_text = _normalize_response_text(getattr(response, "text", None))

    if not response_text:
        raise RuntimeError(
            "Gemini returned an empty response. Try again with shorter PDFs."
        )

    try:
        comparison_result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Gemini returned an invalid comparison response."
        ) from error

    return _validate_comparison_result(comparison_result)


def analyze_document(document_text="", pdf_bytes=None):
    """Explain one text document or one PDF in clear language."""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except (FileNotFoundError, KeyError):
            api_key = None

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found. Check your .env file.")

    client = _get_client(api_key)
    document_input = document_text or "The document is attached as a visual PDF. Read its pages directly."
    prompt = f"""
You are a careful document understanding assistant.

Explain the document below for a busy reader who wants to understand it quickly.
Use only the text provided. Do not invent facts or give legal advice.
Write in clear, plain language and identify uncertainty when information is missing.
Return valid JSON only using exactly this structure:

{{
  "plain_language_explanation": "A concise explanation of what this document says and why it matters",
  "key_points": ["Important point supported by the document"],
  "important_details": [
    {{"field": "Date, name, amount, deadline, or requirement", "value": "Value from the document"}}
  ],
  "action_items": ["Action the reader may need to take, if stated or clearly required"],
  "limitations": ["Missing information, ambiguity, or important context not present"],
  "risk_flags": [],
  "deadlines": [],
  "source_citations": [
    {{
      "finding": "Payment deadline",
      "quote": "Exact sentence from the document",
      "source": "Document A"
    }}
  ]
}}

DOCUMENT:
{document_input}
"""

    response = None
    for attempt in range(3):
        try:
            contents = prompt
            if pdf_bytes is not None:
                contents = [
                    types.Part.from_bytes(
                        data=pdf_bytes,
                        mime_type="application/pdf",
                    ),
                    prompt,
                ]
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contents,
                config=_json_config(max_output_tokens=2048),
            )
            break
        except Exception as error:
            if not _is_retryable_error(error) or attempt == 2:
                raise RuntimeError(
                    "Gemini could not analyze the document: "
                    f"{type(error).__name__}: {error}"
                ) from error
            time.sleep(2**attempt)

    if response is None:
        raise RuntimeError("Gemini did not return a comparison response.")

    if response is None:
        raise RuntimeError("Gemini did not return an analysis response.")

    response_text = _normalize_response_text(getattr(response, "text", None))
    if not response_text:
        raise RuntimeError("Gemini returned an empty analysis. Try a shorter document.")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned an invalid document analysis.") from error


def ask_document(document_text="", question="", pdf_bytes=None):
    """Answer a user's question using only one document and cite the evidence."""

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found. Check your .env file.")

    client = _get_client(api_key)
    document_input = document_text or "The document is attached as a visual PDF. Read its pages directly."
    prompt = f"""
You answer questions about a document carefully and only use evidence from it.
Do not guess. If the answer is not present, say exactly: "Not found in the document."
Return valid JSON only using this structure:

{{
  "answer": "Direct, plain-language answer to the user's question",
  "confidence": "High, Medium, or Low",
  "citations": [
    {{"quote": "Exact short quote supporting the answer", "source": "Document"}}
  ]
}}

USER QUESTION:
{question}

DOCUMENT:
{document_input}
"""

    contents = prompt
    if pdf_bytes is not None:
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=_json_config(max_output_tokens=1024),
        )
    except Exception as error:
        raise RuntimeError(
            "Gemini could not answer the question: "
            f"{type(error).__name__}: {error}"
        ) from error

    response_text = _normalize_response_text(getattr(response, "text", None))
    if not response_text:
        raise RuntimeError("Gemini returned an empty answer. Please try again.")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned an invalid answer.") from error


def ask_compared_documents(document_a_text, document_b_text, question):
    """Answer a question using both compared documents and cite each source."""

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found. Check your .env file.")

    client = _get_client(api_key)
    prompt = f"""
You answer questions about two compared documents using only the evidence below.
Do not guess or give legal advice. Keep Document A and Document B separate.
If the answer is not present, say exactly: "Not found in the provided documents."
When the question asks what changed, explain the difference plainly.
Return valid JSON only using this structure:

{{
  "answer": "Direct, plain-language answer to the user's question",
  "confidence": "High, Medium, or Low",
  "citations": [
    {{"quote": "Exact short quote supporting the answer", "source": "Document A, Document B, or Both"}}
  ]
}}

USER QUESTION:
{question}

DOCUMENT A:
{document_a_text}

DOCUMENT B:
{document_b_text}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=_json_config(max_output_tokens=1024),
        )
    except Exception as error:
        raise RuntimeError(
            "Gemini could not answer the comparison question: "
            f"{type(error).__name__}: {error}"
        ) from error

    response_text = _normalize_response_text(getattr(response, "text", None))
    if not response_text:
        raise RuntimeError("Gemini returned an empty comparison answer. Please try again.")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned an invalid comparison answer.") from error
