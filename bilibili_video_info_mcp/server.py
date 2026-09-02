"""
Core module for Bilibili Video Info MCP Server
"""

import argparse
import asyncio
import webbrowser
from mcp.server.fastmcp import FastMCP
from . import bilibili_api, browser_auth

# Create FastMCP server instance named BilibiliVideoInfo
mcp = FastMCP("BilibiliVideoInfo", dependencies=["requests"])


@mcp.tool(
    annotations={
        "title": "Login to Bilibili via Browser",
        "readOnlyHint": False,
        "openWorldHint": True,
    }
)
async def login_bilibili(timeout: int = 300) -> dict:
    """Open a browser page to log in to Bilibili and automatically capture session cookies.
    
    Supports:
    1. QR code scan via the Bilibili mobile app (fastest and recommended).
    2. Auto-detection from local browser stores (Chrome, Safari, Edge, Firefox, Brave, Arc).
    3. Manual SESSDATA or Cookie header paste.
    
    Args:
        timeout: Maximum seconds to wait for sign-in (default 300 seconds).
        
    Returns:
        Dictionary containing authentication result, user profile, and method.
    """
    capture_server = browser_auth.CookieCaptureServer()
    auth_url = capture_server.start()
    webbrowser.open(auth_url)

    try:
        sessdata, method, user_info = await capture_server.wait(timeout=float(timeout))
        uname = user_info.get("uname", "Authenticated User")
        return {
            "success": True,
            "message": f"Successfully logged in as {uname} via {method}. Session saved.",
            "method": method,
            "user": user_info,
        }
    except (TimeoutError, asyncio.TimeoutError):
        return {
            "success": False,
            "message": f"Timed out after {timeout}s waiting for browser login.",
            "auth_url": auth_url,
        }
    finally:
        capture_server.stop()


@mcp.tool(
    annotations={
        "title": "Get Bilibili Login Status",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
async def get_login_status() -> dict:
    """Check current Bilibili authentication state and user profile.
    
    Returns:
        Dictionary indicating whether the user is logged in, along with user details if active.
    """
    return bilibili_api.check_login_status()


@mcp.tool(
    annotations={
        "title": "Logout from Bilibili",
        "readOnlyHint": False,
        "openWorldHint": False,
    }
)
async def logout_bilibili() -> dict:
    """Log out and remove stored Bilibili session cookies.
    
    Returns:
        Confirmation dictionary indicating session was cleared.
    """
    cleared = bilibili_api.clear_session()
    return {
        "success": True,
        "message": "Bilibili session cleared." if cleared else "No active session found.",
    }


@mcp.tool(
    annotations={
        "title": "Get Bilibili Video Metadata",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
async def get_video_info(url: str) -> dict:
    """Get comprehensive metadata and details for a Bilibili video.
    
    Returns video title, description, uploader (name and ID), duration,
    category, publication date, engagement stats (views, likes, danmaku, comments, favorites, shares),
    and episode/part listings.
    
    Args:
        url: Bilibili video URL (e.g. https://www.bilibili.com/video/BV1x341177NN or short link https://b23.tv/xxxxx)
        
    Returns:
        Dictionary containing structured video metadata and statistics.
    """
    bvid = bilibili_api.extract_bvid(url)
    if not bvid:
        return {"error": f"Unable to extract BV ID from URL: {url}"}

    details, error = bilibili_api.get_video_details(bvid)
    if error:
        return {"error": error.get("error", "Failed to fetch video details")}

    return details or {"error": "No video details returned"}


@mcp.tool(
    annotations={
        "title": "Get Video Subtitles",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
async def get_subtitles(url: str) -> list:
    """Get subtitles and transcript from a Bilibili video.
    
    Args:
        url: Bilibili video URL, e.g., https://www.bilibili.com/video/BV1x341177NN or short link https://b23.tv/xxxxx
        
    Returns:
        List of subtitle tracks with language name (e.g. 'Chinese (Simplified)', 'English'),
        coherent transcript string, timestamped line segments, and raw line arrays.
    """
    bvid = bilibili_api.extract_bvid(url)
    if not bvid:
        return [f"Error: Unable to extract BV ID from URL: {url}"]

    aid, cid, error = bilibili_api.get_video_basic_info(bvid)
    if error:
        return [f"Failed to get video info: {error.get('error', 'Unknown error')}"]

    subtitles, error = bilibili_api.get_subtitles(aid, cid)
    if error:
        return [f"Failed to get subtitles: {error.get('error', 'Unknown error')}"]

    if not subtitles:
        return ["This video has no subtitles"]

    return subtitles


@mcp.tool(
    annotations={
        "title": "Get Video Danmaku",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
async def get_danmaku(url: str) -> list:
    """Get danmaku (bullet comments / on-screen comments) from a Bilibili video.
    
    Args:
        url: Bilibili video URL, e.g., https://www.bilibili.com/video/BV1x341177NN or short link https://b23.tv/xxxxx
        
    Returns:
        List of bullet comment strings from video viewers.
    """
    bvid = bilibili_api.extract_bvid(url)
    if not bvid:
        return [f"Error: Unable to extract BV ID from URL: {url}"]

    aid, cid, error = bilibili_api.get_video_basic_info(bvid)
    if error:
        return [f"Failed to get video info: {error.get('error', 'Unknown error')}"]

    danmaku, error = bilibili_api.get_danmaku(cid)
    if error:
        return [f"Failed to get danmaku: {error.get('error', 'Unknown error')}"]

    if not danmaku:
        return ["This video has no danmaku"]

    return danmaku


@mcp.tool(
    annotations={
        "title": "Get Video Comments",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
async def get_comments(url: str) -> list:
    """Get popular top comments from a Bilibili video.
    
    Args:
        url: Bilibili video URL, e.g., https://www.bilibili.com/video/BV1x341177NN or short link https://b23.tv/xxxxx
        
    Returns:
        List of popular comments with user name, comment content, and like counts.
    """
    bvid = bilibili_api.extract_bvid(url)
    if not bvid:
        return [f"Error: Unable to extract BV ID from URL: {url}"]

    aid, cid, error = bilibili_api.get_video_basic_info(bvid)
    if error:
        return [f"Failed to get video info: {error.get('error', 'Unknown error')}"]

    comments, error = bilibili_api.get_comments(aid)
    if error:
        return [f"Failed to get comments: {error.get('error', 'Unknown error')}"]

    if not comments:
        return ["This video has no popular comments"]

    return comments


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bilibili Video Info MCP Server")
    parser.add_argument('transport', nargs='?', default='stdio', choices=['stdio', 'sse', 'streamable-http'],
                        help='Transport type (stdio, sse, or streamable-http)')
    args = parser.parse_args()
    mcp.run(transport=args.transport)
