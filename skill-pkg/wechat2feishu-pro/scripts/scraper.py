"""
scraper.py — 微信公众号文章抓取模块
使用 Playwright 模拟真实浏览器，绕过微信反爬机制
"""

import asyncio
import json
import base64
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


@dataclass
class RawArticle:
    """抓取到的原始文章数据"""
    url: str
    title: str
    author: str
    publish_time: str
    content_html: str       # 正文原始 HTML
    image_urls: list[str]   # 所有图片链接
    image_data: dict = field(default_factory=dict)  # {url: base64编码的图片数据}


async def fetch_article(url: str) -> RawArticle:
    """
    主入口：抓取公众号文章
    返回 RawArticle 数据对象
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            locale="zh-CN",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        page = await context.new_page()

        # 拦截图片响应，直接保存二进制数据（绕过微信防盗链）
        image_data: dict[str, str] = {}

        async def handle_response(response):
            try:
                content_type = response.headers.get("content-type", "")
                if "image" in content_type and "mmbiz" in response.url:
                    body = await response.body()
                    if body:
                        image_data[response.url] = base64.b64encode(body).decode("utf-8")
            except Exception:
                pass

        page.on("response", handle_response)

        # 屏蔽广告追踪脚本，加速加载
        await page.route(
            "**/{adtrack,stat,res,wx_api}**",
            lambda route: route.abort(),
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeout:
            await browser.close()
            raise RuntimeError(f"页面加载超时：{url}")

        # 等待正文区域渲染完成
        try:
            await page.wait_for_selector("#js_content, .rich_media_content", timeout=15_000)
        except PlaywrightTimeout:
            await browser.close()
            raise RuntimeError("正文区域未找到，该链接可能已失效或需要登录")

        # 滚动页面以触发所有懒加载图片
        await page.evaluate("""async () => {
            await new Promise(resolve => {
                let totalHeight = 0;
                const distance = 300;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= document.body.scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")
        # 等待图片响应完成
        await page.wait_for_timeout(2000)

        # 提取关键字段
        title = await _extract_text(page, [
            "#activity-name",
            ".rich_media_title",
            "h1",
        ])

        author = await _extract_text(page, [
            "#js_name",
            ".rich_media_meta_nickname",
            ".account_nickname_inner",
        ])

        publish_time = await _extract_text(page, [
            "#publish_time",
            "em#publish_time",
            ".rich_media_meta_text",
        ])

        # 提取正文 HTML
        content_html = await page.evaluate("""() => {
            const el = document.querySelector('#js_content')
                     || document.querySelector('.rich_media_content');
            return el ? el.innerHTML : '';
        }""")

        # 提取所有图片真实地址（处理 data-src 懒加载）
        image_urls = await page.evaluate("""() => {
            const imgs = document.querySelectorAll(
                '#js_content img, .rich_media_content img'
            );
            const urls = [];
            imgs.forEach(img => {
                const src = img.getAttribute('data-src')
                          || img.getAttribute('src')
                          || '';
                if (src && src.startsWith('http')) {
                    urls.push(src);
                }
            });
            return [...new Set(urls)];  // 去重
        }""")

        await browser.close()

        return RawArticle(
            url=url,
            title=title.strip() or "无标题",
            author=author.strip() or "未知作者",
            publish_time=publish_time.strip() or "",
            content_html=content_html,
            image_urls=image_urls,
            image_data=image_data,
        )


async def _extract_text(page, selectors: list[str]) -> str:
    """按优先级尝试多个选择器，返回第一个非空文本"""
    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                if text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


def scrape(url: str) -> RawArticle:
    """同步包装器，供 main.py 调用"""
    return asyncio.run(fetch_article(url))


if __name__ == "__main__":
    # 快速测试
    import sys
    if len(sys.argv) < 2:
        print("用法: python scraper.py <公众号文章URL>")
        sys.exit(1)

    article = scrape(sys.argv[1])
    print(f"标题：{article.title}")
    print(f"作者：{article.author}")
    print(f"时间：{article.publish_time}")
    print(f"图片：{len(article.image_urls)} 张")
    print(f"HTML长度：{len(article.content_html)} 字符")
