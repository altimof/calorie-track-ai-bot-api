from fastapi import APIRouter, Depends

from ...schemas import GoalRequest, GoalResponse
from ...services.db import db_create_or_update_goal, db_get_goal
from ...utils.error_handling import handle_api_errors
from .deps import get_authenticated_user_id

router = APIRouter()


@router.get("/goals", response_model=GoalResponse | None)
@handle_api_errors("goal retrieval")
async def get_goal(user_id: str = Depends(get_authenticated_user_id)):
    """Get user's goal."""
    goal = await db_get_goal(user_id)
    return goal


@router.post("/goals", response_model=GoalResponse)
@handle_api_errors("goal creation")
async def create_goal(goal_data: GoalRequest, user_id: str = Depends(get_authenticated_user_id)):
    """Create a new goal."""
    goal = await db_create_or_update_goal(user_id, goal_data.daily_kcal_target)
    return goal


@router.patch("/goals", response_model=GoalResponse)
@handle_api_errors("goal update")
async def update_goal(goal_data: GoalRequest, user_id: str = Depends(get_authenticated_user_id)):
    """Update user's goal."""
    goal = await db_create_or_update_goal(user_id, goal_data.daily_kcal_target)
    return goal
