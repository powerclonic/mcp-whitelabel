from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from src.config.settings import settings
from src.server.tools import register_tools

mcp = FastMCP(settings.app_name, version=settings.app_version)
register_tools(mcp)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.app_version})


def create_app() -> Starlette:
    mcp_app = mcp.http_app(path="/mcp")
    return Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )


app = create_app()

