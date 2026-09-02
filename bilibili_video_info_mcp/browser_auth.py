"""Browser-based authentication and cookie capture for Bilibili Video Info MCP."""

from __future__ import annotations

import asyncio
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import bilibili_api

HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bilibili MCP Authentication</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #00aeec;
      --accent-hover: #009cd3;
      --border: #334155;
      --success: #10b981;
      --warning: #f59e0b;
      --error: #ef4444;
    }
    @media (prefers-color-scheme: light) {
      :root {
        --bg: #f8fafc;
        --card-bg: #ffffff;
        --text: #0f172a;
        --text-muted: #64748b;
        --accent: #00aeec;
        --accent-hover: #009cd3;
        --border: #e2e8f0;
        --success: #10b981;
        --warning: #f59e0b;
        --error: #ef4444;
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      max-width: 480px;
      width: 100%;
      padding: 2rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    }
    .header {
      text-align: center;
      margin-bottom: 1.5rem;
    }
    .logo {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      font-size: 20px;
      margin-bottom: 0.75rem;
    }
    h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 0.35rem; }
    p.sub { font-size: 0.9rem; color: var(--text-muted); line-height: 1.4; }
    
    .tabs {
      display: flex;
      border-bottom: 1px solid var(--border);
      margin-bottom: 1.5rem;
      gap: 0.5rem;
    }
    .tab {
      padding: 0.6rem 0.8rem;
      font-size: 0.88rem;
      color: var(--text-muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .tab.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      font-weight: 600;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    .qr-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 1rem;
    }
    .qr-box {
      width: 220px;
      height: 220px;
      background: white;
      padding: 10px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--border);
      position: relative;
    }
    .qr-box img {
      width: 200px;
      height: 200px;
      display: block;
      border-radius: 4px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.84rem;
      font-weight: 500;
    }
    .badge-waiting { background: rgba(0, 174, 236, 0.15); color: var(--accent); }
    .badge-scanned { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
    .badge-success { background: rgba(16, 185, 129, 0.15); color: var(--success); }
    .badge-error { background: rgba(239, 68, 68, 0.15); color: var(--error); }
    
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      padding: 0.7rem 1rem;
      border-radius: 8px;
      font-size: 0.92rem;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
      border: none;
      text-decoration: none;
    }
    .btn:active { transform: scale(0.98); }
    .btn-primary {
      background: var(--accent);
      color: white;
    }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-secondary {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
      margin-top: 0.5rem;
    }
    .btn-secondary:hover { background: rgba(128, 128, 128, 0.1); }
    
    textarea, input[type="text"] {
      width: 100%;
      padding: 0.75rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      font-family: ui-monospace, SFMono-Regular, monospace;
      font-size: 0.85rem;
      margin-bottom: 0.75rem;
      box-sizing: border-box;
    }
    textarea { min-height: 80px; resize: vertical; }
    textarea:focus, input:focus { outline: 2px solid var(--accent); }
    
    .msg-box {
      margin-top: 0.75rem;
      padding: 0.65rem 0.9rem;
      border-radius: 8px;
      font-size: 0.85rem;
      line-height: 1.4;
      display: none;
    }
    .msg-box.err { display: block; background: rgba(239, 68, 68, 0.15); color: var(--error); }
    .msg-box.ok { display: block; background: rgba(16, 185, 129, 0.15); color: var(--success); }
    
    .done-screen {
      display: none;
      text-align: center;
      padding: 1.5rem 0;
    }
    .done-icon {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      font-size: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1rem;
    }
    .user-info {
      margin: 1rem 0;
      padding: 0.75rem;
      border-radius: 8px;
      background: rgba(128, 128, 128, 0.08);
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <div class="card">
    <div id="auth-container">
      <div class="header">
        <div class="logo">B</div>
        <h1>Connect Bilibili</h1>
        <p class="sub">Authenticate your Bilibili account to extract your session securely.</p>
      </div>

      <div class="tabs">
        <div class="tab active" onclick="switchTab('qr')">QR Code Login</div>
        <div class="tab" onclick="switchTab('detect')">Auto-Detect</div>
        <div class="tab" onclick="switchTab('manual')">Manual Input</div>
      </div>

      <!-- Tab 1: QR Code -->
      <div id="tab-qr" class="tab-content active">
        <div class="qr-container">
          <div class="qr-box">
            <img id="qr-img" src="" alt="Bilibili QR Code" />
          </div>
          <div id="qr-status" class="badge badge-waiting">Generating QR code...</div>
          <p class="sub" style="font-size: 0.82rem;">Scan with the Bilibili Mobile App</p>
          <button type="button" class="btn btn-secondary" onclick="loadQRCode()" style="width: auto; padding: 0.4rem 0.8rem; font-size: 0.82rem;">
            Refresh QR Code
          </button>
        </div>
      </div>

      <!-- Tab 2: Auto-Detect -->
      <div id="tab-detect" class="tab-content">
        <p class="sub" style="margin-bottom: 1rem;">
          Automatically scan your local browser cookies (Chrome, Safari, Edge, Firefox, Brave, Arc) for an active bilibili.com login session.
        </p>
        <button type="button" class="btn btn-primary" id="btn-detect" onclick="detectBrowserSession()">
          Detect Session from Browsers
        </button>
        <div id="detect-msg" class="msg-box"></div>
      </div>

      <!-- Tab 3: Manual Input -->
      <div id="tab-manual" class="tab-content">
        <p class="sub" style="margin-bottom: 0.75rem;">
          Paste your <code>SESSDATA</code> value or your full Bilibili <code>Cookie:</code> header:
        </p>
        <textarea id="cookie-input" placeholder="SESSDATA=xxxxx; bili_jct=xxxxx... or just the SESSDATA value"></textarea>
        <button type="button" class="btn btn-primary" id="btn-submit" onclick="submitManualCookie()">
          Save & Connect
        </button>
        <a class="btn btn-secondary" href="https://www.bilibili.com" target="_blank" rel="noopener">
          Open Bilibili in Browser &rarr;
        </a>
        <div id="manual-msg" class="msg-box"></div>
      </div>
    </div>

    <!-- Done Screen -->
    <div id="done-screen" class="done-screen">
      <div class="done-icon">&#10003;</div>
      <h2>Connected Successfully!</h2>
      <div class="user-info" id="user-info-display">Logged in</div>
      <p class="sub" style="margin-bottom: 1.5rem;">
        Your Bilibili session cookies have been captured and saved. You can close this tab and return to your AI assistant.
      </p>
      <button class="btn btn-secondary" onclick="window.close()">Close Window</button>
    </div>
  </div>

  <script>
    const token = "__TOKEN__";
    let currentQRKey = "";
    let pollInterval = null;

    function switchTab(name) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      const tabIdx = name === 'qr' ? 0 : name === 'detect' ? 1 : 2;
      document.querySelectorAll('.tab')[tabIdx].classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
      
      if (name === 'qr' && !currentQRKey) {
        loadQRCode();
      }
    }

    async function loadQRCode() {
      if (pollInterval) clearInterval(pollInterval);
      const statusEl = document.getElementById('qr-status');
      const imgEl = document.getElementById('qr-img');
      statusEl.className = 'badge badge-waiting';
      statusEl.textContent = 'Generating QR code...';
      
      try {
        const res = await fetch(`/auth/${token}/qr`);
        const data = await res.json();
        if (data.success && data.url) {
          currentQRKey = data.qrcode_key;
          imgEl.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=0&data=${encodeURIComponent(data.url)}`;
          statusEl.textContent = 'Waiting for scan...';
          startPolling(currentQRKey);
        } else {
          statusEl.className = 'badge badge-error';
          statusEl.textContent = data.error || 'Failed to load QR code';
        }
      } catch (err) {
        statusEl.className = 'badge badge-error';
        statusEl.textContent = 'Network error loading QR code';
      }
    }

    function startPolling(key) {
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`/auth/${token}/poll?key=${key}`);
          const data = await res.json();
          const statusEl = document.getElementById('qr-status');

          if (data.status === 'scanned') {
            statusEl.className = 'badge badge-scanned';
            statusEl.textContent = 'Scanned! Please confirm on app.';
          } else if (data.status === 'expired') {
            statusEl.className = 'badge badge-error';
            statusEl.textContent = 'QR code expired. Click refresh.';
            clearInterval(pollInterval);
          } else if (data.status === 'success') {
            clearInterval(pollInterval);
            statusEl.className = 'badge badge-success';
            statusEl.textContent = 'Login confirmed!';
            showSuccess(data.user);
          }
        } catch (e) {
          console.error('Polling error', e);
        }
      }, 1500);
    }

    async function detectBrowserSession() {
      const msgEl = document.getElementById('detect-msg');
      const btnEl = document.getElementById('btn-detect');
      btnEl.disabled = true;
      btnEl.textContent = 'Scanning browsers...';
      msgEl.className = 'msg-box';
      msgEl.style.display = 'none';

      try {
        const res = await fetch(`/auth/${token}/detect`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showSuccess(data.user);
        } else {
          msgEl.className = 'msg-box err';
          msgEl.textContent = data.message || 'No Bilibili session found in local browsers. Try QR code login instead.';
        }
      } catch (err) {
        msgEl.className = 'msg-box err';
        msgEl.textContent = 'Error scanning browser cookies: ' + err.message;
      } finally {
        btnEl.disabled = false;
        btnEl.textContent = 'Detect Session from Browsers';
      }
    }

    async function submitManualCookie() {
      const input = document.getElementById('cookie-input').value.trim();
      const msgEl = document.getElementById('manual-msg');
      const btnEl = document.getElementById('btn-submit');
      if (!input) {
        msgEl.className = 'msg-box err';
        msgEl.textContent = 'Please enter your SESSDATA or Cookie header.';
        return;
      }
      btnEl.disabled = true;
      btnEl.textContent = 'Verifying...';

      try {
        const res = await fetch(`/auth/${token}/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cookies: input })
        });
        const data = await res.json();
        if (data.success) {
          showSuccess(data.user);
        } else {
          msgEl.className = 'msg-box err';
          msgEl.textContent = data.message || 'Verification failed. Please check the SESSDATA value.';
        }
      } catch (err) {
        msgEl.className = 'msg-box err';
        msgEl.textContent = 'Error submitting cookie: ' + err.message;
      } finally {
        btnEl.disabled = false;
        btnEl.textContent = 'Save & Connect';
      }
    }

    function showSuccess(user) {
      if (pollInterval) clearInterval(pollInterval);
      document.getElementById('auth-container').style.display = 'none';
      document.getElementById('done-screen').style.display = 'block';
      if (user && user.uname) {
        document.getElementById('user-info-display').innerHTML = 
          `Logged in as <strong>${escapeHtml(user.uname)}</strong> (UID: ${user.mid || 'N/A'}) &bull; Status: ${user.vip_status || 'Normal'}`;
      }
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    // Initialize QR Code on page load
    loadQRCode();
  </script>
</body>
</html>
"""


class _AuthHandler(BaseHTTPRequestHandler):
    """Internal HTTP handler for loopback authentication requests."""

    server: _AuthServer

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _is_authorized(self, path_parts: list[str]) -> bool:
        if len(path_parts) < 2 or path_parts[0] != "auth":
            return False
        return secrets.compare_digest(path_parts[1], self.server.token)

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html_str: str) -> None:
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        if not self._is_authorized(parts):
            self.send_error(404, "Not Found")
            return

        # /auth/{token} -> HTML page
        if len(parts) == 2:
            html = HTML_PAGE.replace("__TOKEN__", self.server.token)
            self._send_html(200, html)
            return

        action = parts[2] if len(parts) > 2 else ""

        # /auth/{token}/qr -> Get fresh QR code
        if action == "qr":
            qr_res = bilibili_api.get_qrcode()
            self._send_json(200, qr_res)
            return

        # /auth/{token}/poll?key=... -> Poll QR code
        if action == "poll":
            params = parse_qs(parsed.query)
            key = params.get("key", [""])[0]
            if not key:
                self._send_json(400, {"status": "error", "message": "Missing key parameter"})
                return

            poll_res = bilibili_api.poll_qrcode(key)
            if poll_res.get("status") == "success":
                sessdata = poll_res.get("sessdata", "")
                bili_jct = poll_res.get("bili_jct", "")
                dede_user_id = poll_res.get("dede_user_id", "")

                # Check user info with new session
                bilibili_api.set_in_memory_session(sessdata, bili_jct, dede_user_id)
                user_info = bilibili_api.check_login_status()
                bilibili_api.save_session(sessdata, bili_jct, dede_user_id, user_info=user_info)

                self.server.complete(sessdata, "qr_code", user_info)
                poll_res["user"] = user_info

            self._send_json(200, poll_res)
            return

        # /auth/{token}/status -> Current status
        if action == "status":
            self._send_json(200, {
                "completed": self.server.is_completed(),
                "method": self.server.capture_method,
            })
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        if not self._is_authorized(parts):
            self.send_error(404, "Not Found")
            return

        action = parts[2] if len(parts) > 2 else ""

        # /auth/{token}/detect -> Auto-detect from local browsers
        if action == "detect":
            cookies = bilibili_api.extract_cookies_from_browsers()
            if cookies and cookies.get("SESSDATA"):
                sessdata = cookies["SESSDATA"]
                bili_jct = cookies.get("bili_jct", "")
                dede_user_id = cookies.get("DedeUserID", "")

                bilibili_api.set_in_memory_session(sessdata, bili_jct, dede_user_id)
                user_info = bilibili_api.check_login_status()

                if user_info.get("is_logged_in"):
                    bilibili_api.save_session(sessdata, bili_jct, dede_user_id, user_info=user_info)
                    self.server.complete(sessdata, "browser_detected", user_info)
                    self._send_json(200, {"success": True, "user": user_info})
                    return
                else:
                    self._send_json(200, {
                        "success": False,
                        "message": "Found browser cookies, but the session has expired. Please log in again.",
                    })
                    return
            else:
                self._send_json(200, {
                    "success": False,
                    "message": "No active Bilibili login session found in local browser cookie stores.",
                })
                return

        # /auth/{token}/submit -> Manual paste
        if action == "submit":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8", errors="ignore")
            try:
                data = json.loads(post_body)
                raw_input = data.get("cookies", "")
            except Exception:
                raw_input = post_body

            parsed_cookies = bilibili_api.parse_cookie_string(raw_input)
            sessdata = parsed_cookies.get("SESSDATA")
            if not sessdata:
                self._send_json(200, {
                    "success": False,
                    "message": "Could not find a valid SESSDATA token in the input.",
                })
                return

            bili_jct = parsed_cookies.get("bili_jct", "")
            dede_user_id = parsed_cookies.get("DedeUserID", "")
            bilibili_api.set_in_memory_session(sessdata, bili_jct, dede_user_id)
            user_info = bilibili_api.check_login_status()

            if user_info.get("is_logged_in"):
                bilibili_api.save_session(sessdata, bili_jct, dede_user_id, user_info=user_info)
                self.server.complete(sessdata, "manual_pasted", user_info)
                self._send_json(200, {"success": True, "user": user_info})
            else:
                self._send_json(200, {
                    "success": False,
                    "message": f"SESSDATA validation failed: {user_info.get('message', 'Invalid session')}",
                })
            return

        self.send_error(404, "Not Found")


class _AuthServer(ThreadingHTTPServer):
    """Custom ThreadingHTTPServer holding state and future."""

    def __init__(self, server_address: tuple[str, int], RequestHandlerClass: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, RequestHandlerClass)
        self.token = secrets.token_urlsafe(32)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.future: asyncio.Future[tuple[str, str, dict[str, Any]]] | None = None
        self.capture_method: str | None = None
        self._completed = False

    def complete(self, sessdata: str, method: str, user_info: dict[str, Any]) -> None:
        if self._completed:
            return
        self._completed = True
        self.capture_method = method
        if self.future and self.loop and not self.future.done():
            self.loop.call_soon_threadsafe(
                self.future.set_result,
                (sessdata, method, user_info),
            )

    def is_completed(self) -> bool:
        return self._completed


class CookieCaptureServer:
    """Ephemeral loopback server that guides user browser login and captures SESSDATA."""

    def __init__(self) -> None:
        self.server: _AuthServer | None = None
        self.thread: threading.Thread | None = None
        self.url = ""

    def start(self) -> str:
        """Start server on 127.0.0.1 with an ephemeral port."""
        self.server = _AuthServer(("127.0.0.1", 0), _AuthHandler)
        self.server.loop = asyncio.get_running_loop()
        self.server.future = self.server.loop.create_future()

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/auth/{self.server.token}"
        return self.url

    async def wait(self, timeout: float = 300) -> tuple[str, str, dict[str, Any]]:
        """Wait until authentication completes or timeout expires."""
        if not self.server or not self.server.future:
            raise RuntimeError("Capture server not started")
        return await asyncio.wait_for(self.server.future, timeout=timeout)

    def stop(self) -> None:
        """Shutdown the HTTP server and clean up resources."""
        if self.server:
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            self.server = None
        self.thread = None
