import os

from fastapi import Request
from fastapi.responses import JSONResponse


def public_dashboard_read_only() -> bool:
    return (
        os.getenv(
            "PUBLIC_DASHBOARD_READ_ONLY",
            "false",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def install_dashboard_security(app):
    """
    Render hosts a public read-only dashboard.

    GitHub Actions remains responsible for scheduled
    paper execution.

    When PUBLIC_DASHBOARD_READ_ONLY=true, external
    state-changing HTTP methods are blocked.

    Local development remains unchanged unless the
    environment variable is explicitly enabled.
    """

    @app.middleware("http")
    async def dashboard_read_only_middleware(
        request: Request,
        call_next,
    ):
        if (
            public_dashboard_read_only()
            and request.method
            not in {
                "GET",
                "HEAD",
                "OPTIONS",
            }
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Public dashboard is "
                        "read-only."
                    ),
                    "paperOnly": True,
                    "liveBrokerOrders": False,
                },
            )

        return await call_next(
            request
        )
