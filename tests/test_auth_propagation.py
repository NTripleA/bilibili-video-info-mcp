"""Auth cookies must reach every Bilibili API path that can benefit from them.

Regression cover for the bug where only SESSDATA and bili_jct were attached: Bilibili's
anti-bot gate keys on DedeUserID, so /x/web-interface/view returned HTTP 412 while the
nav-based login check kept reporting a healthy session.
"""

import pytest

from bilibili_video_info_mcp import bilibili_api

from .conftest import make_response

VIEW_OK = {
    "code": 0,
    "data": {
        "bvid": "BV194tn6pE8o",
        "aid": 111222333,
        "cid": 444555666,
        "title": "Test Video",
        "desc": "Test description",
        "owner": {"name": "Uploader", "mid": 42},
        "stat": {"view": 10, "danmaku": 2, "reply": 3, "like": 4},
        "duration": 120,
        "tname": "Tech",
        "pubdate": 1700000000,
        "pic": "https://i0.hdslb.com/cover.jpg",
        "pages": [],
    },
}

NAV_OK = {
    "code": 0,
    "data": {
        "isLogin": True,
        "uname": "TestUser",
        "mid": 10086,
        "level_info": {"current_level": 5},
        "vipStatus": 1,
        "vipType": 2,
        "money": 100.0,
    },
}

EXPECTED_AUTH_COOKIES = ["DedeUserID", "SESSDATA", "bili_jct"]


# --------------------------------------------------------------------------- anonymous


def test_anonymous_session_has_no_auth_cookies():
    assert bilibili_api.get_auth_cookies() == {}
    assert bilibili_api.is_authenticated() is False


def test_anonymous_video_request_sends_no_auth_cookies(http):
    http.route("web-interface/view", make_response(json_data=VIEW_OK))

    details, error = bilibili_api.get_video_details("BV194tn6pE8o")

    assert error is None
    assert details["title"] == "Test Video"
    call = http.call_to("web-interface/view")
    assert call.cookies == {}
    assert "Cookie" not in call.headers


def test_public_endpoints_still_work_without_credentials(http):
    """No credentials must never mean "refuse to try" - anonymous requests proceed."""
    http.route("web-interface/view", make_response(json_data=VIEW_OK))
    http.route("v2/reply", make_response(json_data={"code": 0, "data": {"replies": []}}))

    aid, cid, error = bilibili_api.get_video_basic_info("BV194tn6pE8o")
    comments, comments_error = bilibili_api.get_comments(aid)

    assert (aid, cid, error) == (111222333, 444555666, None)
    assert comments_error is None
    assert comments == []


# ------------------------------------------------------------------- saved credentials


def test_saved_session_file_is_loaded_into_auth_cookies(saved_session):
    data = saved_session()

    cookies = bilibili_api.get_auth_cookies()

    assert sorted(cookies) == EXPECTED_AUTH_COOKIES
    assert cookies["SESSDATA"] == data["SESSDATA"]
    assert cookies["bili_jct"] == data["bili_jct"]
    assert cookies["DedeUserID"] == data["DedeUserID"]
    assert bilibili_api.is_authenticated() is True


def test_environment_variables_still_authenticate(monkeypatch):
    monkeypatch.setenv("SESSDATA", "env-sessdata")
    monkeypatch.setenv("BILI_JCT", "env-bilijct")
    monkeypatch.setenv("DedeUserID", "20172")

    assert bilibili_api.get_auth_cookies() == {
        "SESSDATA": "env-sessdata",
        "bili_jct": "env-bilijct",
        "DedeUserID": "20172",
    }


def test_dede_user_id_falls_back_to_saved_profile_mid(saved_session):
    saved_session(DedeUserID="", user_info={"is_logged_in": True, "mid": 777})

    assert bilibili_api.get_auth_cookies()["DedeUserID"] == "777"


def test_dede_user_id_is_resolved_via_nav_when_missing(http, saved_session):
    saved_session(DedeUserID="", user_info={})
    http.route("web-interface/nav", make_response(json_data=NAV_OK))

    cookies = bilibili_api.get_auth_cookies()

    assert cookies["DedeUserID"] == "10086"
    assert http.call_to("web-interface/nav").cookies == {"SESSDATA": "test-sessdata-value-abc123"}


def test_partial_session_omits_empty_cookies(saved_session):
    saved_session(bili_jct="", DedeUserID="", user_info={})

    assert sorted(bilibili_api.get_auth_cookies()) == ["SESSDATA"]


# --------------------------------------------------------- authenticated request paths


