# MCP Server for Bilibili Video Info

> [!NOTE]
> This MCP server and its documentation have been standardized to English for English AI assistants and LLM usage. Please refer to [README.md](./README.md) for the canonical documentation.

[![smithery badge](https://smithery.ai/badge/@lesir831/bilibili-video-info-mcp)](https://smithery.ai/server/@lesir831/bilibili-video-info-mcp)

A Model Context Protocol (MCP) server that empowers English AI assistants and LLMs to retrieve comprehensive information from Bilibili videos, including video metadata, full transcripts and subtitles (with English language labels), danmaku (bullet comments), and user comments.

---

## Authentication

Authentication is optional for many public videos, but recommended for higher rate limits, full subtitles, and avoiding Bilibili anti-bot rate limits.

### 1. Browser Login (Recommended)
You can simply tell your AI assistant: *"Log in to Bilibili"* or call `login_bilibili`. It will:
1. Open a secure local authentication page in your browser (`http://127.0.0.1:<port>/auth/<token>`).
2. Offer three convenient options:
   - **QR Code Scan** with the Bilibili mobile app (fastest and easiest).
   - **Auto-Detect** session cookies directly from your local browsers (Chrome, Safari, Edge, Firefox, Brave, Arc).
   - **Manual Input** to paste your `SESSDATA` cookie.
3. Automatically save the session locally (`~/.config/bilibili-video-info-mcp/session.json`) for all future requests.

### 2. Environment Variable (Alternative)
You can also supply `SESSDATA` directly via environment variables:
```bash
export SESSDATA="your_sessdata_value"
```

---

## Client Setup

### Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "bilibili-video-info-mcp": {
      "command": "uvx",
      "args": ["bilibili-video-info-mcp"]
    }
  }
}
```

### Cursor / Continue / Other MCP Clients
- **Command**: `uvx bilibili-video-info-mcp`
- **Transport**: `stdio`

### Server-Sent Events (SSE) Mode
```bash
cp .env.example .env
uvx run --env .env bilibili-video-info-mcp sse
```
Client configuration:
```json
{
  "mcpServers": {
    "bilibili-video-info-mcp": {
      "url": "http://127.0.0.1:$PORT$/sse"
    }
  }
}
```

### Streamable HTTP Mode
```bash
cp .env.example .env
uvx run --env .env bilibili-video-info-mcp streamable-http
```
Client configuration:
```json
{
  "mcpServers": {
    "bilibili-video-info-mcp": {
      "url": "http://127.0.0.1:$PORT$/mcp"
    }
  }
}
```

---

## MCP Tools List

### 1. `get_video_info`
Fetches complete metadata for a Bilibili video, including title, description, uploader profile, duration, publication date, categories, statistics (views, likes, coins, favorites, comments, danmaku), and multi-part episode listings.

```json
{
  "name": "get_video_info",
  "arguments": {
    "url": "https://www.bilibili.com/video/BV1x341177NN"
  }
}
```

### 2. `get_subtitles`
Retrieves subtitles and transcripts. Returns the full continuous transcript text, timestamped line segments, language codes, and human-readable English language names (e.g. `Chinese (Simplified)`, `Chinese (AI Auto-generated)`, `English`).

```json
{
  "name": "get_subtitles",
  "arguments": {
    "url": "https://www.bilibili.com/video/BV1x341177NN"
  }
}
```

### 3. `get_danmaku`
Fetches bullet comments (on-screen scrolling viewer reactions) from a video.

```json
{
  "name": "get_danmaku",
  "arguments": {
    "url": "https://www.bilibili.com/video/BV1x341177NN"
  }
}
```

### 4. `get_comments`
Retrieves top popular comments, usernames, and like counts from a video.

```json
{
  "name": "get_comments",
  "arguments": {
    "url": "https://www.bilibili.com/video/BV1x341177NN"
  }
}
```

### 5. `login_bilibili`
Launches the local browser authentication page to scan a QR code or auto-detect cookies.
```json
{
  "name": "login_bilibili",
  "arguments": {
    "timeout": 300
  }
}
```

### 6. `get_login_status`
Checks if a valid Bilibili session is active and returns username and VIP status.
```json
{
  "name": "get_login_status",
  "arguments": {}
}
```

### 7. `logout_bilibili`
Logs out and deletes the stored session file.
```json
{
  "name": "logout_bilibili",
  "arguments": {}
}
```

---

## FAQ

### 1. Do I need to be logged in?
Many public videos can return danmaku, comments, and basic info without logging in. However, Bilibili frequently enforces anti-bot verification (HTTP 412) on unauthenticated requests. Logging in with `login_bilibili` prevents rate limits and gives access to full subtitles and HD streams.

### 2. Where is my login session stored?
Sessions captured via browser login are saved locally on your machine at `~/.config/bilibili-video-info-mcp/session.json`. They are strictly stored on your device and only sent directly to official Bilibili API endpoints.

### 3. What video link formats are supported?
Standard Bilibili video links are supported, such as:
- `https://www.bilibili.com/video/BV1x341177NN`
- `https://b23.tv/xxxxx` (short links)
- Any URL containing a Bilibili `BV...` identifier
