import os

from bilibili_video_info_mcp.server import mcp
from mcp.server.transport_security import TransportSecuritySettings


def _env_list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def configure_remote_server() -> None:
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.getenv("PORT", "8000"))
    mcp.settings.stateless_http = True
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
            *_env_list("MCP_ALLOWED_HOSTS"),
        ],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
            *_env_list("MCP_ALLOWED_ORIGINS"),
        ],
    )


if __name__ == "__main__":
    configure_remote_server()
    mcp.run(transport="streamable-http")
