# 📔 WeChat2Feishu-Pro 开发沉淀日志 (v1.0 完结篇)

本日志记录了项目从基础功能到“Pro”级进化的全过程。这是我们共同攻克飞书 API 陷阱、优化用户体验的见证。

---

## 📅 项目时间轴：2026-03-09 至 2026-03-10

### 1. 🖼️ 图片防盗链与渲染的“终极方案”
- **技术突破**：弃用传统的“重抓 URL”逻辑，改为利用 `Playwright` 监听网络响应，在浏览器渲染瞬间捕获 **Binary 二进制原数据**。
- **排版创新**：设计了“替身修补战术” (Two-Step Patch)。先用占位符生成文档，再通过 Docx Patch 接口精准回填图片。
- **比例修正**：集成 `Pillow` 库，动态识别图片宽高，解决了飞书转存中长期存在的图片拉伸变形问题。

### 2. 🛡️ 攻克 Wiki 知识库的“内容黑洞”
- **避坑指南**：确认飞书 Wiki 挂载时 `node_type: "origin"` 会导致内容丢失。
- **解决方案**：切换为官方推荐的 **`move_docs_to_wiki`** 接口，并配合 `drive_route_token` 路由参数，确保了内容 100% 物理搬迁且图片可见。
- **管理权限突破**：发现 Tenant 模式创建的文档默认为机器人私有。通过 **“空间预授权 + 自动赋权”** 机制，实现了在创建后立即通过 API 将该文档的 **Full Access (管理权限)** 授予管理员，彻底解决了用户无法管理转存文档的问题。
- **标题修复**：在导入阶段显式指定 `title` 字段，解决了 Wiki 文档名称缺失的问题。


### 3. 🤖 OpenClaw 深度适配与智能决策
- **产品化升级**：将“程序员工具”进化为“智能助理”。
- **静默授权**：默认开启 **Tenant Mode (机器人身份)**，通过后台 API 自动续期 Token，实现了真正的无人值守，彻底告别浏览器弹窗。
- **智能路由**：设计了“特定目录 > 默认路径 > 系统主页”的多级存储策略，提升了 Skill 的通用性和鲁棒性。

### 4. 📂 本地知识库的“最优解”
- **结构抉择**：放弃了由于 Base64 内联导致的“源码不可读”模式，回归 **“文件夹 + README.md + images/”** 经典解耦结构。
- **沉淀认知**：理解到 Markdown 的力量在于其简洁性，本地备份应以“易于检索和二次编辑”为第一准则。

---

## 💡 核心箴言 (Final Lessons)
1. **API 只是工具，逻辑才是灵魂**：飞书 API 极其复杂且多变，通过“多重判断”和“容错提取”建立的稳健性比代码量更重要。
2. **好的 Skill 应该是黑盒**：用户不需要理解复杂的挂载逻辑，只需要一个简单的“反馈链接”。
3. **沉淀是资产的复利**：每一次报错后的复盘（如 `99992402` 错误），都是下一阶段（1.1版本）最坚实的基石。

---
*WeChat2Feishu-Pro v1.0 正式交付。1.1 “情报哨兵”计划即将开启。*

---

## 📅 项目时间轴：2026-03-11

### 5. 🛰️ v1.1.0-alpha “情报哨兵” (Sentinel) 核心落地
- **自动化闭环**：实现了基于 RSS 的自动巡逻脚本 `sentinel.py`。通过 `feedparser` 监听情报源，发现新文章后全自动触发 `scrape` 和 `save` 流程。
- **通知机制集成**：新增了 `notify` 指令。当哨兵成功转存文章后，会通过飞书机器人向管理员发送即时通知，并附带生成的 **飞书文档直链** 和原文链接，实现了“情报获取 -> 存储 -> 提醒”的完整闭环。
- **配置管理工具化**：为 `sentinel.py` 增加了完善的 CLI 交互，支持 `list-feeds`, `add-feed`, `remove-feed` 命令，彻底告别了手动编辑 JSON 配置文件。
- **环境迁移兼容性修复**：修复了项目迁移后虚拟环境 (`.venv`) 路径硬编码导致的解释器失效问题，并将所有内部路径逻辑重构为基于项目根目录的相对路径，极大提升了项目的可移植性。

