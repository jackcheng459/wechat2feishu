
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

def normalize_url(url: str) -> str:
    """归一化微信图片 URL，确保抓取和转换时的 Key 匹配"""
    if not url: return ""
    # 保留关键的 wx_fmt 参数，因为它决定了文件扩展名识别
    fmt_match = re.search(r"wx_fmt=(\w+)", url)
    fmt = fmt_match.group(1) if fmt_match else "jpeg"
    base_url = url.split("?")[0]
    return f"{base_url}?wx_fmt={fmt}"

def _headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"}

def _api_get(path: str, params: dict, user_token: str) -> dict:
    resp = requests.get(f"{FEISHU_BASE}{path}", headers=_headers(user_token), params=params, timeout=15)
    return resp.json()

def _check_response(resp: dict, action: str):
    if resp.get("code", -1) != 0:
        raise RuntimeError(f"{action} 失败：{resp.get('msg')} (code={resp.get('code')})")

# ─── 图片处理逻辑 ─────────────────────────────────────────────────────────────

def upload_image(image_url: str, user_token: str, doc_id: str = "", image_b64: str = "") -> str | None:
    """上传图片至飞书，返回 file_token (docx_image 专用)"""
    import base64 as _base64
    try:
        if image_b64:
            img_bytes = _base64.b64decode(image_b64)
            # 简易文件头识别
            if img_bytes[:4] == b'\x89PNG': ext, mime = ".png", "image/png"
            elif img_bytes[:6] in (b'GIF87a', b'GIF89a'): ext, mime = ".gif", "image/gif"
            elif b'WEBP' in img_bytes[:16]: ext, mime = ".webp", "image/webp"
            else: ext, mime = ".jpg", "image/jpeg"
        else:
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://mp.weixin.qq.com/"}
            resp = requests.get(image_url, headers=headers, timeout=15)
            if resp.status_code != 200: return None
            img_bytes = resp.content
            mime = resp.headers.get("content-type", "image/jpeg")
            ext = ".jpg" if "jpeg" in mime else ".png"

        files = {"file": (f"image{ext}", img_bytes, mime)}
        data = {
            "file_name": f"img_{int(time.time())}{ext}",
            "parent_type": "docx_image",
            "parent_node": doc_id,
            "size": str(len(img_bytes))
        }
        resp = requests.post(
            f"{FEISHU_BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {user_token}"},
            data=data,
            files=files,
            timeout=30
        ).json()
        
        if resp.get("code") == 0:
            return resp["data"]["file_token"]
        return None
    except Exception:
        return None

