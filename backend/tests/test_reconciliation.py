from decimal import Decimal

from mismatch_desk.models import (
    DeliveryRecord,
    DocumentLine,
    Invoice,
    PurchaseOrder,
    ReconciliationRequest,
)
from mismatch_desk.reconciliation import reconcile


def _line(
    line_id: str,
    *,
    item_code: str = "ITEM-1",
    quantity: str = "10",
    unit_price: str = "2.50",
) -> DocumentLine:
    return DocumentLine(
        line_id=line_id,
        item_code=item_code,
        description="Test item",
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
    )


def _request(
    invoice_lines: list[DocumentLine],
    order_lines: list[DocumentLine],
    deliveries: list[DeliveryRecord] | None = None,
) -> ReconciliationRequest:
    return ReconciliationRequest(
        invoice=Invoice(
            invoice_number="INV-1",
            supplier_name="Test Supplier",
            purchase_order_number="PO-1",
            lines=invoice_lines,
        ),
        purchase_order=PurchaseOrder(
            order_number="PO-1",
            supplier_name="Test Supplier",
            lines=order_lines,
        ),
        deliveries=deliveries or [],
    )


def test_flags_partial_delivery_and_price_mismatch() -> None:
    request = ReconciliationRequest(
        invoice=Invoice(
            invoice_number="INV-1042",
            supplier_name="Torino Components",
            purchase_order_number="PO-778",
            lines=[
                DocumentLine(
                    line_id="inv-1",
                    item_code="BRG-42",
                    description="Bearing 42mm",
                    quantity=Decimal("100"),
                    unit_price=Decimal("12.50"),
                )
            ],
        ),
        purchase_order=PurchaseOrder(
            order_number="PO-778",
            supplier_name="Torino Components",
            lines=[
                DocumentLine(
                    line_id="po-1",
                    item_code="BRG-42",
                    description="Bearing, 42 mm",
                    quantity=Decimal("100"),
                    unit_price=Decimal("12.00"),
                )
            ],
        ),
        deliveries=[
            DeliveryRecord(
                delivery_number="DN-900",
                purchase_order_number="PO-778",
                lines=[
                    DocumentLine(
                        line_id="dn-1",
                        item_code="BRG-42",
                        description="Bearing 42 mm",
                        quantity=Decimal("80"),
                        unit_price=Decimal("12.00"),
                    )
                ],
            )
        ],
    )

    codes = {item.code.value for item in reconcile(request)}

    assert codes == {"quantity_exceeds_received", "unit_price_mismatch"}


def test_fully_matching_invoice_has_no_discrepancies() -> None:
    request = _request(
        [_line("inv-1")],
        [_line("po-1")],
        [
            DeliveryRecord(
                delivery_number="DN-1",
                purchase_order_number="PO-1",
                lines=[_line("dn-1")],
            )
        ],
    )

    assert reconcile(request) == []


def test_adds_quantities_across_deliveries() -> None:
    request = _request(
        [_line("inv-1", quantity="100")],
        [_line("po-1", quantity="100")],
        [
            DeliveryRecord(
                delivery_number="DN-1",
                purchase_order_number="PO-1",
                lines=[_line("dn-1", quantity="40")],
            ),
            DeliveryRecord(
                delivery_number="DN-2",
                purchase_order_number="PO-1",
                lines=[_line("dn-2", quantity="60")],
            ),
        ],
    )

    assert reconcile(request) == []


def test_flags_invoice_quantity_greater_than_ordered() -> None:
    request = _request(
        [_line("inv-1", quantity="11")],
        [_line("po-1", quantity="10")],
    )

    discrepancies = reconcile(request)

    assert [item.code.value for item in discrepancies] == ["quantity_exceeds_ordered"]
    assert discrepancies[0].expected == "10"
    assert discrepancies[0].actual == "11"


def test_flags_invoice_item_without_matching_order_line() -> None:
    request = _request(
        [_line("inv-1", item_code="UNKNOWN")],
        [_line("po-1", item_code="ITEM-1")],
    )

    discrepancies = reconcile(request)

    assert [item.code.value for item in discrepancies] == ["unmatched_invoice_line"]
    assert discrepancies[0].invoice_line_id == "inv-1"


def test_flags_ambiguous_match_when_order_lines_share_item_code() -> None:
    request = _request(
        [_line("inv-1")],
        [_line("po-1"), _line("po-2", quantity="20")],
    )

    discrepancies = reconcile(request)

    assert [item.code.value for item in discrepancies] == ["ambiguous_item_match"]
    assert discrepancies[0].related_line_ids == ["po-1", "po-2"]
