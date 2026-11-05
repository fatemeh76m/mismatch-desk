from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_PDF_PAGES = 20
MAX_DOCUMENT_CHARACTERS = 30_000


class PdfTextExtractionError(ValueError):
    """Raised when a PDF cannot safely provide usable invoice text."""


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise PdfTextExtractionError("Password-protected PDFs are not supported yet.")

        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise PdfTextExtractionError(
                f"This PDF has {page_count} pages; the current limit is {MAX_PDF_PAGES}."
            )

        page_texts = []
        extracted_characters = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_characters += len(page_text)
            if extracted_characters > MAX_DOCUMENT_CHARACTERS:
                raise PdfTextExtractionError(
                    f"The extracted text exceeds the {MAX_DOCUMENT_CHARACTERS:,}-character limit."
                )
            page_texts.append(page_text)
    except PdfTextExtractionError:
        raise
    except (PdfReadError, ValueError, EOFError) as error:
        raise PdfTextExtractionError("The uploaded file could not be read as a valid PDF.") from error

    document_text = "\n\n".join(text.strip() for text in page_texts if text.strip())
    if not document_text:
        raise PdfTextExtractionError(
            "No selectable text was found. This may be a scanned PDF and needs OCR before review."
        )
    if len(document_text) > MAX_DOCUMENT_CHARACTERS:
        raise PdfTextExtractionError(
            f"The extracted text exceeds the {MAX_DOCUMENT_CHARACTERS:,}-character limit."
        )

    return document_text, page_count
