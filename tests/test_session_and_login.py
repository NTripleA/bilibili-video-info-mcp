"""Existing session storage and login-status behaviour must remain intact."""

from bilibili_video_info_mcp import bilibili_api

from .conftest import make_response

NAV_LOGGED_IN = {
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

NAV_ANONYMOUS = {"code": 0, "data": {"isLogin": False}}


def test_login_status_reports_profile_when_logged_in(http, saved_session):
    saved_session()
    http.route("web-interface/nav", make_response(json_data=NAV_LOGGED_IN))

    status = bilibili_api.check_login_status()

    assert status == {
        "is_logged_in": True,
        "uname": "TestUser",
        "mid": 10086,
        "level": 5,
        "vip_status": "VIP",
        "vip_type": 2,
        "coins": 100.0,
    }


def test_login_status_reports_logged_out_without_session(http):
    http.route("web-interface/nav", make_response(json_data=NAV_ANONYMOUS))

    status = bilibili_api.check_login_status()

    assert status["is_logged_in"] is False
    assert "login_bilibili" in status["message"]


def test_login_status_surfaces_transport_errors(http):
    http.route("web-interface/nav", make_response(status_code=500))

    status = bilibili_api.check_login_status()

    assert status["is_logged_in"] is False
    assert "Failed to check login status" in status["error"]


def test_save_session_roundtrips_through_the_session_file():
    saved = bilibili_api.save_session(
        "sessdata-1", "jct-1", "", user_info={"is_logged_in": True, "mid": 555}
    )
    bilibili_api._in_memory_session.clear()

    session = bilibili_api.get_session()

    assert saved is True
    assert session["SESSDATA"] == "sessdata-1"
    assert session["DedeUserID"] == "555"
    assert bilibili_api.get_auth_cookies()["DedeUserID"] == "555"


def test_in_memory_session_takes_priority_over_the_file(saved_session):
    saved_session()

    bilibili_api.set_in_memory_session("memory-sessdata", "memory-jct", "999")

    assert bilibili_api.get_auth_cookies() == {
        "SESSDATA": "memory-sessdata",
        "bili_jct": "memory-jct",
        "DedeUserID": "999",
    }


def test_logout_clears_credentials(saved_session):
    saved_session()
    bilibili_api.set_in_memory_session("memory-sessdata", "memory-jct", "999")

    cleared = bilibili_api.clear_session()

    assert cleared is True
    assert bilibili_api.get_auth_cookies() == {}
    assert bilibili_api.is_authenticated() is False


def test_parse_cookie_string_handles_header_and_bare_token():
    header = bilibili_api.parse_cookie_string(
        "Cookie: SESSDATA=abc%2C123; bili_jct=xyz; DedeUserID=42"
    )

    assert header == {"SESSDATA": "abc%2C123", "bili_jct": "xyz", "DedeUserID": "42"}
    assert bilibili_api.parse_cookie_string("bare-sessdata-token") == {
        "SESSDATA": "bare-sessdata-token"
    }


def test_extract_bvid_from_url_and_short_link(http):
    http.route(
        "b23.tv",
        make_response(url="https://www.bilibili.com/video/BV194tn6pE8o"),
    )

    assert bilibili_api.extract_bvid("https://www.bilibili.com/video/BV1x341177NN") == "BV1x341177NN"
    assert bilibili_api.extract_bvid("https://b23.tv/abcdef") == "BV194tn6pE8o"
    assert bilibili_api.extract_bvid("https://www.bilibili.com/") is None