@pytest.mark.parametrize(
    "call, url_fragment",
    [
        (lambda: bilibili_api.get_video_details("BV194tn6pE8o"), "web-interface/view"),
        (lambda: bilibili_api.get_video_basic_info("BV194tn6pE8o"), "web-interface/view"),
        (lambda: bilibili_api.get_subtitles(1, 2), "player/wbi/v2"),
        (lambda: bilibili_api.get_danmaku(2), "dm/list.so"),
        (lambda: bilibili_api.get_comments(1), "v2/reply"),
        (lambda: bilibili_api.check_login_status(), "web-interface/nav"),
    ],
    ids=["video_details", "video_basic_info", "subtitles", "danmaku", "comments", "login_status"],
)
def test_every_api_path_attaches_saved_credentials(http, saved_session, call, url_fragment):
    saved_session()
    http.route("web-interface/view", make_response(json_data=VIEW_OK))
    http.route("web-interface/nav", make_response(json_data=NAV_OK))
    http.route("player/wbi/v2", make_response(json_data={"code": 0, "data": {}}))
    http.route("dm/list.so", make_response(content=b"<i></i>"))
    http.route("v2/reply", make_response(json_data={"code": 0, "data": {"replies": []}}))

    call()

    request = http.call_to(url_fragment)
    assert request.cookie_names == EXPECTED_AUTH_COOKIES
    assert request.cookies["SESSDATA"] == "test-sessdata-value-abc123"
    assert request.cookies["bili_jct"] == "test-bilijct-value-def456"
    assert request.cookies["DedeUserID"] == "10086"


def test_basic_info_consumers_inherit_authentication(http, saved_session):
    """subtitles/danmaku/comments all resolve aid+cid through the view endpoint first."""
    saved_session()
    http.route("web-interface/view", make_response(json_data=VIEW_OK))
    http.route("player/wbi/v2", make_response(json_data={"code": 0, "data": {}}))
    http.route("dm/list.so", make_response(content=b"<i></i>"))
    http.route("v2/reply", make_response(json_data={"code": 0, "data": {"replies": []}}))

    aid, cid, error = bilibili_api.get_video_basic_info("BV194tn6pE8o")
    assert error is None
    bilibili_api.get_subtitles(aid, cid)
    bilibili_api.get_danmaku(cid)
    bilibili_api.get_comments(aid)

    assert len(http.calls) == 4
    for call in http.calls:
        assert call.cookie_names == EXPECTED_AUTH_COOKIES


def test_browser_headers_sent_on_every_request(http, saved_session):
    saved_session()
    http.route("web-interface/view", make_response(json_data=VIEW_OK))

    bilibili_api.get_video_details("BV194tn6pE8o")

    headers = http.call_to("web-interface/view").headers
    assert headers["Referer"] == "https://www.bilibili.com/"
    assert "Mozilla/5.0" in headers["User-Agent"]


def test_subtitle_content_from_bilibili_cdn_is_authenticated(http, saved_session):
    saved_session()
    subtitle_meta = {
        "code": 0,
        "data": {
            "subtitle": {
                "subtitles": [
                    {
                        "lan": "zh-CN",
                        "lan_doc": "中文",
                        "subtitle_url": "//aisubtitle.hdslb.com/sub.json",
                    }
                ]
            }
        },
    }
    http.route("player/wbi/v2", make_response(json_data=subtitle_meta))
    http.route(
        "aisubtitle.hdslb.com",
        make_response(json_data={"body": [{"from": 0, "to": 1, "content": "hello"}]}),
    )

    subtitles, error = bilibili_api.get_subtitles(1, 2)

    assert error is None
    assert subtitles[0]["transcript"] == "hello"
    assert subtitles[0]["language"] == "Chinese (Simplified)"
    assert http.call_to("aisubtitle.hdslb.com").cookie_names == EXPECTED_AUTH_COOKIES


def test_credentials_are_not_sent_to_non_bilibili_hosts(http, saved_session):
    saved_session()
    http.route("evil.example.com", make_response(json_data={}))

    bilibili_api.bili_get("https://evil.example.com/collect")

    call = http.call_to("evil.example.com")
    assert call.cookies == {}
    assert "Cookie" not in call.headers


def test_login_flow_endpoints_stay_anonymous(http, saved_session):
    """QR generation/polling must not ride on an existing session."""
    saved_session()
    http.route(
        "qrcode/generate",
        make_response(json_data={"code": 0, "data": {"url": "https://x", "qrcode_key": "k"}}),
    )
    http.route("qrcode/poll", make_response(json_data={"code": 0, "data": {"code": 86101}}))

    bilibili_api.get_qrcode()
    bilibili_api.poll_qrcode("k")

    assert http.call_to("qrcode/generate").cookies == {}
    assert http.call_to("qrcode/poll").cookies == {}
