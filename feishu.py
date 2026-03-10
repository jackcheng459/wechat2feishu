
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
class SaveResult:
    """增强版保存结果，包含更多调试信息"""
    document_url: str       # 最终可访问的 URL
    document_id: str        # 原始 Docx Token
    title: str
    wiki_token: str = ""    # Wiki 节点 Token
    raw_doc_url: str = ""   # 原始 Docx URL (兜底用)

@dataclass
class SaveTarget:
    type: str           # "folder" or "wiki"
    token: str          # folder_token or space_id
    node_token: str     # wiki node token
    display_name: str

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

def is_valid_feishu_url(url: str) -> bool:
    """校验生成的链接是否完整，防止返回 https://feishu.cn/wiki/ 这种残链"""
    if not url: return False
    # 如果链接以 /wiki/ 或 /docx/ 结尾，说明没有带上真正的 token
    if url.rstrip("/").endswith(("/wiki", "/docx")):
        return False
    # 检查链接中是否包含疑似 token 的长字符
    parts = url.rstrip("/").split("/")
    return len(parts[-1]) > 10

def build_feishu_access_url(doc_token: str, wiki_token: str = "", explicit_url: str = "") -> str:
    """构建最稳健的可访问链接，具备多级降级逻辑"""
    # 1. 如果接口返回了显式且有效的 URL，优先使用
    if explicit_url and is_valid_feishu_url(explicit_url):
        return explicit_url
    
    # 2. 优先构建 Wiki 链接
    if wiki_token:
        url = f"https://feishu.cn/wiki/{wiki_token}"
        if is_valid_feishu_url(url): return url
        
    # 3. 兜底构建 Docx 链接
    return f"https://feishu.cn/docx/{doc_token}"

