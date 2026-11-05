from decimal import Decimal

from .models import (
    DeliveryRecord,
    Discrepancy,
    DiscrepancyCode,
    DocumentLine,
    Invoice,
    PurchaseOrder,
    ReconciliationRequest,
)


def _item_key(line: DocumentLine) -> str:
    if line.item_code:
        return f"code:{line.item_code.strip().casefold()}"
    return f"description:{' '.join(line.description.casefold().split())}"


def reconcile(request: ReconciliationRequest) -> list[Discrepancy]:
    """Apply deterministic checks. Ambiguous records are surfaced, never guessed."""
    invoice = request.invoice
    order = request.purchase_order
    discrepancies: list[Discrepancy] = []

    if invoice.purchase_order_number != order.order_number:
        discrepancies.append(
            Discrepancy(
                code=DiscrepancyCode.ORDER_NOT_FOUND,
                message="The referenced purchase order does not match the supplied order.",
                expected=order.order_number,
                actual=invoice.purchase_order_number,
            )
        )

    if invoice.supplier_name.strip().casefold() != order.supplier_name.strip().casefold():
        discrepancies.append(
            Discrepancy(
                code=DiscrepancyCode.SUPPLIER_MISMATCH,
                message="The invoice supplier name differs from the purchase order supplier.",
                expected=order.supplier_name,
                actual=invoice.supplier_name,
            )
        )

    order_by_key: dict[str, list[DocumentLine]] = {}
    for line in order.lines:
        order_by_key.setdefault(_item_key(line), []).append(line)

    received_by_key: dict[str, Decimal] = {}
    delivery_ids_by_key: dict[str, list[str]] = {}
    for delivery in request.deliveries:
        if delivery.purchase_order_number != order.order_number:
            continue
        for line in delivery.lines:
            key = _item_key(line)
            received_by_key[key] = received_by_key.get(key, Decimal("0")) + line.quantity
            delivery_ids_by_key.setdefault(key, []).append(line.line_id)

    matched_count = 0
    for invoice_line in invoice.lines:
        key = _item_key(invoice_line)
        candidates = order_by_key.get(key, [])
        if len(candidates) == 0:
            discrepancies.append(
                Discrepancy(
                    code=DiscrepancyCode.UNMATCHED_INVOICE_LINE,
                    message="No purchase-order line matches this invoice item identifier.",
                    invoice_line_id=invoice_line.line_id,
                )
            )
            continue
        if len(candidates) > 1:
            discrepancies.append(
                Discrepancy(
                    code=DiscrepancyCode.AMBIGUOUS_ITEM_MATCH,
                    message="Multiple purchase-order lines share this item identifier.",
                    invoice_line_id=invoice_line.line_id,
                    related_line_ids=[line.line_id for line in candidates],
                )
            )
            continue

        order_line = candidates[0]
        matched_count += 1
        related_ids = [order_line.line_id, *delivery_ids_by_key.get(key, [])]
        received_quantity = received_by_key.get(key, Decimal("0"))

        if invoice_line.quantity > order_line.quantity:
            discrepancies.append(
                Discrepancy(
                    code=DiscrepancyCode.QUANTITY_EXCEEDS_ORDERED,
                    message="The invoiced quantity is greater than the quantity ordered.",
                    invoice_line_id=invoice_line.line_id,
                    related_line_ids=related_ids,
                    expected=str(order_line.quantity),
                    actual=str(invoice_line.quantity),
                )
            )
        if request.deliveries and invoice_line.quantity > received_quantity:
            discrepancies.append(
                Discrepancy(
                    code=DiscrepancyCode.QUANTITY_EXCEEDS_RECEIVED,
                    message="The invoiced quantity is greater than the quantity recorded as delivered.",
                    invoice_line_id=invoice_line.line_id,
                    related_line_ids=related_ids,
                    expected=str(received_quantity),
                    actual=str(invoice_line.quantity),
                )
            )
        if invoice_line.unit_price != order_line.unit_price:
            discrepancies.append(
                Discrepancy(
                    code=DiscrepancyCode.UNIT_PRICE_MISMATCH,
                    message="The invoiced unit price differs from the purchase-order price.",
                    invoice_line_id=invoice_line.line_id,
                    related_line_ids=related_ids,
                    expected=str(order_line.unit_price),
                    actual=str(invoice_line.unit_price),
                )
            )

    return discrepancies
