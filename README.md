# 🚀 WeChat2Feishu-Pro (适配 OpenClaw)
### 微信文章一键转存飞书：高保真、智能路由、无人值守。

**WeChat2Feishu-Pro** 是一款专门为飞书用户打造的自动化剪藏工具。它解决了微信图片防盗链、排版错乱、代码块截断以及 Wiki 权限等核心痛点。

---

## 🤖 通过 OpenClaw 一键安装 (推荐)

如果你正在使用 OpenClaw (或 Gemini CLI)，可通过以下步骤快速集成：

### 1. 安装技能
在终端运行以下命令（根据你的工具名选择 `openclaw` 或 `gemini`）：
```bash
openclaw skills install https://github.com/jackcheng459/WeChat2Feishu-Pro
# 或者
gemini skills install https://github.com/jackcheng459/WeChat2Feishu-Pro
```

### 2. 初始化环境
技能会自动下载到 `~/.openclaw/skills/WeChat2Feishu-Pro`。请进入该目录执行环境安装：
```bash
cd ~/.openclaw/skills/WeChat2Feishu-Pro
bash scripts/setup.sh
```

### 3. 配置与授权
1.  **创建配置**：`cp .env.example .env` 并填入你的 **App ID** 和 **App Secret**。
2.  **首次授权**：运行 `python3 scripts/auth.py login` 完成扫码验证。
3.  **权限赋予**：将你的飞书应用添加为目标文件夹/知识库的**管理员**。

---

## ✨ 核心优势
- **🛡️ 捕获二进制原图**：彻底杜绝微信图片防盗链导致的 `default.png`。
- **📐 比例精准适配**：自动识别图片宽高并同步注入飞书，拒绝图片拉伸。
- **🤖 智能存储路由**：支持“即时指定 > 默认记忆 > 系统主页”的多级存储逻辑。
- **📁 双轨存档**：云端存入飞书，本地同步生成标准 `README.md` + 原图文件夹。

---

## 📂 项目结构
- `SKILL.md`: 官方技能定义文件。
- `scripts/`: 核心执行脚本（抓取、转换、赋权）。
- `references/`: 架构手册与开发日志。
- `exports/`: 本地图文备份。

## 🤝 鸣谢
本项目灵感源自 [wechat2feishu](https://github.com/zhaodl1983/wechat2feishu)，并在其基础上进行了 Pro 级深度重构。
