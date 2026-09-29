"""Entry point: python app.py"""
import uvicorn

from promptcheck.config import load_settings
from promptcheck.main import create_app

if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
