"""
Local development entrypoint.

    python run.py

For production, use Gunicorn/Uvicorn workers directly (see README.md / Procfile).
"""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "development") != "production",
    )
