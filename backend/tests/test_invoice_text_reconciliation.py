from decimal import Decimal

from fastapi.testclient import TestClient

from mismatch_desk.main import app, get_invoice_extractor
from mismatch_desk.models import (
    EvidenceField,
    ExtractedInvoice,
    ExtractedInvoiceLine,
    InvoiceExtractionResponse,
    NumericEvidenceField,
)


class FakeInvoiceExtractor:
    def __init__(self, response: InvoiceExtractionResponse) -> None:
        self.response = response
        self.received_text: str | None = None

    async def extract(self, source_text: str) -> InvoiceExtractionResponse:
        self.received_text = source_text
        return self.response


def _evidence(value: str) -> EvidenceField:
    return EvidenceField(value=value, source_quote=value, status="found")


def _extraction(
    *, invoice_number_status: str = "found", quantity: str = "10"
) -> InvoiceExtractionResponse:
    invoice_number = EvidenceField(
        value="INV-1" if invoice_number_status == "found" else None,
        source_quote="INV-1" if invoice_number_status == "found" else None,
        status=invoice_number_status,
    )
    reasons = (
        []
        if invoice_number_status == "found"
        else [f"invoice.invoice_number is marked {invoice_number_status}."]
    )
    return InvoiceExtractionResponse(
        extracted_invoice=ExtractedInvoice(
            invoice_number=invoice_number,
            supplier_name=_evidence("Test Supplier"),
            purchase_order_number=_evidence("PO-1"),
            lines=[
                ExtractedInvoiceLine(
                    item_code=_evidence("ITEM-1"),
                    description=_evidence("Test item"),
                    quantity=NumericEvidenceField(
                        value=Decimal(quantity), source_quote=quantity, status="found"
                    ),
                    unit=_evidence("each"),
                    unit_price=NumericEvidenceField(
                        value=Decimal("2.50"), source_quote="2.50", status="found"
                    ),
                )
            ],
        ),
        review_required=bool(reasons),
        review_reasons=reasons,
    )


def _request_body() -> dict[str, object]:
    line = {
        "line_id": "po-1",
        "item_code": "ITEM-1",
        "description": "Test item",
        "quantity": "10",
        "unit": "each",
        "unit_price": "2.50",
    }
    return {
        "document_text": "Invoice INV-1 for Test Supplier, PO-1; 10 Test item at 2.50",
        "purchase_order": {
            "order_number": "PO-1",
            "supplier_name": "Test Supplier",
            "lines": [line],
        },
        "deliveries": [
            {
                "delivery_number": "DN-1",
                "purchase_order_number": "PO-1",
                "lines": [{**line, "line_id": "dn-1"}],
            }
        ],
    }


def test_text_endpoint_returns_evidence_and_reconciliation() -> None:
    fake = FakeInvoiceExtractor(_extraction())
    app.dependency_overrides[get_invoice_extractor] = lambda: fake
    try:
        with TestClient(app) as client:
            response = client.post("/api/invoices/reconcile-from-text", json=_request_body())
    finally:
        app.dependency_overrides.pop(get_invoice_extractor, None)

    assert response.status_code == 200
    body = response.json()
    assert fake.received_text == _request_body()["document_text"]
    assert body["extraction"]["extracted_invoice"]["invoice_number"]["source_quote"] == "INV-1"
    assert body["extraction"]["review_required"] is False
    assert body["reconciliation"]["invoice_number"] == "INV-1"
    assert body["reconciliation"]["status"] == "ready_for_review"
    assert body["reconciliation"]["discrepancies"] == []


def test_text_endpoint_stops_when_extraction_needs_review() -> None:
    fake = FakeInvoiceExtractor(_extraction(invoice_number_status="ambiguous"))
    app.dependency_overrides[get_invoice_extractor] = lambda: fake
    try:
        with TestClient(app) as client:
            response = client.post("/api/invoices/reconcile-from-text", json=_request_body())
    finally:
        app.dependency_overrides.pop(get_invoice_extractor, None)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["review_required"] is True
    assert body["extraction"]["review_reasons"] == [
        "invoice.invoice_number is marked ambiguous."
    ]
    assert body["reconciliation"] is None


def test_text_endpoint_stops_when_values_cannot_form_a_valid_invoice() -> None:
    fake = FakeInvoiceExtractor(_extraction(quantity="0"))
    app.dependency_overrides[get_invoice_extractor] = lambda: fake
    try:
        with TestClient(app) as client:
            response = client.post("/api/invoices/reconcile-from-text", json=_request_body())
    finally:
        app.dependency_overrides.pop(get_invoice_extractor, None)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["review_required"] is True
    assert body["extraction"]["review_reasons"] == [
        "Extracted values cannot be represented by the supported invoice fields."
    ]
    assert body["reconciliation"] is None
