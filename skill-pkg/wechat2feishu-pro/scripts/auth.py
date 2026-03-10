"""
auth.py — 飞书 OAuth 授权模块
"""

import os
import time
import json
import webbrowser
import http.server
import threading
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

FEISHU_APP_ID     = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

REDIRECT_PORT = 9999
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}/callback"

AUTH_URL    = "https://open.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL   = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
REFRESH_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"


def get_valid_token() -> str:
    """获取有效令牌，默认使用 Tenant 模式以实现无人值守"""
    load_dotenv(ENV_PATH)
    
    # 强制优先：使用 Tenant 模式 (机器人身份)
    # 只要配置了 APP_ID 和 SECRET 即可运行，不再需要浏览器登录
    try:
        return _get_tenant_token()
    except Exception as e:
        # 如果 Tenant Token 获取失败，再尝试回退到用户 Token (保留兼容性)
        token     = os.getenv("FEISHU_USER_ACCESS_TOKEN", "")
        expire_at = float(os.getenv("FEISHU_TOKEN_EXPIRE_AT", "0"))
        if token and time.time() < expire_at - 600:
            return token
        raise RuntimeError(f"❌ 无法获取静默令牌且用户授权已失效: {e}")



def _get_tenant_token() -> str:
    """获取应用自有的 Tenant Access Token (不需用户登录)"""
    import requests
    resp = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })
    data = resp.json()
    if data.get("code") == 0:
        return data["tenant_access_token"]
    raise RuntimeError(f"获取 Tenant Token 失败: {data.get('msg')}")



def login():
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请先在 .env 文件中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return

    params = urllib.parse.urlencode({
        "client_id":     FEISHU_APP_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "docx:document drive:drive wiki:wiki",
    })
    auth_url = f"{AUTH_URL}?{params}"

    auth_code_holder = {}
    server_done      = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs     = urllib.parse.parse_qs(parsed.query)
            code   = qs.get("code", [None])[0]

            if code:
                auth_code_holder["code"] = code
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family:sans-serif;text-align:center;padding:60px">
                    <h2>&#x2705; \xe6\x8e\x88\xe6\x9d\x83\xe6\x88\x90\xe5\x8a\x9f\uff01</h2>
                    <p>\xe5\x8f\xaf\xe4\xbb\xa5\xe5\x85\xb3\xe9\x97\xad\xe6\xad\xa4\xe7\xaa\x97\xe5\x8f\xa3\xe4\xba\x86\u3002</p></body></html>
                """)
            else:
                self.send_response(400)
                self.end_headers()
            server_done.set()

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    thread = threading.Thread(target=httpd.handle_request)
    thread.daemon = True
    thread.start()

    print(f"\n🌐 正在打开飞书授权页面…")
    print(f"   如果浏览器未自动打开，请手动访问：\n   {auth_url}\n")
    webbrowser.open(auth_url)

    server_done.wait(timeout=120)

    code = auth_code_holder.get("code")
    if not code:
        print("❌ 授权超时或取消")
        return

    print("✅ 收到授权码，正在换取 Token…")
    token_data = _exchange_code(code)
    _save_token(token_data)
    print("✅ Token 已保存，授权完成！")
    print(f"   过期时间：{int(token_data['expires_in'] / 3600)} 小时后")


def _exchange_code(code: str) -> dict:
    import requests
    resp = requests.post(TOKEN_URL, json={
        "grant_type":    "authorization_code",
        "client_id":     FEISHU_APP_ID,
        "client_secret": FEISHU_APP_SECRET,
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
    })
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"换取 Token 失败：{data}")
    return data


def _refresh_token(refresh_token: str) -> dict:
    import requests
    resp = requests.post(REFRESH_URL, json={
        "grant_type":    "refresh_token",
        "client_id":     FEISHU_APP_ID,
        "client_secret": FEISHU_APP_SECRET,
        "refresh_token": refresh_token,
    })
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"刷新 Token 失败：{data}")
    return data


def _save_token(token_data: dict):
    load_dotenv(ENV_PATH)
    expire_at = str(time.time() + token_data.get("expires_in", 7200))
    set_key(str(ENV_PATH), "FEISHU_USER_ACCESS_TOKEN", token_data["access_token"])
    set_key(str(ENV_PATH), "FEISHU_REFRESH_TOKEN",token_data.get("refresh_token", ""))
    set_key(str(ENV_PATH), "FEISHU_TOKEN_EXPIRE_AT",   expire_at)
    
    # 新增：保存管理员 ID (open_id)
    if "open_id" in token_data:
        set_key(str(ENV_PATH), "ADMIN_USER_ID", token_data["open_id"])
        os.environ["ADMIN_USER_ID"] = token_data["open_id"]

    os.environ["FEISHU_USER_ACCESS_TOKEN"] = token_data["access_token"]
    os.environ["FEISHU_REFRESH_TOKEN"]     = token_data.get("refresh_token", "")
    os.environ["FEISHU_TOKEN_EXPIRE_AT"]   = expire_at



if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "login":
        login()
    elif cmd == "status":
        try:
            token = get_valid_token()
            expire_at = float(os.getenv("FEISHU_TOKEN_EXPIRE_AT", "0"))
            remaining = int((expire_at - time.time()) / 3600)
            print(f"✅ Token 有效，约 {remaining} 小时后过期")
            print(f"   Token 前缀：{token[:20]}…")
        except RuntimeError as e:
            print(str(e))
    else:
        print("用法: python auth.py [login|status]")
