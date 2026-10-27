from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

FRONTEND_DIST = (
    PROJECT_ROOT
    / "frontend"
    / "dist"
)


def mount_dashboard(
    app: FastAPI,
) -> None:
    """
    Serve the compiled React/Vite dashboard from FastAPI.

    API routes are registered before this function is called,
    so API, health and documentation routes continue working.

    If frontend/dist does not exist during local development,
    FastAPI continues running without mounting the dashboard.
    """

    index_file = (
        FRONTEND_DIST
        / "index.html"
    )

    if not index_file.exists():
        return

    assets_dir = (
        FRONTEND_DIST
        / "assets"
    )

    if assets_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(
                directory=str(
                    assets_dir
                )
            ),
            name="dashboard-assets",
        )

    @app.get(
        "/",
        include_in_schema=False,
    )
    def production_dashboard():
        return FileResponse(
            str(index_file)
        )

    @app.get(
        "/{full_path:path}",
        include_in_schema=False,
    )
    def production_dashboard_fallback(
        full_path: str,
    ):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        requested_file = (
            FRONTEND_DIST
            / full_path
        )

        try:
            requested_file.resolve().relative_to(
                FRONTEND_DIST.resolve()
            )
        except ValueError:
            return FileResponse(
                str(index_file)
            )

        if (
            requested_file.exists()
            and requested_file.is_file()
        ):
            return FileResponse(
                str(requested_file)
            )

        return FileResponse(
            str(index_file)
        )
