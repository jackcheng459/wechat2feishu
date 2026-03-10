# OpenClaw Skill：WeChat2Feishu-Pro (多级存储决策版)

## Skill 名称
`wechat2feishu-pro`

## 描述
微信公众号高保真转存机器人。支持自动抓取并提供多层级的存储目标建议（最近使用/默认路径/系统主页），引导用户快速决策。

---

## 🤖 工作流逻辑

### 1. 触发与抓取
- **触发**：检测到 `mp.weixin.qq.com` 链接。
- **执行**：运行 `python main.py scrape "{URL}"` 抓取文章并缓存图片数据。
- **展示**：向用户展示文章预览（标题、摘要、图片数）。

### 2. 存储目标询问与决策
机器人应引导用户按以下优先级确定存储位置：

#### **步骤 A：请求指定或确认**
机器人询问：“文章处理完毕！您想存到哪？”并提供以下选项供用户快捷选择：
1. **即时指定**：提示用户可以直接发送一个文件夹/知识库的链接或名称。
2. **默认路径建议**：若用户记忆（Memory）中有 `default_save_path`，主动推荐：“是否存入您的默认目录：{path_name}？”
3. **系统主页兜底**：若无默认设置，提示：“或者直接存入您的飞书云文档主页？”

#### **步骤 B：执行保存**
根据用户的最终回复（编号或路径名称）调用对应的 `save` 命令。

---

## 执行指令示例

### 获取目标列表 (用于展示选项)
```bash
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && .venv/bin/python main.py list-folders
```

### 执行保存
- **存入指定/默认文件夹**：`cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && .venv/bin/python main.py save --dest-type folder --dest-token {token}`
- **存入指定/默认知识库**：`cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && .venv/bin/python main.py save --dest-type wiki --dest-token {space_id} --node-token {node_token}`
- **存入主页**：`cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && .venv/bin/python main.py save --dest-type root`


---

## 预期结果
转存成功后反馈：确认消息 + 最终文档链接。
注意：本技能不设自动超时处理，必须等待用户确认后方可执行写入操作。