def _grant_management_permission(doc_token: str, user_token: str):
    """将文档的管理权限赋予管理员用户 (ou_xxxx)"""
    admin_id = os.getenv("ADMIN_USER_ID", "")
    if not admin_id:
        return
    
    # 飞书 API：增加协作者权限
    payload = {
        "member_type": "openid",
        "member_id": admin_id,
        "perm": "full_access" # 管理权限
    }
    
    try:
        # 先尝试对底层的 Docx 赋权
        requests.post(
            f"{FEISHU_BASE}/drive/v1/permissions/{doc_token}/members",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"type": "docx"},
            json=payload,
            timeout=10
        )
        print(f"✅ 已尝试将管理权限赋予用户 {admin_id}", flush=True)
    except Exception as e:
        print(f"⚠️ 赋权异常: {e}", flush=True)




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
    两步走转存：原生导入 + 高保真 Patch
    """
    root_token = _get_root_folder(user_token)

    # 1. 上传占位图（略过，逻辑保持不变...）
    if image_urls:
        import base64 as _base64
        for idx, img_url in enumerate(image_urls, 1):
            base_img_url = img_url.split("?")[0]
            placeholder_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            placeholder_bytes = _base64.b64decode(placeholder_b64)
            files = {"file": (f"tmp_{idx}.png", placeholder_bytes, "image/png")}
            data = {"file_name": f"tmp_{idx}.png", "parent_type": "explorer", "parent_node": root_token, "size": str(len(placeholder_bytes))}
            up_resp = requests.post(f"{FEISHU_BASE}/drive/v1/files/upload_all", headers={"Authorization": f"Bearer {user_token}"}, data=data, files=files, timeout=30).json()
            if up_resp.get("code") == 0:
                file_token = up_resp["data"]["file_token"]
                image_url_map[img_url] = file_token
                markdown_text = re.sub(re.escape(base_img_url) + r"[^\s\)]*", file_token, markdown_text)

    # 2. 上传 MD 并执行导入
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)
    md_bytes = markdown_text.encode('utf-8')
    md_resp = requests.post(f"{FEISHU_BASE}/drive/v1/files/upload_all", headers={"Authorization": f"Bearer {user_token}"}, 
                            data={"file_name": f"{safe_name}.md", "parent_type": "explorer", "parent_node": root_token, "size": str(len(md_bytes))},
                            files={"file": (f"{safe_name}.md", md_bytes, "text/markdown")}, timeout=30).json()
    _check_response(md_resp, "上传临时文本")
    md_token = md_resp["data"]["file_token"]

    mount_key = target.token if target.type == "folder" else root_token
    import_payload = {"file_extension": "md", "file_token": md_token, "type": "docx", "title": title, "point": {"mount_type": 1, "mount_key": mount_key}}
    task_resp = requests.post(f"{FEISHU_BASE}/drive/v1/import_tasks", headers=_headers(user_token), json=import_payload).json()
    _check_response(task_resp, "创建转换任务")
    ticket = task_resp["data"]["ticket"]

    # 3. 轮询导入结果
    doc_token, doc_url = "", ""
    for _ in range(30):
        time.sleep(2)
        res = requests.get(f"{FEISHU_BASE}/drive/v1/import_tasks/{ticket}", headers=_headers(user_token)).json()
        if res.get("data", {}).get("result", {}).get("job_status") == 0:
            doc_token = res["data"]["result"]["token"]
            doc_url = res["data"]["result"]["url"]
            break
    if not doc_token: raise RuntimeError("导入超时")

    # 4. 重点：Wiki 挂载与容错 Token 提取
    wiki_token = ""
    final_access_url = doc_url
    if target.type == "wiki":
        time.sleep(2)
        space_id = target.token if target.token.isdigit() else ""
        parent_node_token = target.node_token
        
        # 核心逻辑：如果没传子节点，尝试获取知识库的根节点
        if not parent_node_token:
            # 尝试 1：获取空间节点列表
            root_nodes = _api_get(f"/wiki/v2/spaces/{space_id}/nodes", {"page_size": 50}, user_token)
            nodes = root_nodes.get("data", {}).get("items", [])
            
            # 过滤出可以作为父节点的类型 (wiki, folder, docx 等)
            valid_parents = [n for n in nodes if n.get("obj_type") in ("wiki", "folder", "docx")]
            if valid_parents:
                parent_node_token = valid_parents[0].get("node_token")
            
            # 尝试 2：如果列表失败，尝试获取空间基本信息
            if not parent_node_token:
                node_resp = _api_get(f"/wiki/v2/spaces/get_node", {"token": target.token, "obj_type": "wiki"}, user_token)
                parent_node_token = node_resp.get("data", {}).get("node", {}).get("node_token", "")


        if not parent_node_token:
            pass
        else:
            wiki_payload = {"obj_type": "docx", "obj_token": doc_token, "parent_node_token": parent_node_token}
            wiki_resp = requests.post(f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki", headers=_headers(user_token), json=wiki_payload, timeout=15).json()
            
            # 容错提取 Wiki Token
            w_data = wiki_resp.get("data", {})
            wiki_token = w_data.get("wiki_token") or w_data.get("node_token") or w_data.get("node", {}).get("node_token", "")
            
            # 如果 API 没返回 wiki_token，主动查询父节点的子节点列表来找到新创建的节点
            if not wiki_token:
                time.sleep(1)  # 等待挂载完成
                children_resp = _api_get(f"/wiki/v2/spaces/{space_id}/nodes", {"page_size": 50, "parent_node_token": parent_node_token}, user_token)
                for node in children_resp.get("data", {}).get("items", []):
                    if node.get("obj_token") == doc_token:
                        wiki_token = node.get("node_token", "")
                        break
            
            final_access_url = build_feishu_access_url(doc_token, wiki_token, w_data.get("node", {}).get("obj_edit_url", ""))




    # 5. 修补图片（保持逻辑不变...）
    if image_urls:
        print(json.dumps({"status": "uploading_images", "message": "正在注入高保真图片..."}), flush=True)
        blocks_resp = requests.get(f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks?page_size=500", headers=_headers(user_token)).json()
        image_blocks = [b for b in blocks_resp.get("data", {}).get("items", []) if b["block_type"] == 27]
        patched_count = 0
        for i in range(min(len(image_blocks), len(image_urls))):
            block, img_url = image_blocks[i], image_urls[i]
            block_id = block["block_id"]
            try:
                base_img_url = img_url.split("?")[0]
                b64 = next((data for u, data in (image_data or {}).items() if u.split("?")[0] == base_img_url), "")
                import base64 as _base64
                if b64:
                    img_bytes = _base64.b64decode(b64)
                    ext, mime = (".png", "image/png") if img_bytes[:4] == b'\x89PNG' else (".jpg", "image/jpeg")
                else:
                    r = requests.get(img_url, timeout=10); img_bytes = r.content; mime = r.headers.get("content-type", "image/jpeg"); ext = ".jpg"
                img_w, img_h = 800, 600
                try:
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(img_bytes)) as im: img_w, img_h = im.size
                except: pass
                up_res = requests.post(f"{FEISHU_BASE}/drive/v1/medias/upload_all", headers={"Authorization": f"Bearer {user_token}"}, 
                                       data={"file_name": f"i_{block_id}{ext}", "parent_type": "docx_image", "parent_node": block_id, "size": str(len(img_bytes)), "extra": json.dumps({"drive_route_token": doc_token})},
                                       files={"file": (f"i{ext}", img_bytes, mime)}, timeout=30).json()
                if up_res.get("code") == 0:
                    requests.patch(f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{block_id}", headers=_headers(user_token), json={"replace_image": {"token": up_res["data"]["file_token"], "width": img_w, "height": img_h}}, timeout=15)
                    patched_count += 1
                    print(json.dumps({"status": "image_progress", "current": patched_count, "total": len(image_urls)}), flush=True)
            except: pass

    # 6. 最后一步：赋予管理权 (如果是 Tenant 模式创建，此步至关重要)
    _grant_management_permission(doc_token, user_token)



    return SaveResult(

        document_url=final_access_url, 
        document_id=doc_token, 
        title=title, 
        wiki_token=wiki_token, 
        raw_doc_url=f"https://feishu.cn/docx/{doc_token}"
    )

def list_folders(user_token: str, parent_token: str = "") -> list[dict]:
    resp = _api_get("/drive/v1/files", {"page_size": 50, "folder_token": parent_token} if parent_token else {"page_size": 50}, user_token)
    return [{"name": i["name"], "token": i["token"], "type": i["type"]} for i in resp.get("data", {}).get("files", []) if i["type"] == "folder"]

def list_wikis(user_token: str) -> list[dict]:
    resp = _api_get("/wiki/v2/spaces", {"page_size": 50}, user_token)
    return [{"name": i["name"], "space_id": i["space_id"]} for i in resp.get("data", {}).get("items", [])]

def list_wiki_nodes(space_id: str, parent_node_token: str, user_token: str) -> list[dict]:
    resp = _api_get(f"/wiki/v2/spaces/{space_id}/nodes", {"page_size": 50, "parent_node_token": parent_node_token}, user_token)
    return [{"title": i.get("title", ""), "node_token": i["node_token"], "has_child": i.get("has_child", False)} for i in resp.get("data", {}).get("items", []) if i.get("obj_type") in ("doc", "docx", "folder", "wiki")]
