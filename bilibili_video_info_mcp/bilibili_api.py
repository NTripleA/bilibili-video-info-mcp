import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

# Bilibili API endpoints
API_GET_VIEW_INFO = "https://api.bilibili.com/x/web-interface/view"
API_GET_SUBTITLE = "https://api.bilibili.com/x/player/wbi/v2"
API_GET_DANMAKU = "https://api.bilibili.com/x/v1/dm/list.so"
API_GET_COMMENTS = "https://api.bilibili.com/x/v2/reply"
API_NAV = "https://api.bilibili.com/x/web-interface/nav"
API_QRCODE_GENERATE = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
API_QRCODE_POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

# Default Headers for requests
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# Session file locations
PRIMARY_SESSION_FILE = Path.home() / ".config" / "bilibili-video-info-mcp" / "session.json"
LOCAL_SESSION_FILE = Path(".sessdata")

# In-memory session cache
_in_memory_session: dict[str, Any] = {}


def get_session() -> dict[str, Any]:
    """Retrieve current session dict, prioritizing memory, then env, then session file."""
    if _in_memory_session.get("SESSDATA"):
        return _in_memory_session.copy()

    # Check environment variables
    env_sessdata = os.getenv("SESSDATA")
    if env_sessdata and env_sessdata.strip():
        return {
            "SESSDATA": env_sessdata.strip(),
            "bili_jct": os.getenv("BILI_JCT", "").strip(),
            "DedeUserID": os.getenv("DedeUserID", "").strip(),
            "source": "environment",
        }

    # Check persistent session files
    for path in (PRIMARY_SESSION_FILE, LOCAL_SESSION_FILE):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("SESSDATA"):
                        data["source"] = str(path)
                        return data
            except Exception:
                pass

    return {}


def get_sessdata() -> str | None:
    """Get SESSDATA cookie string or None if unauthenticated."""
    session = get_session()
    return session.get("SESSDATA")


def set_in_memory_session(
    sessdata: str,
    bili_jct: str = "",
    dede_user_id: str = "",
    user_info: dict[str, Any] | None = None,
) -> None:
    """Set session in memory for the current process."""
    global _in_memory_session
    _in_memory_session = {
        "SESSDATA": sessdata.strip(),
        "bili_jct": bili_jct.strip(),
        "DedeUserID": str(dede_user_id).strip(),
        "user_info": user_info or {},
    }


