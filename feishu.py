
import json
import os
import re
import time
import requests
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

FEISHU_BASE = "https://open.feishu.cn/open-apis"

@dataclass
class SaveTarget:
    type: str           # "folder" or "wiki"
    token: str          # folder_token or space_id
    node_token: str     # wiki node token
    display_name: str

@dataclass
class SaveResult:
    document_url: str
    document_id: str
    title: str

# ─── 核心工具函数 ─────────────────────────────────────────────────────────────

def _headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"}

def _api_get(path: str, params: dict, user_token: str) -> dict:
    resp = requests.get(f"{FEISHU_BASE}{path}", headers=_headers(user_token), params=params, timeout=15)
    return resp.json()

def _check_response(resp: dict, action: str):
    if resp.get("code", -1) != 0:
        raise RuntimeError(f"{action} 失败：{resp.get('msg')} (code={resp.get('code')})")

def _get_root_folder(user_token: str) -> str:
    """获取用户的根目录 (我的空间) folder_token"""
    resp = _api_get("/drive/explorer/v2/root_folder/meta", {}, user_token)
    _check_response(resp, "获取云空间根目录")
    return resp["data"]["token"]

# ─── 终极导入方案 ───────────────────────────────────────────────────────────

def create_document(
    title: str,
    markdown_text: str,
    image_url_map: dict[str, str], # no longer strictly needed but kept for compatibility signature
    target: SaveTarget,
    user_token: str,
    image_urls: list[str] | None = None,
    image_data: dict[str, str] | None = None,
) -> SaveResult:
    """
    使用飞书原生 import_tasks 接口将 Markdown 导入为高保真 Docx
    """
    # 1. 确定工作目录
    if target.type == "folder":
        folder_token = target.token
    elif target.type == "wiki":
        folder_token = _get_root_folder(user_token)
    else:
        raise ValueError(f"不支持的类型：{target.type}")

    # 2. 上传所有图片为 Drive Explorer 文件并获取 Token
    if image_urls:
        total = len(image_urls)
        print(json.dumps({"status": "uploading_images", "message": f"正在上传 {total} 张图片至图床..."}), flush=True)
        import base64 as _base64
        
        for idx, img_url in enumerate(image_urls, 1):
            b64 = (image_data or {}).get(img_url, "")
            try:
                if b64:
                    img_bytes = _base64.b64decode(b64)
                    if img_bytes[:4] == b'\x89PNG': ext, mime = ".png", "image/png"
                    elif img_bytes[:6] in (b'GIF87a', b'GIF89a'): ext, mime = ".gif", "image/gif"
                    elif b'WEBP' in img_bytes[:16]: ext, mime = ".webp", "image/webp"
                    else: ext, mime = ".jpg", "image/jpeg"
                else:
                    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://mp.weixin.qq.com/"}
                    resp = requests.get(img_url, headers=headers, timeout=15)
                    if resp.status_code != 200: continue
                    img_bytes = resp.content
                    mime = resp.headers.get("content-type", "image/jpeg")
                    ext = ".jpg" if "jpeg" in mime else ".png"

                files = {"file": (f"img_{idx}{ext}", img_bytes, mime)}
                data = {
                    "file_name": f"img_{idx}{ext}",
                    "parent_type": "explorer",
                    "parent_node": folder_token,
                    "size": str(len(img_bytes))
                }
                
                up_resp = requests.post(
                    f"{FEISHU_BASE}/drive/v1/files/upload_all", 
                    headers={"Authorization": f"Bearer {user_token}"}, 
                    data=data, 
                    files=files, 
                    timeout=30
                ).json()
                
                if up_resp.get("code") == 0:
                    file_token = up_resp["data"]["file_token"]
                    # 替换 Markdown 中的图片 URL 为飞书 token
                    # 使用正则匹配基础 URL，因为 processor.py 可能修改了查询参数
                    base_url = img_url.split("?")[0]
                    markdown_text = re.sub(re.escape(base_url) + r"[^\s\)]*", file_token, markdown_text)

            except Exception as e:
                print(f"  ❌ 图片 {idx} 上传失败: {e}")
                
            print(json.dumps({"status": "image_progress", "current": idx, "total": total}), flush=True)

    # 3. 将 Markdown 文本上传为 .md 文件
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    md_filename = f"{safe_title}.md"
    md_bytes = markdown_text.encode('utf-8')
    
    files_md = {"file": (md_filename, md_bytes, "text/markdown")}
    data_md = {
        "file_name": md_filename, 
        "parent_type": "explorer", 
        "parent_node": folder_token, 
        "size": str(len(md_bytes))
    }
    
    md_resp = requests.post(
        f"{FEISHU_BASE}/drive/v1/files/upload_all", 
        headers={"Authorization": f"Bearer {user_token}"}, 
        data=data_md, 
        files=files_md,
        timeout=30
    ).json()
    _check_response(md_resp, "上传 Markdown 文件")
    md_token = md_resp["data"]["file_token"]

    # 4. 创建导入任务将 .md 转换为 docx
    import_payload = {
        "file_extension": "md",
        "file_token": md_token,
        "type": "docx",
        "point": {
            "mount_type": 1,
            "mount_key": folder_token
        }
    }
    task_resp = requests.post(
        f"{FEISHU_BASE}/drive/v1/import_tasks", 
        headers=_headers(user_token), 
        json=import_payload
    ).json()
    _check_response(task_resp, "创建文档转换任务")
    ticket = task_resp["data"]["ticket"]

    # 5. 轮询等待转换完成
    doc_token = ""
    doc_url = ""
    for _ in range(30): # 最大等待60秒
        time.sleep(2)
        res = requests.get(f"{FEISHU_BASE}/drive/v1/import_tasks/{ticket}", headers=_headers(user_token)).json()
        status = res.get("data", {}).get("result", {}).get("job_status")
        if status == 0:
            doc_token = res["data"]["result"]["token"]
            doc_url = res["data"]["result"]["url"]
            break
        elif status in (3, 4, 10, 11):
            raise RuntimeError(f"文档转换失败: {res.get('data', {}).get('result', {}).get('job_error_msg')}")

    if not doc_token:
        raise RuntimeError("等待文档转换超时，请稍后在飞书云空间查看。")

    # 6. 如果目标是知识库，将生成的文档挂载为知识库节点
    if target.type == "wiki":
        space_id = target.token if target.token.isdigit() else ""
        parent_node_token = target.node_token or target.token
        
        if not space_id:
            node_resp = _api_get(f"/wiki/v2/spaces/get_node", {"token": parent_node_token, "obj_type": "wiki"}, user_token)
            space_id = node_resp.get("data", {}).get("node", {}).get("space_id", "")
            
        wiki_payload = {
            "obj_type": "docx",
            "obj_token": doc_token,
            "node_type": "origin", 
            "parent_node_token": parent_node_token,
            "title": title
        }
        wiki_resp = requests.post(
            f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes", 
            headers=_headers(user_token), 
            json=wiki_payload,
            timeout=15
        ).json()
        _check_response(wiki_resp, "挂载到知识库")
        
        node = wiki_resp["data"]["node"]
        doc_url = node.get("obj_edit_url") or f"https://feishu.cn/wiki/{node['node_token']}"
        doc_token = node.get("obj_token", doc_token)

    return SaveResult(document_url=doc_url, document_id=doc_token, title=title)

# ─── 列表查询接口 ─────────────────────────────────────────────────────────────

def list_folders(user_token: str, parent_token: str = "") -> list[dict]:
    params = {"page_size": 50}
    if parent_token: params["folder_token"] = parent_token
    resp = _api_get("/drive/v1/files", params, user_token)
    files = resp.get("data", {}).get("files", [])
    return [{"name": i["name"], "token": i["token"], "type": i["type"]} for i in files if i["type"] == "folder"]

def list_wikis(user_token: str) -> list[dict]:
    resp = _api_get("/wiki/v2/spaces", {"page_size": 50}, user_token)
    return [{"name": i["name"], "space_id": i["space_id"]} for i in resp.get("data", {}).get("items", [])]

def list_wiki_nodes(space_id: str, parent_node_token: str, user_token: str) -> list[dict]:
    params = {"page_size": 50, "parent_node_token": parent_node_token}
    resp = _api_get(f"/wiki/v2/spaces/{space_id}/nodes", params, user_token)
    items = resp.get("data", {}).get("items", [])
    return [{"title": i.get("title", ""), "node_token": i["node_token"], "has_child": i.get("has_child", False)} 
            for i in items if i.get("obj_type") in ("doc", "docx", "folder", "wiki")]
