"""python -m app: configure stdout logging and serve the API."""
import logging
import os
import sys

import uvicorn

from app.config import load_settings
from app.main import create_app


def main() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = load_settings()
    # our middleware logs each request, so uvicorn's own access log is off
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port,
                access_log=False, log_config=None)


if __name__ == "__main__":
    main()