def save_session(
    sessdata: str,
    bili_jct: str = "",
    dede_user_id: str = "",
    user_info: dict[str, Any] | None = None,
) -> bool:
    """Save session to memory and persistent disk file."""
    set_in_memory_session(sessdata, bili_jct, dede_user_id, user_info)
    data = {
        "SESSDATA": sessdata.strip(),
        "bili_jct": bili_jct.strip(),
        "DedeUserID": str(dede_user_id).strip(),
        "user_info": user_info or {},
        "saved_at": time.time(),
    }

    # Try primary location in ~/.config
    try:
        PRIMARY_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PRIMARY_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        pass

    # Fallback to local file in current working directory
    try:
        with open(LOCAL_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def clear_session() -> bool:
    """Clear in-memory session and persistent session files."""
    global _in_memory_session
    _in_memory_session = {}
    cleared = False
    for path in (PRIMARY_SESSION_FILE, LOCAL_SESSION_FILE):
        try:
            if path.exists():
                path.unlink()
                cleared = True
        except Exception:
            pass
    return cleared


def check_login_status() -> dict[str, Any]:
    """Query Bilibili nav API to check current login state and user info."""
    headers = _get_headers()
    try:
        resp = requests.get(API_NAV, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
            user_data = data["data"]
            return {
                "is_logged_in": True,
                "uname": user_data.get("uname", ""),
                "mid": user_data.get("mid", 0),
                "level": user_data.get("level_info", {}).get("current_level", 0),
                "vip_status": "VIP" if user_data.get("vipStatus") == 1 else "Normal",
                "vip_type": user_data.get("vipType", 0),
                "coins": user_data.get("money", 0),
            }
        return {
            "is_logged_in": False,
            "message": "Not logged in. Use the 'login_bilibili' tool to authenticate.",
        }
    except Exception as e:
        return {
            "is_logged_in": False,
            "error": f"Failed to check login status: {e}",
        }


def get_qrcode() -> dict[str, Any]:
    """Fetch a new QR code for Bilibili login from official passport API."""
    try:
        resp = requests.get(API_QRCODE_GENERATE, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 and "data" in data:
            return {
                "success": True,
                "url": data["data"]["url"],
                "qrcode_key": data["data"]["qrcode_key"],
            }
        return {"success": False, "error": data.get("message", "Failed to generate QR code")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def poll_qrcode(qrcode_key: str) -> dict[str, Any]:
    """Poll the status of a login QR code from official passport API."""
    try:
        params = {"qrcode_key": qrcode_key}
        resp = requests.get(API_QRCODE_POLL, params=params, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 0:
            poll_data = data.get("data", {})
            status_code = poll_data.get("code")

            if status_code == 0:
                # Login successful - extract cookies
                cookies = resp.cookies.get_dict()
                sessdata = cookies.get("SESSDATA")
                bili_jct = cookies.get("bili_jct", "")
                dede_user_id = cookies.get("DedeUserID", "")

                # Fallback: extract from returned redirect URL query params
                redirect_url = poll_data.get("url", "")
                if redirect_url:
                    parsed_params = parse_qs(urlparse(redirect_url).query)
                    if not sessdata and "SESSDATA" in parsed_params:
                        sessdata = parsed_params["SESSDATA"][0]
                    if not bili_jct and "bili_jct" in parsed_params:
                        bili_jct = parsed_params["bili_jct"][0]
                    if not dede_user_id and "DedeUserID" in parsed_params:
                        dede_user_id = parsed_params["DedeUserID"][0]

                return {
                    "status": "success",
                    "code": 0,
                    "message": "Login successful",
                    "sessdata": sessdata,
                    "bili_jct": bili_jct,
                    "dede_user_id": dede_user_id,
                }
            elif status_code == 86101:
                return {"status": "waiting", "code": 86101, "message": "Waiting for scan..."}
            elif status_code == 86090:
                return {"status": "scanned", "code": 86090, "message": "Scanned! Please confirm on your mobile app."}
            elif status_code == 86038:
                return {"status": "expired", "code": 86038, "message": "QR code has expired."}
            else:
                return {"status": "unknown", "code": status_code, "message": poll_data.get("message", "Unknown status")}
        return {"status": "error", "message": data.get("message", "Polling failed")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def parse_cookie_string(raw: str) -> dict[str, str]:
    """Parse a pasted raw Cookie header or SESSDATA token into a dict."""
    raw = raw.strip()
    if not raw:
        return {}

    # Check if user pasted plain SESSDATA string directly (e.g. 1a2b3c...)
    if "=" not in raw and len(raw) > 10 and " " not in raw:
        return {"SESSDATA": raw}

    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()

    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k.strip()] = v.strip().strip('"').strip("'")
    return cookies


def extract_cookies_from_browsers() -> dict[str, str] | None:
    """Attempt to read Bilibili session cookies from local browser cookie stores."""
    # Try rookiepy
    try:
        import rookiepy
        records = rookiepy.load(["bilibili.com", ".bilibili.com"])
        cookies = {r["name"]: r["value"] for r in records if "bilibili.com" in str(r.get("domain", ""))}
        if cookies.get("SESSDATA"):
            return cookies
    except Exception:
        pass

    # Try browser_cookie3
    try:
        import browser_cookie3
        for loader in [
            browser_cookie3.chrome,
            browser_cookie3.firefox,
            browser_cookie3.safari,
            browser_cookie3.edge,
            browser_cookie3.brave,
            browser_cookie3.opera,
            browser_cookie3.chromium,
        ]:
            try:
                jar = loader(domain_name="bilibili.com")
                cookies = {cookie.name: cookie.value for cookie in jar if cookie.value}
                if cookies.get("SESSDATA"):
                    return cookies
            except Exception:
                continue
    except Exception:
        pass

    return None


def _get_headers() -> dict[str, str]:
    """Build request headers, injecting Cookie if a session is present."""
    headers = DEFAULT_HEADERS.copy()
    session = get_session()
    sessdata = session.get("SESSDATA")
    bili_jct = session.get("bili_jct")
    cookies = []
    if sessdata:
        cookies.append(f"SESSDATA={sessdata}")
    if bili_jct:
        cookies.append(f"bili_jct={bili_jct}")
    if cookies:
        headers["Cookie"] = "; ".join(cookies)
    return headers


def extract_bvid(url: str) -> str | None:
    """Extract BV ID from URL, following redirects for short links if needed."""
    # First try to extract the BV ID directly from the URL
    match = re.search(r"BV[a-zA-Z0-9_]+", url)
    if match:
        return match.group(0)

    # If it is a short link (such as b23.tv), follow redirects to get the full URL
    if "b23.tv" in url:
        try:
            response = requests.head(url, headers=_get_headers(), allow_redirects=True, timeout=10)
            if response.status_code == 200:
                # Get the final redirected URL
                final_url = response.url
                match = re.search(r"BV[a-zA-Z0-9_]+", final_url)
                if match:
                    return match.group(0)
        except requests.RequestException as e:
            print(f"Error resolving short URL: {e}")

    return None


LANGUAGE_NAMES: dict[str, str] = {
    "zh-CN": "Chinese (Simplified)",
    "zh-Hans": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "zh-Hant": "Chinese (Traditional)",
    "zh-HK": "Chinese (Hong Kong)",
    "ai-zh": "Chinese (AI Auto-generated)",
    "en": "English",
    "en-US": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
}


def get_video_details(bvid: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Fetch complete metadata and details for a given bvid.
    
    Returns:
        tuple (video_details_dict, error_dict)
    """
    headers = _get_headers()
    try:
        params_view = {"bvid": bvid}
        response_view = requests.get(API_GET_VIEW_INFO, params=params_view, headers=headers, timeout=10)

        if response_view.status_code == 412:
            return None, {
                "error": (
                    "Bilibili anti-bot check triggered (HTTP 412). "
                    "Please authenticate by calling 'login_bilibili' or setting the SESSDATA cookie."
                )
            }

        response_view.raise_for_status()
        data_view = response_view.json()

        if data_view.get("code") == -412:
            return None, {
                "error": (
                    "Request was blocked by Bilibili anti-bot protection (code -412). "
                    "Please authenticate using the 'login_bilibili' tool or configure SESSDATA."
                )
            }
        elif data_view.get("code") != 0:
            return None, {
                "error": f"Failed to get video info: {data_view.get('message', 'Unknown error')}",
                "details": data_view,
            }

        video_data = data_view.get("data", {})
        owner = video_data.get("owner", {})
        stat = video_data.get("stat", {})
        pages = video_data.get("pages", [])

        pubdate = video_data.get("pubdate")
        published_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(pubdate)) if pubdate else None

        details = {
            "bvid": video_data.get("bvid", bvid),
            "aid": video_data.get("aid"),
            "cid": video_data.get("cid"),
            "title": video_data.get("title", ""),
            "description": video_data.get("desc", ""),
            "uploader": {
                "name": owner.get("name", ""),
                "mid": owner.get("mid", 0),
            },
            "duration_seconds": video_data.get("duration", 0),
            "category": video_data.get("tname", ""),
            "published_at": published_at,
            "url": f"https://www.bilibili.com/video/{video_data.get('bvid', bvid)}",
            "cover_url": video_data.get("pic", ""),
            "stats": {
                "views": stat.get("view", 0),
                "danmaku": stat.get("danmaku", 0),
                "replies": stat.get("reply", 0),
                "likes": stat.get("like", 0),
                "coins": stat.get("coin", 0),
                "favorites": stat.get("favorite", 0),
                "shares": stat.get("share", 0),
            },
            "parts": [
                {
                    "page": p.get("page"),
                    "part_name": p.get("part"),
                    "duration_seconds": p.get("duration"),
                    "cid": p.get("cid"),
                }
                for p in pages
            ] if len(pages) > 1 else [],
        }
        return details, None
    except requests.RequestException as e:
        if hasattr(e, "response") and e.response is not None and e.response.status_code == 412:
            return None, {
                "error": (
                    "Bilibili anti-bot check triggered (HTTP 412). "
                    "Please authenticate by calling 'login_bilibili' or setting the SESSDATA cookie."
                )
            }
        return None, {"error": f"Failed to fetch video details: {e}"}


def get_video_basic_info(bvid: str) -> tuple[int | None, int | None, dict[str, Any] | None]:
    """Gets aid and cid for a given bvid."""
    details, error = get_video_details(bvid)
    if error:
        return None, None, error
    if not details:
        return None, None, {"error": "Failed to get video info"}
    return details.get("aid"), details.get("cid"), None


def get_subtitles(aid: int, cid: int):
    """Fetches subtitles for a given aid and cid."""
    headers = _get_headers()
    subtitles = []
    try:
        params_subtitle = {"aid": aid, "cid": cid}
        response_subtitle = requests.get(API_GET_SUBTITLE, params=params_subtitle, headers=headers, timeout=10)
        response_subtitle.raise_for_status()
        subtitle_data = response_subtitle.json()

        if subtitle_data.get("code") == 0 and subtitle_data.get("data", {}).get("subtitle", {}).get("subtitles"):
            for sub_meta in subtitle_data["data"]["subtitle"]["subtitles"]:
                if sub_meta.get("subtitle_url"):
                    try:
                        subtitle_json_url = f"https:{sub_meta['subtitle_url']}"
                        response_sub_content = requests.get(subtitle_json_url, headers=headers, timeout=10)
                        response_sub_content.raise_for_status()
                        sub_content = response_sub_content.json()
                        subtitle_body = sub_content.get("body", [])

                        content_list = []
                        lines = []
                        for item in subtitle_body:
                            text = item.get("content", "").strip()
                            if text:
                                content_list.append(text)
                                lines.append({
                                    "from": item.get("from"),
                                    "to": item.get("to"),
                                    "text": text,
                                })

                        lan_code = sub_meta.get("lan", "")
                        lang_name = LANGUAGE_NAMES.get(lan_code, sub_meta.get("lan_doc", lan_code or "Unknown"))

                        subtitles.append({
                            "lan": lan_code,
                            "language": lang_name,
                            "lan_doc": sub_meta.get("lan_doc", ""),
                            "transcript": "\n".join(content_list),
                            "lines": lines,
                            "content": content_list,
                        })
                    except requests.RequestException as e:
                        print(f"Could not fetch or parse subtitle content from {sub_meta.get('subtitle_url')}: {e}")
        return subtitles, None
    except requests.RequestException as e:
        if hasattr(e, "response") and e.response is not None and e.response.status_code == 412:
            return [], {
                "error": (
                    "Bilibili anti-bot check triggered (HTTP 412). "
                    "Please authenticate by calling 'login_bilibili' or setting the SESSDATA cookie."
                )
            }
        return [], {"error": f"Could not fetch subtitles: {e}"}


def get_danmaku(cid: int):
    """Fetches danmaku for a given cid."""
    headers = _get_headers()
    danmaku_list = []
    try:
        params_danmaku = {"oid": cid}
        response_danmaku = requests.get(API_GET_DANMAKU, params=params_danmaku, headers=headers, timeout=10)
        danmaku_content = response_danmaku.content.decode("utf-8", errors="ignore")
        root = ET.fromstring(danmaku_content)
        for d in root.findall("d"):
            if d.text:
                danmaku_list.append(d.text)
        return danmaku_list, None
    except (requests.RequestException, ET.ParseError) as e:
        if hasattr(e, "response") and getattr(e, "response", None) is not None and e.response.status_code == 412:
            return [], {
                "error": (
                    "Bilibili anti-bot check triggered (HTTP 412). "
                    "Please authenticate by calling 'login_bilibili' or setting the SESSDATA cookie."
                )
            }
        return [], {"error": f"Failed to get or parse danmaku: {e}"}


def get_comments(aid: int):
    """Fetches popular comments for a given aid."""
    headers = _get_headers()
    comments_list = []
    try:
        params_comments = {"type": 1, "oid": aid, "sort": 2}  # sort=2 fetches hot comments
        response_comments = requests.get(API_GET_COMMENTS, params=params_comments, headers=headers, timeout=10)
        response_comments.raise_for_status()
        comments_data = response_comments.json()

        if comments_data.get("code") == 0 and comments_data.get("data", {}).get("replies"):
            for comment in comments_data["data"]["replies"]:
                if comment.get("content", {}).get("message"):
                    comments_list.append({
                        "user": comment.get("member", {}).get("uname", "Unknown User"),
                        "content": comment["content"]["message"],
                        "likes": comment.get("like", 0),
                    })
        return comments_list, None
    except requests.RequestException as e:
        if hasattr(e, "response") and e.response is not None and e.response.status_code == 412:
            return [], {
                "error": (
                    "Bilibili anti-bot check triggered (HTTP 412). "
                    "Please authenticate by calling 'login_bilibili' or setting the SESSDATA cookie."
                )
            }
        return [], {"error": f"Failed to get comments: {e}"}
