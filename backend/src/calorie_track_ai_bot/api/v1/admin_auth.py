"""Admin-only access for operational routes (webhook management, analytics, dev diagnostics)."""

import hmac

from fastapi import HTTPException, Request

from ...services import config

BEARER_SCHEME = "bearer "


def require_admin_token(request: Request) -> None:
    """Allow the request only with `Authorization: Bearer <ADMIN_API_TOKEN>`.

    Without ADMIN_API_TOKEN configured these routes are disabled and answer 404,
    so they are off unless an operator opts in.

    Use as a FastAPI dependency: dependencies=[Depends(require_admin_token)]
    """
    if not config.ADMIN_API_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")

    authorization = request.headers.get("authorization", "")
    if authorization[: len(BEARER_SCHEME)].lower() != BEARER_SCHEME:
        raise HTTPException(status_code=401, detail="Admin token required")

    token = authorization[len(BEARER_SCHEME) :].strip()
    if not hmac.compare_digest(token.encode(), config.ADMIN_API_TOKEN.encode()):
        config.logger.warning("Rejected request with an invalid admin token")
        raise HTTPException(status_code=401, detail="Admin token required")
