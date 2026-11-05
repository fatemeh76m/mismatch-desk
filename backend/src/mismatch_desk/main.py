from fastapi import Depends, FastAPI, HTTPException
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
    ReconciliationRequest,
    ReconciliationRequest,
    ReconciliationResult,
)
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
