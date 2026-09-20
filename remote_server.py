from bilibili_video_info_mcp.server import mcp
from mcp.server.transport_security import TransportSecuritySettings

mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8000
mcp.settings.stateless_http = True

mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "bilibili.ntriplealab.com",
        "bilibili.ntriplealab.com:*",
        "127.0.0.1:*",
        "localhost:*",
    ],
    allowed_origins=[
        "https://bilibili.ntriplealab.com",
        "https://bilibili.ntriplealab.com:*",
        "http://127.0.0.1:*",
        "http://localhost:*",
    ],
)

mcp.run(transport="streamable-http")
