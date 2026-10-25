from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ...schemas import InlineChatType
from ...services.db import db_fetch_inline_analytics
from .admin_auth import require_admin_token

router = APIRouter()

INLINE_ACK_TARGET_MS = 3000
INLINE_RESULT_TARGET_MS = 12000
DEFAULT_RANGE_DAYS = 6
ACCURACY_TOLERANCE = 5.0
BENCHMARK_DATASET = "inline-benchmark-v1"


def _parse_date(value: str | None, default: date) -> date:
    if value is None:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - FastAPI validation prevents most cases
        raise HTTPException(
            status_code=400, detail="Invalid date format; expected YYYY-MM-DD"
        ) from exc


def _normalize_chat_type(value: str | None) -> InlineChatType | None:
    if value is None:
        return None
    try:
        return InlineChatType(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="chat_type must be 'private' or 'group'"
        ) from exc


@router.get("/analytics/inline-summary", dependencies=[Depends(require_admin_token)])
async def get_inline_summary(
    range_start: str | None = Query(None),
    range_end: str | None = Query(None),
    chat_type: str | None = Query(None),
) -> dict[str, Any]:
    today = date.today()
    end_date = _parse_date(range_end, today)
    start_date = _parse_date(range_start, end_date - timedelta(days=DEFAULT_RANGE_DAYS))

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="range_start must be on or before range_end")

    chat_type_enum = _normalize_chat_type(chat_type)
    records = await db_fetch_inline_analytics(
        start_date, end_date, chat_type_enum.value if chat_type_enum else None
    )

    buckets = []
    for record in records:
        buckets.append(
            {
                "date": record.date.isoformat(),
                "chat_type": record.chat_type.value,
                "request_count": record.request_count,
                "success_count": record.success_count,
                "failure_count": record.failure_count,
                "permission_block_count": record.permission_block_count,
                "avg_ack_latency_ms": record.avg_ack_latency_ms,
                "p95_result_latency_ms": record.p95_result_latency_ms,
                "accuracy_within_tolerance_pct": float(record.accuracy_within_tolerance_pct),
                "trigger_counts": record.trigger_counts or {},
                "failure_reasons": [
                    {"reason": reason.reason, "count": reason.count}
                    for reason in record.failure_reasons or []
                ],
            }
        )

    return {
        "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "buckets": buckets,
        "sla": {
            "ack_target_ms": INLINE_ACK_TARGET_MS,
            "result_target_ms": INLINE_RESULT_TARGET_MS,
        },
        "accuracy": {
            "tolerance_pct": ACCURACY_TOLERANCE,
            "benchmark_dataset": BENCHMARK_DATASET,
        },
    }
