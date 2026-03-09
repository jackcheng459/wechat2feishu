
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

def _headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"}

def _api_get(path: str, params: dict, user_token: str) -> dict:
    resp = requests.get(f"{FEISHU_BASE}{path}", headers=_headers(user_token), params=params, timeout=15)
    return resp.json()

def _check_response(resp: dict, action: str):
    if resp.get("code", -1) != 0:
        raise RuntimeError(f"{action} 失败：{resp.get('msg')} (code={resp.get('code')})")

def _get_root_folder(user_token: str) -> str:
    resp = _api_get("/drive/explorer/v2/root_folder/meta", {}, user_token)
    _check_response(resp, "获取云空间根目录")
    return resp["data"]["token"]

def create_document(
    title: str,
    markdown_text: str,
    image_url_map: dict[str, str],
    target: SaveTarget,
    user_token: str,
    image_urls: list[str] | None = None,
    image_data: dict[str, str] | None = None,
) -> SaveResult:
    """
    两步走：先 import_tasks，然后 PATCH blocks
    """
    if target.type == "folder":
        folder_token = target.token
    elif target.type == "wiki":
        folder_token = _get_root_folder(user_token)
    else:
        raise ValueError(f"不支持的类型：{target.type}")

    # 1. 获取临时 token 以生成 MD
    if image_urls:
        total = len(image_urls)
        
        # 为了能够在 import_tasks 后找到对应的图片块，我们使用一个唯一的标记作为 placeholder
        for idx, img_url in enumerate(image_urls, 1):
            base_img_url = img_url.split("?")[0]
            
            # 创建一个 1x1 的透明/极小图片作为占位符
            import base64
            placeholder_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            placeholder_bytes = base64.b64decode(placeholder_b64)
            
            files = {"file": (f"placeholder_{idx}.png", placeholder_bytes, "image/png")}
            data = {
                "file_name": f"placeholder_{idx}.png",
                "parent_type": "explorer",
                "parent_node": folder_token,
                "size": str(len(placeholder_bytes))
            }
            
            up_resp = requests.post(f"{FEISHU_BASE}/drive/v1/files/upload_all", headers={"Authorization": f"Bearer {user_token}"}, data=data, files=files, timeout=30).json()
            
            if up_resp.get("code") == 0:
                file_token = up_resp["data"]["file_token"]
                image_url_map[img_url] = file_token
                markdown_text = re.sub(re.escape(base_img_url) + r"[^\s\)]*", file_token, markdown_text)

    # 2. 上传 MD 文件

    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    md_filename = f"{safe_title}.md"
    md_bytes = markdown_text.encode('utf-8')
    
    files_md = {"file": (md_filename, md_bytes, "text/markdown")}
    data_md = {"file_name": md_filename, "parent_type": "explorer", "parent_node": folder_token, "size": str(len(md_bytes))}
    md_resp = requests.post(f"{FEISHU_BASE}/drive/v1/files/upload_all", headers={"Authorization": f"Bearer {user_token}"}, data=data_md, files=files_md, timeout=30).json()
    _check_response(md_resp, "上传 Markdown 文件")
    md_token = md_resp["data"]["file_token"]

    # 3. 创建导入任务
    import_payload = {"file_extension": "md", "file_token": md_token, "type": "docx", "point": {"mount_type": 1, "mount_key": folder_token}}
    task_resp = requests.post(f"{FEISHU_BASE}/drive/v1/import_tasks", headers=_headers(user_token), json=import_payload).json()
    _check_response(task_resp, "创建文档转换任务")
    ticket = task_resp["data"]["ticket"]

    # 4. 轮询
    doc_token = ""
    doc_url = ""
    for _ in range(30):
        time.sleep(2)
        res = requests.get(f"{FEISHU_BASE}/drive/v1/import_tasks/{ticket}", headers=_headers(user_token)).json()
        status = res.get("data", {}).get("result", {}).get("job_status")
        if status == 0:
            doc_token = res["data"]["result"]["token"]
            doc_url = res["data"]["result"]["url"]
            break
        elif status in (3, 4, 10, 11):
            raise RuntimeError(f"文档转换失败: {res.get('data', {}).get('result', {}).get('job_error_msg')}")

    if not doc_token: raise RuntimeError("等待文档转换超时。")

    # 5. 修补图片 (Image Patching for high fidelity)
    if image_urls:
        print(json.dumps({"status": "uploading_images", "message": "正在将高保真图片注入文档..."}), flush=True)
        blocks_resp = requests.get(f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks?page_size=500", headers=_headers(user_token)).json()
        blocks = blocks_resp.get("data", {}).get("items", [])
        
        # 提取所有的图片块
        image_blocks = [b for b in blocks if b["block_type"] == 27]
        
        # 按顺序一一对应进行修补 (假设顺序完全一致)
        patched_count = 0
        for i in range(min(len(image_blocks), len(image_urls))):
            block = image_blocks[i]
            img_url = image_urls[i]
            block_id = block["block_id"]
            
            base_img_url = img_url.split("?")[0]
            b64 = ""
            for loaded_url, data in (image_data or {}).items():
                if loaded_url.split("?")[0] == base_img_url:
                    b64 = data
                    break
            
            try:
                if b64:
                    import base64 as _base64
                    img_bytes = _base64.b64decode(b64)
                    if img_bytes[:4] == b'\x89PNG': ext, mime = ".png", "image/png"
                    elif img_bytes[:6] in (b'GIF87a', b'GIF89a'): ext, mime = ".gif", "image/gif"
                    elif b'WEBP' in img_bytes[:16]: ext, mime = ".webp", "image/webp"
                    else: ext, mime = ".jpg", "image/jpeg"
                else:
                    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://mp.weixin.qq.com/"}
                    resp = requests.get(img_url, headers=headers, timeout=15)
                    if resp.status_code != 200 or not resp.content: continue
                    img_bytes = resp.content
                    mime = resp.headers.get("content-type", "image/jpeg")
                    ext = ".jpg" if "jpeg" in mime else ".png"

                if not img_bytes or len(img_bytes) < 100: continue

                files = {"file": (f"img_{block_id}{ext}", img_bytes, mime)}
                data = {
                    "file_name": f"img_{block_id}{ext}",
                    "parent_type": "docx_image",
                    "parent_node": block_id,
                    "size": str(len(img_bytes)),
                    "extra": json.dumps({"drive_route_token": doc_token})
                }
                up_resp = requests.post(f"{FEISHU_BASE}/drive/v1/medias/upload_all", headers={"Authorization": f"Bearer {user_token}"}, data=data, files=files, timeout=30).json()

                if up_resp.get("code") == 0:
                    new_token = up_resp["data"]["file_token"]
                    
                    # 使用 Pillow 获取图片真实宽高以防变形
                    img_width, img_height = 800, 600 # default
                    try:
                        from PIL import Image
                        import io
                        with Image.open(io.BytesIO(img_bytes)) as img:
                            img_width, img_height = img.size
                    except Exception as pil_err:
                        pass

                    requests.patch(
                        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{block_id}", 
                        headers=_headers(user_token), 
                        json={
                            "replace_image": {
                                "token": new_token,
                                "width": img_width,
                                "height": img_height
                            }
                        }, 
                        timeout=15
                    )
                    patched_count += 1
                    print(json.dumps({"status": "image_progress", "current": patched_count, "total": len(image_urls)}), flush=True)

            except Exception as e:
                pass



    # 6. 挂载至 Wiki
    if target.type == "wiki":
        space_id = target.token if target.token.isdigit() else ""
        parent_node_token = target.node_token or target.token
        
        if not space_id:
            node_resp = _api_get(f"/wiki/v2/spaces/get_node", {"token": parent_node_token, "obj_type": "wiki"}, user_token)
            space_id = node_resp.get("data", {}).get("node", {}).get("space_id", "")
            
        wiki_payload = {"obj_type": "docx", "obj_token": doc_token, "node_type": "origin", "parent_node_token": parent_node_token, "title": title}
        wiki_resp = requests.post(f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes", headers=_headers(user_token), json=wiki_payload, timeout=15).json()
        _check_response(wiki_resp, "挂载到知识库")
        
        node = wiki_resp["data"]["node"]
        doc_url = node.get("obj_edit_url") or f"https://feishu.cn/wiki/{node['node_token']}"

    return SaveResult(document_url=doc_url, document_id=doc_token, title=title)

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
    return [{"title": i.get("title", ""), "node_token": i["node_token"], "has_child": i.get("has_child", False)} for i in items if i.get("obj_type") in ("doc", "docx", "folder", "wiki")]
