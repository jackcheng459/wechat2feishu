# 🛰️ wechat2feishu-pro
### 微信文章 → 飞书文档：高保真、全自动、智能剪藏工作站

![Version](https://img.shields.io/badge/Version-v1.1.0--alpha-blue.svg?style=for-the-badge) ![Platform](https://img.shields.io/badge/Platform-Feishu%20|%20OpenClaw-green.svg?style=for-the-badge) ![License](https://img.shields.io/badge/License-MIT-orange.svg?style=for-the-badge)

**wechat2feishu-pro** 是一款专为深度阅读者和知识管理者打造的自动化剪藏工具。它解决了微信图片防盗链、排版拉伸、代码块截断以及 Wiki 权限等核心痛点，并引入了“情报哨兵”系统实现 24/7 全自动订阅转存。

---

## 🏗️ 核心工作流 (Workflow)

```text
微信公众号文章 (URL) 
       │
       ▼
[ 采集引擎 (Playwright) ] ──▶ 模拟渲染，捕获二进制图片 (Bypass Hotlink)
       │
       ▼
[ 处理核心 (Processor) ] ──▶ HTML 清洗 -> 标准 Markdown -> 图片比例计算 (Pillow)
       │
       ▼
[ 分发中心 (Feishu API) ] ──▶ 自动导入 (Import) -> 高保真 Patch -> 权限自动赋予
       │
   ┌───┴───┐
   ▼       ▼
(云端存入) (本地备份)
飞书/Wiki  README+Images
   │
   ▼
[ 哨兵通知 (Sentinel) ] ──▶ 飞书机器人推送：文章标题 + 飞书直连 URL
```

---

## ✨ 核心优势

*   **🛡️ 彻底终结“图片加载失败”**：底层拦截浏览器渲染瞬时的 **Binary 二进制原数据**，彻底绕过微信 CDN 防盗链，图片永不丢失。
*   **📐 图片比例精准修复**：集成 `Pillow` 引擎识别图片物理宽高，拒绝飞书转存中常见的图片拉伸变形。
*   **🤖 v1.1 “情报哨兵” (Sentinel)**：内置 RSS 监听引擎，自动轮询订阅源。发现新文即刻转存，并由机器人主动向您推送 **飞书直链通知**。
*   **📁 智能存储路由**：支持“即时指定目录 > 默认记忆路径 > 系统主页根目录”的多级存储逻辑，完美支持 **Wiki 知识库** 挂载。
*   **🔐 权限自动闭环**：采用 Tenant 模式静默授权。机器人创建文档后自动将 **管理权限 (Full Access)** 授予管理员，解决权限隔离问题。

---

## 🚀 快速上手

### 1. 通过 OpenClaw 一键集成 (推荐)
在您的终端中执行：
```bash
openclaw skills install https://github.com/jackcheng459/wechat2feishu-pro
```

### 2. 环境初始化
```bash
cd ~/.openclaw/skills/wechat2feishu-pro
bash scripts/setup.sh
cp .env.example .env  # 填入 APP_ID, APP_SECRET, ADMIN_USER_ID
```

### 3. 配置“情报哨兵”自动巡逻
```bash
# 查看当前巡逻中的情报源
./.venv/bin/python ./tools/sentinel.py list-feeds

# 添加订阅源（支持本地 RSS 或 URL）
./.venv/bin/python ./tools/sentinel.py add-feed --name "公众号名称" --url "RSS链接"

# 启动巡逻任务
./.venv/bin/python ./tools/sentinel.py run
```

---

## 🛠️ 指令手册 (CLI Usage)

| 指令 | 说明 |
| :--- | :--- |
| `main.py scrape {URL}` | 抓取并处理文章，生成本地预览 JSON |
| `main.py save --dest-type root` | 将抓取的文章转存至飞书个人主页 |
| `main.py save --dest-type wiki` | 将文章挂载至指定的 Wiki 知识库节点 |
| `main.py list-folders` | 列出可用的飞书云空间文件夹 |
| `sentinel.py run-once` | 执行一次全量巡逻并退出 |

---

## 📂 项目结构

- `SKILL.md`: OpenClaw 技能定义规范
- `scripts/`: 核心执行逻辑（Scraper, Processor, Feishu API）
- `tools/`: 哨兵系统与配置管理工具
- `references/`: 技术架构手册与开发沉淀日志
- `exports/`: 本地图文离线备份

---

## 🤝 鸣谢与申明
*   灵感源自 `wechat2feishu`，由本人进行 Pro 级深度重构与功能扩展。
*   本项目仅供个人学习与知识沉淀使用，请遵守相关法律法规。

---
*wechat2feishu-pro v1.1.0-alpha | 2026-03-11*