# ─── 文档操作主接口 ───────────────────────────────────────────────────────────

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
    主入口：在飞书创建文档并写入丰富格式
    """
    if target.type == "folder":
        doc_id, doc_url = _create_in_folder(title, target.token, user_token)
    elif target.type == "wiki":
        space_id = target.token if target.token.isdigit() else ""
        node_token = target.node_token or target.token
        doc_id, doc_url = _create_in_wiki(title, space_id, node_token, user_token)
    else:
        raise ValueError(f"不支持的类型：{target.type}")

    # 归一化图片映射表
    norm_map = {normalize_url(k): v for k, v in image_url_map.items()}

    if image_urls:
        total = len(image_urls)
        print(json.dumps({"status": "uploading_images", "message": f"正在上传 {total} 张图片..."}), flush=True)
        for idx, img_url in enumerate(image_urls, 1):
            b64 = (image_data or {}).get(img_url, "")
            token = upload_image(img_url, user_token, doc_id=doc_id, image_b64=b64)
            if token:
                norm_map[normalize_url(img_url)] = token
            print(json.dumps({"status": "image_progress", "current": idx, "total": total}), flush=True)

    # 转换并分批写入
    blocks = _markdown_to_feishu_blocks(markdown_text, norm_map)
    _write_blocks(doc_id, blocks, user_token)
    
    return SaveResult(document_url=doc_url, document_id=doc_id, title=title)

# ─── 飞书 API 内部封装 ───────────────────────────────────────────────────────

def _create_in_folder(title: str, folder_token: str, user_token: str):
    resp = requests.post(f"{FEISHU_BASE}/docx/v1/documents", headers=_headers(user_token),
                         json={"title": title, "folder_token": folder_token}, timeout=15).json()
    _check_response(resp, "创建文档")
    doc_id = resp["data"]["document"]["document_id"]
    return doc_id, f"https://feishu.cn/docx/{doc_id}"

def _create_in_wiki(title: str, space_id: str, parent_node_token: str, user_token: str):
    if not space_id:
        resp = _api_get(f"/wiki/v2/spaces/get_node", {"token": parent_node_token, "obj_type": "wiki"}, user_token)
        space_id = resp.get("data", {}).get("node", {}).get("space_id", "")
    resp = requests.post(f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes", headers=_headers(user_token),
                         json={"obj_type": "docx", "node_type": "origin", "parent_node_token": parent_node_token, "title": title},
                         timeout=15).json()
    _check_response(resp, "创建 Wiki 节点")
    node = resp["data"]["node"]
    return node.get("obj_token", ""), node.get("obj_edit_url") or f"https://feishu.cn/wiki/{node['node_token']}"

def _write_blocks(doc_id: str, blocks: list[dict], user_token: str):
    BATCH = 50
    for i in range(0, len(blocks), BATCH):
        chunk = blocks[i: i + BATCH]
        resp = requests.post(f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                             headers=_headers(user_token), json={"children": chunk, "index": 0}, timeout=30).json()
        _check_response(resp, f"写入第 {i//BATCH + 1} 批内容")

# ─── Markdown → 丰富格式转换 ──────────────────────────────────────────────────

def _markdown_to_feishu_blocks(markdown: str, image_map: dict[str, str]) -> list[dict]:
    blocks = []
    lines  = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. 代码块：降级为带行内代码样式的段落
        if line.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i]); i += 1
            if code_lines:
                blocks.append({
                    "block_type": 2,
                    "text": {"elements": [{"text_run": {"content": "\n".join(code_lines), "text_element_style": {"inline_code": True}}}]}
                })
            i += 1; continue
            
        # 2. 分割线
        if re.match(r"^[-*_]{3,}$", line.strip()):
            blocks.append({"block_type": 11, "divider": {}}); i += 1; continue
            
        # 3. 标题
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            blocks.append({
                "block_type": level + 2, # H1->3, H2->4...
                f"heading{level}": {"elements": _parse_inline(text or " ")}
            })
            i += 1; continue
            
        # 4. 图片：关键修正字段名 file_token
        img_match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", line)
        if img_match:
            url = img_match.group(1); token = image_map.get(normalize_url(url))
            if token:
                blocks.append({"block_type": 27, "image": {"file_token": token}})
            i += 1; continue
            
        # 5. 普通段落：带行内样式解析
        blocks.append({"block_type": 2, "text": {"elements": _parse_inline(line)}})
        i += 1
        
    return blocks

def _parse_inline(text: str) -> list[dict]:
    """
    解析行内 Markdown 样式：**粗体**, _斜体_, `行内代码`
    """
    # 基础清洗：移除 Markdown 链接语法，仅保留显示文字
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', '', text)
    text = text.replace('\n', ' ').strip()
    if not text: return [{"text_run": {"content": " "}}]
    
    elements = []
    pos = 0
    # 正则匹配：粗体、行内代码、斜体
    for m in re.finditer(r'\*\*(.+?)\*\*|__(.+?)__|`(.+?)`|_(.+?)_', text):
        # 处理匹配前的普通文本
        if m.start() > pos:
            elements.append({"text_run": {"content": text[pos: m.start()]}})
            
        raw = m.group(0)
        style = {}
        if raw.startswith("**") or raw.startswith("__"): style["bold"] = True
        elif raw.startswith("`"): style["inline_code"] = True
        elif raw.startswith("_"): style["italic"] = True
        
        content = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
        item = {"text_run": {"content": content}}
        if style: item["text_run"]["text_element_style"] = style
        elements.append(item)
        pos = m.end()
        
    # 处理剩余文本
    if pos < len(text):
        elements.append({"text_run": {"content": text[pos:]}})
        
    return elements

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
