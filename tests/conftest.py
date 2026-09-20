"""Shared fixtures: every test runs against a fully isolated, offline session state."""

import json

import pytest
import requests

from bilibili_video_info_mcp import bilibili_api

AUTH_ENV_VARS = ("SESSDATA", "BILI_JCT", "DedeUserID")


@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    """Point session storage at a temp dir and clear env/memory credentials.

    Without this, a developer's real ~/.config session would leak into the tests.
    """
    monkeypatch.setattr(
        bilibili_api, "PRIMARY_SESSION_FILE", tmp_path / "config" / "session.json"
    )
    monkeypatch.setattr(bilibili_api, "LOCAL_SESSION_FILE", tmp_path / ".sessdata")
    monkeypatch.setattr(bilibili_api, "_in_memory_session", {})
    monkeypatch.setattr(bilibili_api, "_user_id_cache", {})
    for var in AUTH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    """Fail loudly if a test reaches the live Bilibili service."""

    def _blocked(*args, **kwargs):  # pragma: no cover - only runs on a test bug
        raise AssertionError(f"Unmocked HTTP request: {args!r}")

    monkeypatch.setattr(bilibili_api.requests, "request", _blocked)


class RecordedCall:
    """One captured outbound request."""

    def __init__(self, method, url, kwargs):
        self.method = method
        self.url = url
        self.headers = kwargs.get("headers") or {}
        self.cookies = kwargs.get("cookies") or {}
        self.params = kwargs.get("params") or {}
        self.kwargs = kwargs

    @property
    def cookie_names(self):
        return sorted(self.cookies)


class FakeHTTP:
    """Stand-in for requests.request: records calls and replays canned responses."""

    def __init__(self):
        self.calls = []
        self._routes = []
        self.default_response = make_response(json_data={"code": 0, "data": {}})

    def route(self, url_fragment, response):
        """Serve `response` for any URL containing `url_fragment`."""
        self._routes.append((url_fragment, response))

    def __call__(self, method, url, **kwargs):
        self.calls.append(RecordedCall(method, url, kwargs))
        for fragment, response in self._routes:
            if fragment in url:
                if isinstance(response, list):
                    return response.pop(0) if len(response) > 1 else response[0]
                if isinstance(response, Exception):
                    raise response
                return response
        return self.default_response

    def call_to(self, url_fragment):
        """The single recorded call whose URL contains `url_fragment`."""
        matches = [c for c in self.calls if url_fragment in c.url]
        assert matches, f"no request made to {url_fragment}; saw {[c.url for c in self.calls]}"
        return matches[-1]


def make_response(status_code=200, json_data=None, content=b"", url="https://www.bilibili.com/"):
    """Build a real requests.Response so raise_for_status()/json() behave normally."""
    response = requests.Response()
    response.status_code = status_code
    if json_data is not None:
        content = json.dumps(json_data).encode("utf-8")
        response.headers["Content-Type"] = "application/json"
    response._content = content
    response.url = url
    return response


@pytest.fixture
def http(monkeypatch):
    """Install FakeHTTP in place of the real transport."""
    fake = FakeHTTP()
    monkeypatch.setattr(bilibili_api.requests, "request", fake)
    return fake


@pytest.fixture
def saved_session(tmp_path, monkeypatch):
    """Write a session.json exactly like a real browser login produces."""

    def _write(**overrides):
        data = {
            "SESSDATA": "test-sessdata-value-abc123",
            "bili_jct": "test-bilijct-value-def456",
            "DedeUserID": "10086",
            "user_info": {"is_logged_in": True, "uname": "TestUser", "mid": 10086},
            "saved_at": 1700000000.0,
        }
        data.update(overrides)
        path = bilibili_api.PRIMARY_SESSION_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return data

    return _write
