from decimal import Decimal

from mismatch_desk.extraction import review_reasons
from mismatch_desk.models import (
    EvidenceField,
    ExtractedInvoice,
    ExtractedInvoiceLine,
    NumericEvidenceField,
)


def _valid_extraction() -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number=EvidenceField(
            value="INV-1042", source_quote="Invoice number: INV-1042", status="found"
        ),
        supplier_name=EvidenceField(
            value="TORINO COMPONENTS SRL", source_quote="TORINO COMPONENTS SRL", status="found"
        ),
        purchase_order_number=EvidenceField(
            value="PO-778", source_quote="Purchase order: PO-778", status="found"
        ),
        lines=[
            ExtractedInvoiceLine(
                item_code=EvidenceField(value="BRG-42", source_quote="BRG-42", status="found"),
                description=EvidenceField(
                    value="Bearing 42mm", source_quote="Bearing 42mm", status="found"
                ),
                quantity=NumericEvidenceField(
                    value=Decimal("100"), source_quote="Quantity: 100 each", status="found"
                ),
                unit=EvidenceField(value="each", source_quote="100 each", status="found"),
                unit_price=NumericEvidenceField(
                    value=Decimal("12.50"), source_quote="EUR 12.50", status="found"
                ),
            )
        ],
    )


def test_supported_quotes_do_not_require_review() -> None:
    text = (
        "TORINO COMPONENTS SRL\nInvoice number: INV-1042\nPurchase order: PO-778\n"
        "Item code: BRG-42\nDescription: Bearing 42mm\nQuantity: 100 each\n"
        "Unit price: EUR 12.50"
    )

    assert review_reasons(_valid_extraction(), text) == []


def test_source_quotes_must_appear_in_document() -> None:
    extraction = _valid_extraction()

    reasons = review_reasons(extraction, "Invoice number: INV-1042\nTORINO COMPONENTS SRL")

    assert "invoice.purchase_order_number source quote does not exactly match the document text." in reasons
    assert "invoice.lines 1.item_code source quote does not exactly match the document text." in reasons


def test_missing_or_ambiguous_fields_require_human_review() -> None:
    extraction = _valid_extraction()
    extraction.invoice_number = EvidenceField(value=None, source_quote=None, status="missing")
    extraction.lines[0].unit_price = NumericEvidenceField(
        value=None, source_quote="EUR 12.50 or EUR 12.80", status="ambiguous"
    )

    reasons = review_reasons(extraction, "EUR 12.50 or EUR 12.80")

    assert "invoice.invoice_number is marked missing." in reasons
    assert "invoice.lines 1.unit_price is marked ambiguous." in reasons
