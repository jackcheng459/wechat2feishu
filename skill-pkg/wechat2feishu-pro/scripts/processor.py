"""
processor.py — 内容处理模块
职责：清洗 HTML → 转换 Markdown → 提取结构化数据
不涉及任何网络请求（纯本地处理）
"""

import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from scraper import RawArticle


@dataclass
class ProcessedArticle:
    """处理完毕的文章，准备写入飞书"""
    url: str
    title: str
    author: str
    publish_time: str
    markdown: str               # 转换后的 Markdown 正文
    image_urls: list[str]       # 需要上传到飞书图床的图片列表
    word_count: int             # 正文字数（估算）
    summary: str                # 前100字摘要，用于 OpenClaw 展示预览


# 需要从 HTML 中移除的广告/无用区块
_REMOVE_SELECTORS = [
    # 微信底部关注提示
    "#js_pc_qr_code",
    "#js_subscribe_btn",
    ".qr_code_pc_outer",
    # 广告相关
    ".ad_cover",
    "#js_sponsor_ad_area",
    ".rich_media_tool",
    # 底部推广文字区域
    "#js_bottom_bar",
    ".weui-flex__item",
]

# 需要移除的 CSS class 关键词（模糊匹配）
_REMOVE_CLASS_PATTERNS = [
    "subscribe", "qr_code", "sponsor", "ad_",
    "bottom_bar", "follow", "profile_inner",
]


def process(raw: RawArticle) -> ProcessedArticle:
    """
    主入口：将 RawArticle 处理为 ProcessedArticle
    """
    cleaned_html = _clean_html(raw.content_html)
    markdown_text = _to_markdown(cleaned_html)
    markdown_text = _post_process_markdown(markdown_text)

    word_count = _count_words(markdown_text)
    summary = _extract_summary(markdown_text)

    return ProcessedArticle(
        url=raw.url,
        title=raw.title,
        author=raw.author,
        publish_time=raw.publish_time,
        markdown=markdown_text,
        image_urls=raw.image_urls,
        word_count=word_count,
        summary=summary,
    )


def _clean_html(html: str) -> str:
    """清洗 HTML：移除广告、无用元素，修复图片 src"""
    soup = BeautifulSoup(html, "html.parser")

    # 移除指定选择器的元素
    for selector in _REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # 移除含有广告关键词 class 的元素
    for tag in soup.find_all(True):
        # 跳过无 attrs 的标签（如注释、文档类型声明等）
        if tag.attrs is None:
            continue
        classes = tag.get("class", [])
        class_str = " ".join(classes).lower()
        if any(pat in class_str for pat in _REMOVE_CLASS_PATTERNS):
            tag.decompose()

    # 修复懒加载图片：将 data-src 替换为 src
    for img in soup.find_all("img"):
        data_src = img.get("data-src")
        if data_src:
            img["src"] = data_src
            del img["data-src"]
        # 移除微信图片水印参数（保留原图）
        src = img.get("src", "")
        if src and "wx_fmt=" in src:
            # 保留格式参数，移除其他追踪参数
            src = re.sub(r"&?(tp|wxfrom|wx_lazy|wx_co|retryload)=\w+", "", src)
            img["src"] = src.strip("&?")

    # 移除空的 <p> 和 <section> 标签
    for tag in soup.find_all(["p", "section", "span"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    return str(soup)


def _to_markdown(html: str) -> str:
    """将清洗后的 HTML 转换为 Markdown"""
    return md(
        html,
        heading_style="ATX",        # 使用 # 风格标题
        bullets="-",                 # 列表用 - 符号
        strip=["script", "style", "meta", "link"],
    )


def _post_process_markdown(text: str) -> str:
    """Markdown 后处理：清理多余空行、规范格式"""
    # 1. 替换微信常见的特殊不可见字符
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    
    # 2. 核心修复：强制隔离紧跟在图片后的标题 (e.g. "![图片](...)### 标题" -> 换行)
    text = re.sub(r"(!\[.*?\]\(.*?\))\s*(#{1,6}\s+)", r"\1\n\n\2", text)
    
    # 3. 规范化标题前面的空格，确保顶格
    text = re.sub(r"^[ \t]+(#{1,6}\s)", r"\1", text, flags=re.MULTILINE)
    # 规范化标题标记后的空格 (e.g. "###  标题" -> "### 标题")
    text = re.sub(r"^(#{1,6})\s+", r"\1 ", text, flags=re.MULTILINE)
    
    # 4. 核心修复：精准剥离被反引号和乱码包裹的微信代码块
    # 微信常见的坑：`{ json }``![图片]` -> 恢复为标准 JSON 块
    text = re.sub(r"`+({.*?\s*\"scopes\":.*})\s*`+\s*(!\[.*?\]\(.*?\))", r"```json\n\1\n```\n\n\2", text, flags=re.DOTALL)
    
    # 5. 通用代码块规整：确保 ``` 前后有空行，防止飞书解析粘连
    text = re.sub(r"([^\n])\s*```", r"\1\n\n```", text)
    text = re.sub(r"```\s*([^\n])", r"```\n\n\1", text)
    
    # 6. JSON 内容基础美化 (仅针对 scopes 类大配置)
    def format_json_match(m):
        content = m.group(1)
        content = re.sub(r"([{\[,])\s*", r"\1\n  ", content)
        content = re.sub(r"([}\]])", r"\n\1", content)
        return f"```json\n{content}\n```"
    text = re.sub(r"```json\n({.*?\s*\"scopes\":.*})\n```", format_json_match, text, flags=re.DOTALL)
    
    # 7. 移除连续超过2个空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 移除行首行尾多余空格
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = text.strip()
    return text


def _count_words(markdown_text: str) -> int:
    """估算正文字数（去掉 Markdown 标记后）"""
    # 移除 Markdown 语法符号
    plain = re.sub(r"[#*`\[\]()>!\-_~]", "", markdown_text)
    plain = re.sub(r"https?://\S+", "", plain)  # 移除 URL
    # 中文按字符计，英文按单词计
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", plain))
    english_words = len(re.findall(r"[a-zA-Z]+", plain))
    return chinese_chars + english_words


def _extract_summary(markdown_text: str, length: int = 100) -> str:
    """提取前 N 字作为摘要"""
    plain = re.sub(r"[#*`\[\]()>!\-_~]", "", markdown_text)
    plain = re.sub(r"\n+", " ", plain).strip()
    return plain[:length] + "…" if len(plain) > length else plain


if __name__ == "__main__":
    # 快速测试（配合 scraper.py 使用）
    import sys
    from scraper import scrape

    if len(sys.argv) < 2:
        print("用法: python processor.py <公众号文章URL>")
        sys.exit(1)

    raw = scrape(sys.argv[1])
    result = process(raw)

    print(f"标题：{result.title}")
    print(f"字数：{result.word_count}")
    print(f"摘要：{result.summary}")
    print(f"图片：{len(result.image_urls)} 张")
    print("\n--- Markdown 前300字 ---")
    print(result.markdown[:300])
