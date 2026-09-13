"""Uvicorn entrypoint for Sovereign Headless Backend Platform."""

from core.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from core.config import settings

    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
