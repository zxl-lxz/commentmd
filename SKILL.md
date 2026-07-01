---
name: commentmd
description: 打开一个浏览器标签，让用户对指定 Markdown 文件划词评论，提交后返回结构化 JSON 供 Agent 阅读。用于 Agent 生成 md 后请人类审阅的场景。
---

# commentmd

## 触发时机

- 用户显式输入 `/commentmd <md_path>`。
- Agent 生成了一份 Markdown（技术方案、设计文档、README 等）并需要人类审阅意见时，主动建议使用本 skill。

## 用法

```
/commentmd <md_path>
```

参数：`<md_path>` 为待审阅 Markdown 文件的相对或绝对路径。

## Agent 执行步骤

1. 解析 `<md_path>`，转成绝对路径 `$ABS`。
2. 运行：
   ```bash
   python3 ~/.agents/skills/commentmd/scripts/serve.py "$ABS"
   ```
3. 命令会启动本地 HTTP server（127.0.0.1:3118 或下一个空闲端口），自动打开浏览器。用户在浏览器里划词评论并点击「完成评论」后，命令返回 `wrote <out_path>` 并退出。
4. 读取 `<out_path>`（默认与 md 同目录，文件名 `<md名去后缀>.comments.json`）。
5. 逐条阅读评论：`quote` 是被引用的原文片段，`prefix` / `suffix` 是前后 32 字符窗口，`comment` 是用户意见。若 `md_changed_during_review` 为 `true`，提醒用户原文已在审阅期间被外部修改。
6. 根据评论修订原文，并在回复中总结如何回应每条意见。

## 无浏览器 / 远程环境

追加 `--static /tmp/review.html`：
```bash
python3 ~/.agents/skills/commentmd/scripts/serve.py "$ABS" --static /tmp/review.html
```
用户在自己的机器上打开这个 HTML，点击「完成评论」会下载一份 JSON。Agent 需要用户告知下载文件路径后读取。

## 输出 JSON 格式

```json
{
  "schema_version": 1,
  "md_file": "/abs/path/技术方案.md",
  "md_sha256": "abc...",
  "md_changed_during_review": false,
  "created_at": "2026-07-01T10:00:00Z",
  "comment_count": 2,
  "comments": [
    {
      "id": "c1",
      "quote": "使用 MySQL 存储事件",
      "prefix": "存储层设计中，我们",
      "suffix": "，通过主从复制",
      "comment": "为什么不用 PostgreSQL？JSONB 支持更好",
      "created_at": "2026-07-01T10:00:12Z"
    }
  ]
}
```

`comment_count: 0` 表示用户无异议。