---
*WeChat2Feishu-Pro v1.1.0-alpha 已就绪。哨兵巡逻中...*

---

## ⭐ 📅 2026-03-17 — v1.2.0 稳定版（重要里程碑）

> **此版本为首个图片功能完全正常的稳定版本，推荐作为回滚基准点。**
>
> 🏷️ Git Tag：`v1.2.0`
> 📌 Commit：`4440b46`（文档）/ `05cecce`（核心修复）
> ⏪ 回滚命令：`git checkout v1.2.0`

### 6. 🐛 彻底根治图片 `relation mismatch` 问题

**问题溯源**：

经过逐行代码审查，发现 `feishu.py` 的 `create_document` 函数中存在**三套实现混叠**的历史遗留问题：
- 第一套（144–259 行）：`upload_and_replace` 函数，定义后从未调用
- 第二套（261–325 行）：`patch_one_image` 函数，依赖未定义变量 `placeholder_to_url`，在 executor 中静默抛出 `NameError`
- 第三套（370–437 行）：实际运行的路径，但存在致命 Bug

**根本 Bug（第 412 行）**：
```python
# 错误：图片上传时 parent_node 指向文档本身
"parent_node": doc_token

# 正确：必须指向具体的图片块 block_id
"parent_node": block_id
```
飞书 `docx_image` 上传 API 要求 `parent_node` = 目标图片块的 `block_id`，才能建立正确的父子关系。使用 `doc_token` 导致关系绑定错误，后续 `replace_image` PATCH 时飞书校验失败 → `relation mismatch`。

**次要 Bug（第 424 行）**：`replace_image` payload 包含了不被支持的 `width`/`height` 字段。

**修复内容**：
- `parent_node`: `doc_token` → `block_id`
- `replace_image` payload 仅保留 `token`
- 删除两套死代码，函数从 325 行精简至 131 行
- Wiki 挂载逻辑从 `if image_urls` 分支内独立提取，消除耦合

**验证结果**：11/11 图片全部 Patch 成功，Wiki 知识库挂载正常。

---

### 7. 📝 修复安装文档六处错误

发现并修复了导致用户无法正确安装的关键文档问题：

| 文件 | 问题 | 修复 |
| :--- | :--- | :--- |
| `README.md` | `openclaw skills install` 命令不存在 | 改为 `git clone` 正确方式 |
| `README.md` | 缺少升级说明 | 补充 `git pull` 升级章节 |
| `README.md` | `.env` 字段说明不准确 | 对齐实际变量名，说明 `ADMIN_USER_ID` 自动写入 |
| `SKILL.md` | 路径硬编码为开发者本机目录 | 改为通用安装路径 `~/.openclaw/skills/wechat2feishu-pro` |
| `setup.sh` | `requirements.txt` 路径错误 | 改为 `scripts/requirements.txt` |
| `setup.sh` | 末尾提示 auth 路径错误 | 改为 `.venv/bin/python scripts/auth.py login` |

---

### 💡 版本管理建议（供后续维护参考）

**回滚操作**：
```bash
# 回滚到 v1.2.0（当前稳定版）
git checkout v1.2.0

# 查看所有可用版本
git tag -l

# 查看某个版本的详情
git show v1.2.0
```

**发布新版本的标准流程**：
```bash
# 1. 确认所有改动已 commit 并 push
# 2. 打 Tag（语义化版本：v主版本.次版本.补丁）
git tag -a v1.x.x -m "版本说明"
git push origin v1.x.x
# 3. 在开发日志中记录 Tag 和 Commit Hash
```

---
*WeChat2Feishu-Pro v1.2.0 稳定版交付。图片注入功能已完全修复，可正式对外分发。*
