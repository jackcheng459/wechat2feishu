---
name: wechat2feishu-pro
description: 高保真微信转存。save 命令涉及多图上传，请确保其 exec_timeout 设置在 60s 以上。
---

# wechat2feishu-pro 强制执行指南

## ⚠️ 核心规则
**本技能的所有操作必须通过调用以下指定的本地脚本完成。不要使用任何名为 `feishu_mcp` 或类似的内置工具。**

## 🚀 任务执行指令

### 1. 抓取与存储建议 (Scrape & Auto-Sentinel)
当用户发送链接时，**必须**按此流程执行：
1.  **抓取**：`./.venv/bin/python ./scripts/main.py scrape "{URL}"`
2.  **情报源识别**：`./.venv/bin/python ./tools/discover_feed.py "{URL}"`
3.  **询问**：将抓取成功的信息告诉用户。同时，如果 `discover_feed.py` 成功识别了公众号，**主动询问**用户是否要将其加入自动监听，并列出当前的飞书目录供用户选择一个专用的保存文件夹。

### 2. 执行转存 (Save)
根据用户确认的目标执行转存。**必须**使用以下对应的黑盒命令：

**存入主页 (默认)：**
```bash
./.venv/bin/python ./scripts/main.py save --dest-type root
```

**存入指定文件夹：**
```bash
./.venv/bin/python ./scripts/main.py save --dest-type folder --dest-token {token}
```

**存入知识库 (Wiki)：**
```bash
./.venv/bin/python ./scripts/main.py save --dest-type wiki --dest-token {space_id} --node-token {node_token}
```

### 3. 配置自动哨兵 (Add Sentinel Feed)
如果用户同意将该公众号加入自动监听，并指定了目标文件夹，执行以下命令：
```bash
./.venv/bin/python ./tools/sentinel.py add-feed --name "{公众号名称}" --url "{RSS_URL}" --dest-type "{type}" --dest-token "{token}" --node-token "{node_token}"
```

## 🛠️ 辅助指令
- 列出目录：./.venv/bin/python ./scripts/main.py list-folders
- 列出知识库：./.venv/bin/python ./scripts/main.py list-wikis
