from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .extraction import ExtractionProviderError, OpenRouterInvoiceExtractor
from .models import (
    DiscrepancyCode,
    InvoiceExtractionResponse,
    InvoiceTextReconciliationRequest,
    InvoiceTextReconciliationResponse,
    InvoiceTextRequest,
    DocumentLine,
    Invoice,
    PdfTextResponse,
    ReconciliationRequest,
    ReconciliationResult,
)
from .pdf_extraction import PdfTextExtractionError, extract_pdf_text
from .workflow import reconciliation_graph

app = FastAPI(
    title="Mismatch Desk API",
    description="Reconcile invoices against purchase orders and delivery records.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MAX_PDF_BYTES = 10 * 1024 * 1024


def get_invoice_extractor() -> OpenRouterInvoiceExtractor:
    try:
        return OpenRouterInvoiceExtractor.from_environment()
    except ExtractionProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _run_reconciliation(request: ReconciliationRequest) -> ReconciliationResult:
    state = reconciliation_graph.invoke(
        {"request": request, "discrepancies": [], "status": "processing"}
    )
    return ReconciliationResult(
        invoice_number=request.invoice.invoice_number,
        purchase_order_number=request.purchase_order.order_number,
        status=state["status"],
        discrepancies=state["discrepancies"],
        matched_line_count=len(request.invoice.lines)
        - sum(
            1
            for item in state["discrepancies"]
            if item.code
            in {
                DiscrepancyCode.UNMATCHED_INVOICE_LINE,
                DiscrepancyCode.AMBIGUOUS_ITEM_MATCH,
            }
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/invoices/extract", response_model=InvoiceExtractionResponse)
async def extract_invoice_text(request: InvoiceTextRequest) -> InvoiceExtractionResponse:
    try:
        extractor = OpenRouterInvoiceExtractor.from_environment()
        return await extractor.extract(request.document_text)
    except ExtractionProviderError as error:
        status_code = 503 if "not configured" in str(error) else 502
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@app.post("/api/invoices/extract-pdf", response_model=PdfTextResponse)
async def extract_invoice_pdf(file: Annotated[UploadFile, File()]) -> PdfTextResponse:
    filename = file.filename or "uploaded-file"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")

    try:
        pdf_bytes = await file.read(MAX_PDF_BYTES + 1)
    finally:
        await file.close()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="The PDF exceeds the 10 MB upload limit.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    try:
        document_text, page_count = extract_pdf_text(pdf_bytes)
    except PdfTextExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return PdfTextResponse(
        filename=filename,
        page_count=page_count,
        document_text=document_text,
    )


@app.post(
    "/api/invoices/reconcile-from-text",
    response_model=InvoiceTextReconciliationResponse,
)
async def reconcile_invoice_text(
    request: InvoiceTextReconciliationRequest,
    extractor: OpenRouterInvoiceExtractor = Depends(get_invoice_extractor),
) -> InvoiceTextReconciliationResponse:
    try:
        extraction = await extractor.extract(request.document_text)
    except ExtractionProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    if extraction.review_required:
        return InvoiceTextReconciliationResponse(extraction=extraction)

    extracted = extraction.extracted_invoice
    try:
        invoice = Invoice(
            invoice_number=extracted.invoice_number.value,
            supplier_name=extracted.supplier_name.value,
            purchase_order_number=extracted.purchase_order_number.value,
            lines=[
                DocumentLine(
                    line_id=f"extracted-{index}",
                    item_code=line.item_code.value,
                    description=line.description.value,
                    quantity=line.quantity.value,
                    unit=line.unit.value,
                    unit_price=line.unit_price.value,
                )
                for index, line in enumerate(extracted.lines, start=1)
            ],
        )
    except ValidationError:
        extraction = InvoiceExtractionResponse(
            extracted_invoice=extracted,
            review_required=True,
            review_reasons=[
                *extraction.review_reasons,
                "Extracted values cannot be represented by the supported invoice fields.",
            ],
        )
        return InvoiceTextReconciliationResponse(extraction=extraction)

    reconciliation = _run_reconciliation(
        ReconciliationRequest(
            invoice=invoice,
            purchase_order=request.purchase_order,
            deliveries=request.deliveries,
        )
    )
    return InvoiceTextReconciliationResponse(
        extraction=extraction,
        reconciliation=reconciliation,
    )


@app.post("/api/reconciliation", response_model=ReconciliationResult)
def create_reconciliation(request: ReconciliationRequest) -> ReconciliationResult:
    return _run_reconciliation(request)
