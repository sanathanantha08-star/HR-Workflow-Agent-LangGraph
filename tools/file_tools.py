import io
import pdfplumber
from docx import Document
from core.logging import get_logger
from core.exceptions import ResumeParseError
from tools.base import tool_call, with_retry

logger = get_logger("tools.file")


@tool_call("extract_text_from_pdf")
@with_retry()
def extract_text_from_pdf(content: bytes) -> str:
    """Extract plain text from PDF bytes."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception as exc:
        raise ResumeParseError(f"PDF parse failed: {exc}") from exc


@tool_call("extract_text_from_docx")
@with_retry()
def extract_text_from_docx(content: bytes) -> str:
    """Extract plain text from DOCX bytes."""
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:
        raise ResumeParseError(f"DOCX parse failed: {exc}") from exc


@tool_call("extract_text_from_file")
def extract_text_from_file(filename: str, content: bytes) -> str:
    """Route to PDF or DOCX extractor based on filename extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif lower.endswith(".docx") or lower.endswith(".doc"):
        return extract_text_from_docx(content)
    elif lower.endswith(".txt"):
        return content.decode("utf-8", errors="replace")
    else:
        raise ResumeParseError(
            f"Unsupported file type: {filename}",
            details={"supported": [".pdf", ".docx", ".doc", ".txt"]},
        )
