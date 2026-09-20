"""HTTP 412 guidance must depend on whether credentials were actually attached,
and credential values must never surface in errors or logs."""

import logging

import pytest
import requests

from bilibili_video_info_mcp import bilibili_api

from .conftest import make_response

SESSDATA_VALUE = "test-sessdata-value-abc123"
BILI_JCT_VALUE = "test-bilijct-value-def456"

API_CALLS = {
    "video_details": (lambda: bilibili_api.get_video_details("BV194tn6pE8o"), "web-interface/view"),
    "subtitles": (lambda: bilibili_api.get_subtitles(1, 2), "player/wbi/v2"),
    "danmaku": (lambda: bilibili_api.get_danmaku(2), "dm/list.so"),
    "comments": (lambda: bilibili_api.get_comments(1), "v2/reply"),
}


def error_message(result):
    """Pull the error string out of any of the (value, error) tuples."""
    error = result[-1]
    assert error is not None, f"expected an error, got {result!r}"
    return error["error"]


# ------------------------------------------------------------------ 412 differentiation


@pytest.mark.parametrize("name", sorted(API_CALLS))
def test_412_without_credentials_tells_the_user_to_log_in(http, name):
    call, fragment = API_CALLS[name]
    http.route(fragment, make_response(status_code=412))

    message = error_message(call())

    assert "login_bilibili" in message
    assert "anonymously" in message
    assert "risk control" not in message.lower()


@pytest.mark.parametrize("name", sorted(API_CALLS))
def test_412_with_credentials_reports_risk_control_not_a_missing_login(http, saved_session, name):
    saved_session()
    call, fragment = API_CALLS[name]
    http.route(fragment, make_response(status_code=412))

    message = error_message(call())

    assert "risk control" in message.lower()
    assert "not necessarily" in message
    assert "sent anonymously" not in message


def test_412_guidance_differs_between_anonymous_and_authenticated(http, saved_session):
    http.route("web-interface/view", make_response(status_code=412))
    anonymous = bilibili_api._anti_bot_error()

    saved_session()
    authenticated = bilibili_api._anti_bot_error()

    assert anonymous["authenticated"] is False
    assert authenticated["authenticated"] is True
    assert anonymous["error"] != authenticated["error"]
    assert anonymous["http_status"] == authenticated["http_status"] == 412


def test_body_level_minus_412_is_treated_as_anti_bot(http, saved_session):
    saved_session()
    http.route("web-interface/view", make_response(json_data={"code": -412, "message": "risk"}))

    message = error_message(bilibili_api.get_video_details("BV194tn6pE8o"))

    assert "risk control" in message.lower()


def test_412_raised_as_an_exception_is_still_diagnosed(http, saved_session):
    saved_session()
    error = requests.HTTPError("412 Client Error")
    error.response = make_response(status_code=412)
    http.route("web-interface/view", error)

    message = error_message(bilibili_api.get_video_details("BV194tn6pE8o"))

    assert "risk control" in message.lower()


def test_non_412_errors_keep_their_own_message(http):
    http.route("web-interface/view", make_response(json_data={"code": -404, "message": "no video"}))

    message = error_message(bilibili_api.get_video_details("BV194tn6pE8o"))

    assert "no video" in message
    assert "412" not in message


# ------------------------------------------------------------------- credential hygiene


@pytest.mark.parametrize("name", sorted(API_CALLS))
def test_credentials_never_appear_in_error_messages(http, saved_session, caplog, name):
    saved_session()
    call, fragment = API_CALLS[name]
    http.route(fragment, make_response(status_code=412))

    with caplog.at_level(logging.DEBUG):
        message = error_message(call())

    assert SESSDATA_VALUE not in message
    assert BILI_JCT_VALUE not in message
    assert SESSDATA_VALUE not in caplog.text
    assert BILI_JCT_VALUE not in caplog.text


def test_credentials_never_appear_in_transport_failure_messages(http, saved_session, caplog):
    saved_session()
    http.route("web-interface/view", requests.ConnectionError("connection refused"))

    with caplog.at_level(logging.DEBUG):
        message = error_message(bilibili_api.get_video_details("BV194tn6pE8o"))

    assert "connection refused" in message
    assert SESSDATA_VALUE not in message + caplog.text
    assert BILI_JCT_VALUE not in message + caplog.text


def test_subtitle_fetch_failure_is_logged_without_credentials(http, saved_session, caplog):
    saved_session()
    subtitle_meta = {
        "code": 0,
        "data": {
            "subtitle": {
                "subtitles": [{"lan": "en", "subtitle_url": "//aisubtitle.hdslb.com/sub.json"}]
            }
        },
    }
    http.route("player/wbi/v2", make_response(json_data=subtitle_meta))
    http.route("aisubtitle.hdslb.com", requests.ConnectionError("cdn down"))

    with caplog.at_level(logging.DEBUG):
        subtitles, error = bilibili_api.get_subtitles(1, 2)

    assert error is None
    assert subtitles == []
    assert "cdn down" in caplog.text
    assert SESSDATA_VALUE not in caplog.text
