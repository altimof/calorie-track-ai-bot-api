from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from calorie_track_ai_bot.main import app
from calorie_track_ai_bot.schemas import InlineAnalyticsDaily, InlineChatType, InlineFailureReason


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_inline_summary(client: TestClient, admin_headers: dict[str, str]) -> None:
    sample = InlineAnalyticsDaily(
        id=uuid4(),
        date=date(2025, 1, 1),
        chat_type=InlineChatType.group,
        trigger_counts={"reply_mention": 3},
        request_count=5,
        success_count=4,
        failure_count=1,
        permission_block_count=2,
        avg_ack_latency_ms=2500,
        p95_result_latency_ms=9000,
        accuracy_within_tolerance_pct=92.5,
        failure_reasons=[InlineFailureReason(reason="processing_error", count=1)],
        last_updated_at=datetime.now(UTC),
    )

    with patch(
        "calorie_track_ai_bot.api.v1.inline_analytics.db_fetch_inline_analytics",
        new=AsyncMock(return_value=[sample]),
    ) as mock_fetch:
        response = client.get(
            "/api/v1/analytics/inline-summary",
            params={"range_start": "2025-01-01", "range_end": "2025-01-07", "chat_type": "group"},
            headers=admin_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["range"] == {"start": "2025-01-01", "end": "2025-01-07"}
    assert body["sla"]["ack_target_ms"] == 3000
    assert body["accuracy"]["tolerance_pct"] == 5.0

    assert len(body["buckets"]) == 1
    bucket = body["buckets"][0]
    assert bucket["chat_type"] == "group"
    assert bucket["trigger_counts"]["reply_mention"] == 3
    assert bucket["failure_reasons"][0]["reason"] == "processing_error"

    mock_fetch.assert_awaited_once()
