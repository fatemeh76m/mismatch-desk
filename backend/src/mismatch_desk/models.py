from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(description="The value found in the source, or null if unresolved.")
    source_quote: str | None = Field(
        description="An exact short excerpt copied from the source, or null if none exists."
    )
    status: Literal["found", "missing", "ambiguous"] = Field(
        description="Whether the value was found unambiguously in the source."
    )


class NumericEvidenceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Decimal | None = Field(description="The parsed numeric value, or null if unresolved.")
    source_quote: str | None = Field(
        description="An exact short excerpt copied from the source, or null if none exists."
    )
    status: Literal["found", "missing", "ambiguous"] = Field(
        description="Whether the value was found unambiguously in the source."
    )


class ExtractedInvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_code: EvidenceField
    description: EvidenceField
    quantity: NumericEvidenceField
    unit: EvidenceField
    unit_price: NumericEvidenceField


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: EvidenceField
    supplier_name: EvidenceField
    purchase_order_number: EvidenceField
    lines: list[ExtractedInvoiceLine]


class InvoiceTextRequest(BaseModel):
    document_text: str = Field(min_length=1, max_length=30000)


class InvoiceExtractionResponse(BaseModel):
    extracted_invoice: ExtractedInvoice
    review_required: bool
    review_reasons: list[str]


class DocumentLine(BaseModel):
    line_id: str
    item_code: str | None = None
    description: str
    quantity: Decimal = Field(gt=0)
    unit: str = "each"
    unit_price: Decimal = Field(ge=0)


class Invoice(BaseModel):
    invoice_number: str
    supplier_name: str
    purchase_order_number: str
    lines: list[DocumentLine] = Field(min_length=1)


class PurchaseOrder(BaseModel):
    order_number: str
    supplier_name: str
    lines: list[DocumentLine] = Field(min_length=1)


class DeliveryRecord(BaseModel):
    delivery_number: str
    purchase_order_number: str
    lines: list[DocumentLine] = Field(default_factory=list)


class ReconciliationRequest(BaseModel):
    invoice: Invoice
    purchase_order: PurchaseOrder
    deliveries: list[DeliveryRecord] = Field(default_factory=list)


class InvoiceTextReconciliationRequest(InvoiceTextRequest):
    purchase_order: PurchaseOrder
    deliveries: list[DeliveryRecord] = Field(default_factory=list)


class DiscrepancyCode(StrEnum):
    ORDER_NOT_FOUND = "order_not_found"
    SUPPLIER_MISMATCH = "supplier_mismatch"
    UNMATCHED_INVOICE_LINE = "unmatched_invoice_line"
    QUANTITY_EXCEEDS_RECEIVED = "quantity_exceeds_received"
    QUANTITY_EXCEEDS_ORDERED = "quantity_exceeds_ordered"
    UNIT_PRICE_MISMATCH = "unit_price_mismatch"
    AMBIGUOUS_ITEM_MATCH = "ambiguous_item_match"


class Discrepancy(BaseModel):
    code: DiscrepancyCode
    message: str
    invoice_line_id: str | None = None
    related_line_ids: list[str] = Field(default_factory=list)
    expected: str | None = None
    actual: str | None = None


class ReconciliationResult(BaseModel):
    invoice_number: str
    purchase_order_number: str
    status: str
    discrepancies: list[Discrepancy]
    matched_line_count: int


class InvoiceTextReconciliationResponse(BaseModel):
    extraction: InvoiceExtractionResponse
    reconciliation: ReconciliationResult | None = None

