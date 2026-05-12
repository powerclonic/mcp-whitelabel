import uvicorn

from src.config.settings import settings
from src.server.app import app


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

