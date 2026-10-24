"""Tests for db module (psycopg3 / AsyncConnectionPool)."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from psycopg import errors

import calorie_track_ai_bot.services.db.inline_analytics as inline_analytics_module
from calorie_track_ai_bot.schemas import (
    InlineAnalyticsDaily,
    InlineChatType,
    MealCreateFromEstimateRequest,
    MealCreateManualRequest,
    MealType,
)
from calorie_track_ai_bot.services.db import (
    db_create_meal_from_estimate,
    db_create_meal_from_manual,
    db_create_or_update_goal,
    db_create_photo,
    db_delete_meal,
    db_fetch_inline_analytics,
    db_get_estimate,
    db_increment_inline_permission_block,
    db_save_estimate,
    db_upsert_inline_analytics,
)


def _make_mock_pool():
    """Build an AsyncMock pool whose .connection() returns an async context manager with a mock
    connection.  The connection exposes an async ``execute`` that returns a mock cursor with
    ``fetchone`` and ``fetchall``.

    Returns (pool, conn, cursor) so tests can configure return values.
    """
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=cursor)

    # pool.connection() is used as ``async with pool.connection() as conn``
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection.return_value = ctx

    return pool, conn, cursor


class TestDatabaseFunctions:
    """Test database functions backed by psycopg3 connection pool."""

    @pytest.fixture
    def mock_pool(self):
        """Patch ``get_pool`` to return a mock pool and yield (pool, conn, cursor)."""
        pool, conn, cursor = _make_mock_pool()

        async def _get_pool():
            return pool

        with patch("calorie_track_ai_bot.services.database.get_pool", side_effect=_get_pool):
            yield pool, conn, cursor

    # ------------------------------------------------------------------
    # db_create_photo
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_create_photo_returns_uuid(self, mock_pool):
        """db_create_photo should return a valid UUID string."""
        _pool, conn, _cursor = mock_pool

        result = await db_create_photo("photos/test123.jpg")

        assert isinstance(result, str)
        assert len(result) == 36

        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_create_photo_with_all_params(self, mock_pool):
        """db_create_photo passes user_id, display_order, and media_group_id to the INSERT."""
        _pool, conn, _cursor = mock_pool

        result = await db_create_photo(
            tigris_key="photos/full.jpg",
            user_id="user123",
            display_order=2,
            media_group_id="media456",
        )

        assert isinstance(result, str)
        assert len(result) == 36

        conn.execute.assert_awaited_once()
        call_args = conn.execute.call_args
        params = call_args[0][1]
        # params: (pid, tigris_key, user_id, display_order, media_group_id)
        assert params[1] == "photos/full.jpg"
        assert params[2] == "user123"
        assert params[3] == 2
        assert params[4] == "media456"

    @pytest.mark.asyncio
    async def test_db_create_photo_minimal(self, mock_pool):
        """db_create_photo with only the required tigris_key uses default values."""
        _pool, conn, _cursor = mock_pool

        result = await db_create_photo("photos/minimal.jpg")

        assert isinstance(result, str)
        assert len(result) == 36

        params = conn.execute.call_args[0][1]
        assert params[1] == "photos/minimal.jpg"
        assert params[2] is None  # user_id default
        assert params[3] == 0  # display_order default
        assert params[4] is None  # media_group_id default

    # ------------------------------------------------------------------
    # db_save_estimate
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_save_estimate_returns_uuid(self, mock_pool):
        """db_save_estimate should return a valid UUID string."""
        _pool, conn, _cursor = mock_pool

        estimate_data = {
            "kcal_mean": 500,
            "kcal_min": 400,
            "kcal_max": 600,
            "confidence": 0.8,
            "items": [{"label": "pizza", "kcal": 500, "confidence": 0.8}],
        }

        result = await db_save_estimate("photo123", estimate_data)

        assert isinstance(result, str)
        assert len(result) == 36
        conn.execute.assert_awaited_once()

    # ------------------------------------------------------------------
    # db_get_estimate
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_get_estimate_found(self, mock_pool):
        """db_get_estimate returns the row dict when the estimate exists."""
        _pool, _conn, cursor = mock_pool

        row_data = {"id": "estimate123", "kcal_mean": 500, "kcal_min": 400, "kcal_max": 600}
        cursor.fetchone.return_value = row_data

        result = await db_get_estimate("estimate123")

        assert result == row_data

    @pytest.mark.asyncio
    async def test_db_get_estimate_not_found(self, mock_pool):
        """db_get_estimate returns None when no row matches."""
        _pool, _conn, cursor = mock_pool

        cursor.fetchone.return_value = None

        result = await db_get_estimate("nonexistent")

        assert result is None

    # ------------------------------------------------------------------
    # db_create_meal_from_manual
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_create_meal_from_manual(self, mock_pool):
        """db_create_meal_from_manual returns a dict with a UUID meal_id."""
        _pool, conn, _cursor = mock_pool

        data = MealCreateManualRequest(
            meal_date=date(2024, 1, 1),
            meal_type=MealType.breakfast,
            kcal_total=300.5,
        )

        result = await db_create_meal_from_manual(data)

        assert isinstance(result, dict)
        assert "meal_id" in result
        assert isinstance(result["meal_id"], str)
        assert len(result["meal_id"]) == 36
        conn.execute.assert_awaited_once()

    # ------------------------------------------------------------------
    # db_create_meal_from_estimate
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_create_meal_from_estimate_with_overrides(self, mock_pool):
        """Overrides take precedence over the estimate's kcal_mean."""
        _pool, conn, _cursor = mock_pool

        mock_estimate = {"kcal_mean": 400, "kcal_min": 350, "kcal_max": 450}

        with patch(
            "calorie_track_ai_bot.services.db.meals.db_get_estimate",
            return_value=mock_estimate,
        ):
            data = MealCreateFromEstimateRequest(
                meal_date=date(2024, 1, 1),
                meal_type=MealType.lunch,
                estimate_id="00000000-0000-0000-0000-000000000123",
                overrides={"kcal_total": 450},
            )

            result = await db_create_meal_from_estimate(data, "user123")

        assert isinstance(result, dict)
        assert "meal_id" in result
        assert len(result["meal_id"]) == 36

        # The first execute call is the INSERT INTO meals
        insert_call = conn.execute.call_args_list[0]
        params = insert_call[0][1]
        # params order: (mid, user_id, meal_date, meal_type, kcal_total,
        #                protein_grams, carbs_grams, fats_grams, "photo", estimate_id)
        assert params[4] == 450  # kcal_total from overrides

    @pytest.mark.asyncio
    async def test_db_create_meal_from_estimate_no_overrides(self, mock_pool):
        """Without overrides, kcal_total comes from the estimate's kcal_mean."""
        _pool, conn, _cursor = mock_pool

        mock_estimate = {"kcal_mean": 600, "kcal_min": 550, "kcal_max": 650}

        with patch(
            "calorie_track_ai_bot.services.db.meals.db_get_estimate",
            return_value=mock_estimate,
        ):
            data = MealCreateFromEstimateRequest(
                meal_date=date(2024, 1, 1),
                meal_type=MealType.dinner,
                estimate_id="00000000-0000-0000-0000-000000000456",
                overrides=None,
            )

            result = await db_create_meal_from_estimate(data, "user123")

        assert isinstance(result, dict)
        assert "meal_id" in result

        insert_call = conn.execute.call_args_list[0]
        params = insert_call[0][1]
        assert params[4] == 600  # kcal_total from estimate kcal_mean

    @pytest.mark.asyncio
    async def test_db_create_meal_from_estimate_not_found(self, mock_pool):
        """Raises ValueError when the estimate does not exist."""
        _pool, _conn, _cursor = mock_pool

        with patch(
            "calorie_track_ai_bot.services.db.meals.db_get_estimate",
            return_value=None,
        ):
            data = MealCreateFromEstimateRequest(
                meal_date=date(2024, 1, 1),
                meal_type=MealType.snack,
                estimate_id="00000000-0000-0000-0000-000000000999",
                overrides=None,
            )

            with pytest.raises(ValueError, match="Estimate not found"):
                await db_create_meal_from_estimate(data, "user123")

    # ------------------------------------------------------------------
    # db_delete_meal
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_delete_meal_unlinks_photos_before_delete(self, mock_pool):
        """Photos are detached before the meal row is deleted (FK has no ON DELETE action)."""
        _pool, conn, cursor = mock_pool
        cursor.fetchone.return_value = {"id": "meal-1"}

        assert await db_delete_meal("meal-1") is True

        statements = [call[0][0] for call in conn.execute.call_args_list]
        assert statements[0].startswith("UPDATE photos SET meal_id = NULL")
        assert statements[1].startswith("DELETE FROM meals")
        assert all(call[0][1] == ("meal-1",) for call in conn.execute.call_args_list)

    @pytest.mark.asyncio
    async def test_db_delete_meal_not_found(self, mock_pool):
        """Returns False when no meal row was deleted."""
        _pool, _conn, cursor = mock_pool
        cursor.fetchone.return_value = None

        assert await db_delete_meal("missing") is False

    # ------------------------------------------------------------------
    # Inline analytics
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_db_upsert_inline_analytics(self, mock_pool):
        """db_upsert_inline_analytics returns an InlineAnalyticsDaily from the RETURNING row."""
        _pool, _conn, cursor = mock_pool

        daily = InlineAnalyticsDaily(
            id=uuid4(),
            date=date(2024, 1, 1),
            chat_type=InlineChatType.group,
            trigger_counts={"inline_query": 3},
            request_count=3,
            success_count=3,
            failure_count=0,
            permission_block_count=1,
            avg_ack_latency_ms=120,
            p95_result_latency_ms=480,
            accuracy_within_tolerance_pct=95.0,
            failure_reasons=[],
            last_updated_at=datetime.now(UTC),
        )

        cursor.fetchone.return_value = daily.model_dump(mode="json")

        result = await db_upsert_inline_analytics(daily)

        assert result.chat_type == InlineChatType.group
        assert result.trigger_counts["inline_query"] == 3

    @pytest.mark.asyncio
    async def test_db_fetch_inline_analytics(self, mock_pool):
        """db_fetch_inline_analytics returns a list of InlineAnalyticsDaily."""
        _pool, _conn, cursor = mock_pool

        daily = InlineAnalyticsDaily(
            id=uuid4(),
            date=date(2024, 2, 1),
            chat_type=InlineChatType.private,
            trigger_counts={},
            request_count=0,
            success_count=0,
            failure_count=0,
            permission_block_count=0,
            avg_ack_latency_ms=0,
            p95_result_latency_ms=0,
            accuracy_within_tolerance_pct=0.0,
            failure_reasons=[],
            last_updated_at=datetime.now(UTC),
        )

        cursor.fetchall.return_value = [daily.model_dump(mode="json")]

        results = await db_fetch_inline_analytics(date(2024, 2, 1), date(2024, 2, 1), "private")

        assert len(results) == 1
        assert results[0].chat_type == InlineChatType.private

    @pytest.mark.asyncio
    async def test_db_increment_inline_permission_block_creates_default(self, monkeypatch):
        """When no existing row, a default is created and permission_block_count is incremented."""
        saved_daily = InlineAnalyticsDaily(
            id=uuid4(),
            date=date(2024, 3, 1),
            chat_type=InlineChatType.group,
            trigger_counts={},
            request_count=0,
            success_count=0,
            failure_count=0,
            permission_block_count=1,
            avg_ack_latency_ms=0,
            p95_result_latency_ms=0,
            accuracy_within_tolerance_pct=0.0,
            failure_reasons=[],
            last_updated_at=datetime.now(UTC),
        )

        mock_fetch = AsyncMock(return_value=[])
        mock_upsert = AsyncMock(return_value=saved_daily)
        monkeypatch.setattr(
            inline_analytics_module,
            "db_fetch_inline_analytics",
            mock_fetch,
        )
        monkeypatch.setattr(
            inline_analytics_module,
            "db_upsert_inline_analytics",
            mock_upsert,
        )

        result = await db_increment_inline_permission_block(
            date_value=date(2024, 3, 1), chat_type=InlineChatType.group
        )

        mock_fetch.assert_awaited_once()
        mock_upsert.assert_awaited_once()
        assert result.permission_block_count == 1

    @pytest.mark.asyncio
    async def test_db_increment_inline_permission_block_updates_existing(self, monkeypatch):
        """When an existing row is found, permission_block_count is incremented by the given
        amount."""
        existing_daily = InlineAnalyticsDaily(
            id=uuid4(),
            date=date(2024, 4, 1),
            chat_type=InlineChatType.group,
            trigger_counts={},
            request_count=0,
            success_count=0,
            failure_count=0,
            permission_block_count=2,
            avg_ack_latency_ms=0,
            p95_result_latency_ms=0,
            accuracy_within_tolerance_pct=0.0,
            failure_reasons=[],
            last_updated_at=datetime.now(UTC),
        )

        async def fake_upsert(daily: InlineAnalyticsDaily) -> InlineAnalyticsDaily:
            return daily

        mock_fetch = AsyncMock(return_value=[existing_daily])
        mock_upsert = AsyncMock(side_effect=fake_upsert)
        monkeypatch.setattr(
            inline_analytics_module,
            "db_fetch_inline_analytics",
            mock_fetch,
        )
        monkeypatch.setattr(
            inline_analytics_module,
            "db_upsert_inline_analytics",
            mock_upsert,
        )

        result = await db_increment_inline_permission_block(
            date_value=date(2024, 4, 1), chat_type=InlineChatType.group, increment=3
        )

        mock_fetch.assert_awaited_once()
        mock_upsert.assert_awaited_once()
        assert result.permission_block_count == 5

    # ------------------------------------------------------------------
    # db_create_or_update_goal
    # ------------------------------------------------------------------

    GOAL_USER_ID = "1d882190-ac3f-4a06-8a44-20e46bafb9a5"

    @pytest.fixture
    def goal_user(self):
        with patch(
            "calorie_track_ai_bot.services.db.goals.resolve_user_id",
            AsyncMock(return_value=self.GOAL_USER_ID),
        ) as resolve:
            yield resolve

    @pytest.mark.asyncio
    async def test_db_create_or_update_goal_upserts_on_user_id(self, mock_pool, goal_user):
        """The goal is saved with one INSERT ... ON CONFLICT (user_id) and the row is returned."""
        _pool, conn, cursor = mock_pool
        saved = {"id": str(uuid4()), "user_id": self.GOAL_USER_ID, "daily_kcal_target": 1800}
        cursor.fetchone.return_value = saved

        result = await db_create_or_update_goal("59357664", 1800)

        assert result == saved
        goal_user.assert_awaited_once_with("59357664")
        conn.execute.assert_awaited_once()
        sql, params = conn.execute.await_args.args
        assert "ON CONFLICT (user_id) DO UPDATE" in sql
        assert "RETURNING *" in sql
        assert params == (self.GOAL_USER_ID, 1800)

    @pytest.mark.asyncio
    async def test_db_create_or_update_goal_names_missing_unique_index(self, mock_pool, goal_user):
        """Without the unique index, the error is logged with the index name and re-raised."""
        _pool, conn, _cursor = mock_pool
        conn.execute.side_effect = errors.InvalidColumnReference(
            "there is no unique or exclusion constraint matching the ON CONFLICT specification"
        )

        with (
            patch("calorie_track_ai_bot.services.db.goals.logger") as logger,
            pytest.raises(errors.InvalidColumnReference),
        ):
            await db_create_or_update_goal("59357664", 1800)

        assert "idx_goals_user_id_unique" in logger.error.call_args.args[0]

    @pytest.mark.asyncio
    async def test_db_create_or_update_goal_unknown_user(self, mock_pool, goal_user):
        """A Telegram user without a users row is rejected before any SQL runs."""
        _pool, conn, _cursor = mock_pool
        goal_user.return_value = None

        with pytest.raises(ValueError):
            await db_create_or_update_goal("59357664", 1800)

        conn.execute.assert_not_awaited()
