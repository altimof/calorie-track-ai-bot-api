from ._base import resolve_user_id
from .estimates import db_get_estimate, db_get_user_estimate, db_save_estimate
from .goals import db_create_or_update_goal, db_get_goal
from .inline_analytics import (
    db_fetch_inline_analytics,
    db_increment_inline_permission_block,
    db_upsert_inline_analytics,
)
from .meals import (
    _enhance_meal_with_related_data as _enhance_meal_with_related_data,
)
from .meals import (
    db_create_meal_from_estimate,
    db_create_meal_from_manual,
    db_delete_meal,
    db_get_meal,
    db_get_meal_with_photos,
    db_get_meals_calendar_summary,
    db_get_meals_with_photos,
    db_update_meal,
    db_update_meal_with_macros,
)
from .photos import db_create_photo, db_get_photo, db_get_user_photo
from .summaries import db_get_daily_summary, db_get_summaries_by_date_range, db_get_today_data
from .ui_config import (
    db_cleanup_old_ui_configurations,
    db_create_ui_configuration,
    db_delete_ui_configuration,
    db_get_ui_configuration,
    db_get_ui_configurations_by_user,
    db_update_ui_configuration,
)
from .users import db_get_or_create_user, db_get_user

__all__ = [
    "db_cleanup_old_ui_configurations",
    "db_create_meal_from_estimate",
    "db_create_meal_from_manual",
    "db_create_or_update_goal",
    "db_create_photo",
    "db_create_ui_configuration",
    "db_delete_meal",
    "db_delete_ui_configuration",
    "db_fetch_inline_analytics",
    "db_get_daily_summary",
    "db_get_estimate",
    "db_get_goal",
    "db_get_meal",
    "db_get_meal_with_photos",
    "db_get_meals_calendar_summary",
    "db_get_meals_with_photos",
    "db_get_or_create_user",
    "db_get_photo",
    "db_get_summaries_by_date_range",
    "db_get_today_data",
    "db_get_ui_configuration",
    "db_get_ui_configurations_by_user",
    "db_get_user",
    "db_get_user_estimate",
    "db_get_user_photo",
    "db_increment_inline_permission_block",
    "db_save_estimate",
    "db_update_meal",
    "db_update_meal_with_macros",
    "db_update_ui_configuration",
    "db_upsert_inline_analytics",
    "resolve_user_id",
]
