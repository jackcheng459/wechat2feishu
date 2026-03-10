---
name: wechat2feishu-pro
version: 1.0.0
author: zhanghanlin
description: 高保真微信公众号文章转存飞书工具。支持绕过防盗链、保留排版及图片比例、支持 Wiki 知识库挂载及本地备份。适用于需要将微信内容归档到飞书办公环境的场景。
tags: [feishu, wechat, document, automation, archiving]
runtime: python3
entry: scripts/main.py
setup: scripts/setup.sh
---

# WeChat2Feishu-Pro 官方技能指南

本技能允许你将微信公众号链接一键转存至飞书云文档或知识库。

## ⚙️ 环境初始化
在首次使用前，需要确保环境已安装。
执行以下指令完成初始化：
```bash
bash scripts/setup.sh
```

## 🚀 核心指令流

### 1. 抓取与预览
当用户发送微信文章链接时，先执行抓取：
```bash
python3 scripts/main.py scrape "{URL}"
```
根据返回的 JSON，向用户展示标题、作者、字数及摘要。

### 2. 存储目标选择
询问用户存储位置。如果用户不确定，可以调用以下指令列出目录：
```bash
# 列出云空间文件夹
python3 scripts/main.py list-folders
# 列出知识库
python3 scripts/main.py list-wikis
```

### 3. 执行最终保存
根据用户选择的目标（folder 或 wiki），执行保存：
```bash
# 存入个人文件夹
python3 scripts/main.py save --dest-type folder --dest-token {token}

# 存入知识库
python3 scripts/main.py save --dest-type wiki --dest-token {space_id} --node-token {node_token}

# 存入云文档主页
python3 scripts/main.py save --dest-type root
```

## 🛡️ 授权管理
如果由于 Token 过期导致失败，提示用户运行：
```bash
python3 scripts/auth.py login
```

## 📝 架构与日志
- 详细架构请参考 [TECHNICAL_ARCHITECTURE.md](references/TECHNICAL_ARCHITECTURE.md)
- 开发心得请参考 [DEVELOPMENT_LOG.md](references/DEVELOPMENT_LOG.md)
