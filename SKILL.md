---
name: wechat2feishu-pro-pro
description: 高保真微信文章转存专用工具。必须通过执行本地 python 脚本完成，严禁使用内置 MCP 工具。支持自动抓取、Wiki 挂载和图片比例修复。
---

# WeChat2Feishu-Pro 强制执行指南

## ⚠️ 核心规则
**本技能的所有操作必须通过调用以下指定的本地脚本完成。不要使用任何名为 `feishu_mcp` 或类似的内置工具。**

## 🚀 任务执行指令

### 1. 抓取文章 (Scrape)
当用户发送链接时，**必须**运行此命令：
```bash
/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py scrape "{URL}"
```

### 2. 执行转存 (Save)
根据用户确认的目标，**必须**运行以下对应的黑盒命令。脚本内部已处理所有权限和 Wiki 逻辑：

**存入主页 (默认)：**
```bash
/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py save --dest-type root
```

**存入文件夹：**
```bash
/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py save --dest-type folder --dest-token {token}
```

**存入知识库 (Wiki)：**
```bash
/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py save --dest-type wiki --dest-token {space_id} --node-token {node_token}
```

## 🛠️ 辅助指令
- 列出目录：`/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py list-folders`
- 列出知识库：`/Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/.venv/bin/python /Users/zhanghanlin/Documents/VibeCoding2/wechat2feishu-pro/scripts/main.py list-wikis`
