# OpenClaw Skill：微信公众号转存飞书

## Skill 名称
`WeChat2Feishu-Pro`

## 描述
检测到微信公众号链接时，自动抓取文章内容，处理图片防盗链，
询问用户存储目标后，将文章一键转存至飞书云文档或知识库。

---

## 触发规则（在 OpenClaw 中配置）

**触发条件**：消息内容包含以下任意域名
```
mp.weixin.qq.com
```

**触发动作**：执行本 Skill

---

## 执行脚本路径
```
~/Documents/VibeCoding2/WeChat2Feishu-Pro/
```

---

## 完整执行逻辑

### Step 1 — 抓取文章

```bash
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && \
.venv/bin/python main.py scrape "{检测到的URL}"
```

输出示例（JSON）：
```json
{
  "status": "ready",
  "title": "就因为评论区那10个人…",
  "author": "AI编程瓜哥",
  "publish_time": "2026-01-13",
  "word_count": 2800,
  "image_count": 8,
  "summary": "半年前，我发了一篇文章…"
}
```

### Step 2 — 向用户展示预览，询问存储位置

向用户发送以下消息：

```
✅ 文章处理完毕！

📄 标题：{title}
✍️  作者：{author}
📅 时间：{publish_time}
📊 字数：{word_count} 字 | 🖼️ 图片：{image_count} 张

💬 摘要：{summary}

---
请问存到哪里？我来列出可用目录：
```

同时运行以下命令获取目录列表：

```bash
# 个人云空间文件夹
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && \
.venv/bin/python main.py list-folders

# 知识库列表
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && \
.venv/bin/python main.py list-wikis
```

将结果整合成编号菜单发给用户：

```
📂 个人云空间：
  1. AI工具收藏 (folder_token: xxx)
  2. 技术参考 (folder_token: yyy)

📚 知识库：
  3. 团队知识库 / AI工具 (space_id: zzz)

请回复数字选择，或输入其他路径。
```

**⚠️ 重要：等待用户回复，不要自动存储。**

### Step 3 — 用户确认后执行保存

根据用户选择，执行对应命令：

**存到个人空间文件夹：**
```bash
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && \
.venv/bin/python main.py save \
  --dest-type folder \
  --dest-token {folder_token}
```

**存到知识库：**
```bash
cd ~/Documents/VibeCoding2/WeChat2Feishu-Pro && \
.venv/bin/python main.py save \
  --dest-type wiki \
  --dest-token {space_id} \
  --node-token {node_token}
```

### Step 4 — 回复用户结果

```
✅ 转存成功！

📄 《{title}》已保存到 {用户选择的目录名}
👉 点击查看：{document_url}

---
💡 已将此分类记录到我的学习列表。
下次遇到类似文章，我会主动建议存到这里。
```

---

## 分类学习机制

每次成功保存后，在 OpenClaw 的记忆文件中追加一条记录：

**文件路径**：`~/Documents/VibeCoding2/WeChat2Feishu-Pro/classification-memory.md`

**追加格式**：
```markdown
| {日期} | {文章关键词/标签} | {目标目录名} | {dest_type} | {dest_token} |
```

**建议时机**：
- 当用户发来新文章时，先在分类记忆中查找关键词匹配
- 匹配度 > 60% 时，在 Step 2 中主动建议：
  ```
  💡 根据你之前的习惯，这篇文章可能适合存到「AI工具收藏」，要存这里吗？
  （或者告诉我其他目录）
  ```

---

## 错误处理

| 错误情况 | 处理方式 |
|---------|---------|
| 页面加载超时 | 告知用户该链接可能已失效，建议重试 |
| 尚未授权飞书 | 提示运行 `python main.py auth` |
| 环境未初始化 | 提示运行 `bash setup.sh` |
| 图片上传失败 | 继续创建文档，备注"X张图片未能上传" |
| API 报错 | 展示具体错误信息，建议用户检查权限 |
