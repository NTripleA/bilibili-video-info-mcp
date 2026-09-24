"""Remote deployment configuration must preserve Host/Origin protection."""

import asyncio
import runpy
from pathlib import Path

import pytest
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

import remote_server


@pytest.fixture(autouse=True)
def isolated_remote_settings(monkeypatch):
    for name in ("MCP_ALLOWED_HOSTS", "MCP_ALLOWED_ORIGINS", "PORT"):
        monkeypatch.delenv(name, raising=False)
    settings = remote_server.mcp.settings
    original = {
        name: getattr(settings, name)
        for name in ("host", "port", "stateless_http", "transport_security")
    }
    yield
    for name, value in original.items():
        setattr(settings, name, value)


def validate(host, origin=None):
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    request = Request({"type": "http", "headers": headers, "method": "GET", "path": "/mcp"})
    middleware = TransportSecurityMiddleware(remote_server.mcp.settings.transport_security)
    return asyncio.run(middleware.validate_request(request))


def test_defaults_allow_loopback_and_reject_remote_requests():
    remote_server.configure_remote_server()
    assert remote_server.mcp.settings.transport_security.enable_dns_rebinding_protection
    for host in ("127.0.0.1:8000", "localhost:8000", "[::1]:8000"):
        assert validate(host, f"http://{host}") is None
    assert validate("mcp.example.com").status_code == 421
    assert validate("localhost:8000", "https://evil.example.com").status_code == 403


def test_environment_allows_only_configured_remote_host_and_origin(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", " mcp.example.com, ,mcp.example.com:443 ")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", " https://mcp.example.com, ")
    monkeypatch.setenv("PORT", "9000")
    remote_server.configure_remote_server()
    assert remote_server.mcp.settings.port == 9000
    assert validate("mcp.example.com", "https://mcp.example.com") is None
    assert validate("mcp.example.com:443") is None
    assert validate("localhost:9000") is None
    assert validate("mcp.example.com.evil.example.com").status_code == 421
    assert validate("mcp.example.com:8443").status_code == 421
    assert validate("mcp.example.com", "https://evil.example.com").status_code == 403


def test_empty_environment_does_not_disable_protection(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", " , , ")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "")
    remote_server.configure_remote_server()
    assert validate("evil.example.com").status_code == 421


def test_script_entry_point_configures_before_starting(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.com")
    calls = []

    def record_run(**kwargs):
        calls.append(kwargs)
        assert validate("mcp.example.com") is None

    monkeypatch.setattr(remote_server.mcp, "run", record_run)
    runpy.run_path(str(Path(remote_server.__file__)), run_name="__main__")
    assert calls == [{"transport": "streamable-http"}]
