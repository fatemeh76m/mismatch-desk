from uuid import UUID

from .database import SessionLocal
from .db_models import ReviewCase, ReviewDecision
from .models import (
    InvoiceExtractionResponse,
    ReconciliationResult,
    ReviewCaseResponse,
    ReviewDecisionRecord,
    ReviewDecisionRequest,
)


def create_review_case(
    extraction: InvoiceExtractionResponse,
    reconciliation: ReconciliationResult | None,
) -> UUID:
    invoice = extraction.extracted_invoice
    if extraction.review_required:
        status = "awaiting_human_review"
    elif reconciliation:
        status = reconciliation.status
    else:
        status = "awaiting_human_review"

    with SessionLocal() as session:
        case = ReviewCase(
            invoice_number=invoice.invoice_number.value,
            supplier_name=invoice.supplier_name.value,
            purchase_order_number=invoice.purchase_order_number.value,
            status=status,
            extraction_data=extraction.model_dump(mode="json"),
            reconciliation_data=(
                reconciliation.model_dump(mode="json") if reconciliation is not None else None
            ),
        )
        session.add(case)
        session.commit()
        return case.id


def _case_response(case: ReviewCase) -> ReviewCaseResponse:
    return ReviewCaseResponse(
        id=case.id,
        invoice_number=case.invoice_number,
        supplier_name=case.supplier_name,
        purchase_order_number=case.purchase_order_number,
        status=case.status,
        created_at=case.created_at,
        extraction=InvoiceExtractionResponse.model_validate(case.extraction_data),
        reconciliation=(
            ReconciliationResult.model_validate(case.reconciliation_data)
            if case.reconciliation_data is not None
            else None
        ),
        decisions=[
            ReviewDecisionRecord(
                id=decision.id,
                decision=decision.decision,
                reason=decision.reason,
                reviewer_name=decision.reviewer_name,
                created_at=decision.created_at,
            )
            for decision in case.decisions
        ],
    )


def get_review_case(case_id: UUID) -> ReviewCaseResponse | None:
    with SessionLocal() as session:
        case = session.get(ReviewCase, case_id)
        return _case_response(case) if case is not None else None


def record_review_decision(
    case_id: UUID,
    request: ReviewDecisionRequest,
) -> ReviewCaseResponse | None:
    with SessionLocal() as session:
        case = session.get(ReviewCase, case_id)
        if case is None:
            return None
        case.status = request.decision
        session.add(
            ReviewDecision(
                case_id=case_id,
                decision=request.decision,
                reason=request.reason,
                reviewer_name=request.reviewer_name,
            )
        )
        session.commit()
        session.refresh(case)
        return _case_response(case)
