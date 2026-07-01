# commentmd

[![test](https://github.com/zxl-lxz/commentmd/actions/workflows/test.yml/badge.svg)](https://github.com/zxl-lxz/commentmd/actions/workflows/test.yml)

在浏览器里对本地 Markdown 文件做**划词评论**，提交后生成结构化 JSON——供 AI Agent 读取并逐条响应。

![demo](./docs/demo.gif)

作为 Agent **skill** 设计：Agent 生成一份 `.md`（技术方案、设计稿、PR 描述）需要人类审阅时，触发 `commentmd`，等你写完评论后读回 JSON。

_[English README](./README.md)_

## 为什么

Agent 会生成大量 Markdown，把人的反馈精准塞回去，常见做法都有短板：

- 聊天里贴文字——丢失位置上下文。
- 用 CriticMarkup 之类的追踪标记编辑源文件——交互别扭。
- 云端标注（Hypothes.is、Google Docs）——重，需要账号。

`commentmd` 做的最少事：开一个浏览器 tab，让你划词写评论，评论写到 md 同目录的 JSON 里。除了 Python 标准库和一个 CDN 上的 `marked`，无其他依赖。

## 安装

任意目录 clone：

```bash
git clone https://github.com/zxl-lxz/commentmd.git ~/code/commentmd
```

如果你的 Agent 支持 slash command skill 约定，可选地做个 symlink：

```bash
mkdir -p ~/.agents/skills
ln -sfn ~/code/commentmd ~/.agents/skills/commentmd
```

需要 Python 3.9+。

## 用法

### 命令行

```bash
python3 scripts/serve.py path/to/方案.md
```

浏览器自动打开。划选文字 → 点「+ 评论」→ 输入 → 保存。重复。做完点「完成评论」。工具在 md 同目录写 `path/to/方案.comments.json` 后退出。

### Agent skill

如果安装到 `~/.agents/skills/commentmd/`，支持 skill 约定的 Agent 可以：

```
/commentmd path/to/方案.md
```

Agent 读回 `path/to/方案.comments.json`，逐条响应。

### 离线 / headless

不启 server，导出一份自包含 HTML：

```bash
python3 scripts/serve.py path/to/方案.md --static /tmp/review.html
```

在浏览器打开，提交时直接下载 JSON 文件。

## 输出

```json
{
  "schema_version": 1,
  "md_file": "/abs/path/方案.md",
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

每条评论带 `quote` + 32 字符 `prefix`/`suffix` 锚点，是 [W3C TextQuoteSelector](https://www.w3.org/TR/annotation-model/#text-quote-selector) 的简化版。原文即使有轻微改动，Agent 也能靠这三元组做模糊匹配定位。

`md_changed_during_review: true` 表示 server 启动后到提交前，文件被外部修改过。

## 特性

- 任意划词——段落、列表、表格单元、代码块都能选。
- 已评论文字持久淡黄高亮。
- 侧栏 sticky 满高，新评论自动滚入视窗。
- 评论增删改；删除后 id 重排为 `c1..cN`。
- sha256 对比检测审阅期间的文件变更。
- 静态 HTML 导出用于离线 / 远端。
- 运行期无第三方 Python 依赖；前端需能访问 CDN 加载 `marked`。

## CLI 参数

```
python3 scripts/serve.py <md_path> [OPTIONS]

Options:
  --port N           起始端口（默认 3118），冲突则扫描到 3128。
  --out PATH         输出 JSON 路径（默认 <md>.comments.json）。
  --static HTML      不启 server，写独立 HTML 后退出。
  --no-browser       不自动开浏览器。
```

Server 只绑 `127.0.0.1`。

## 开发

```bash
python3 -m unittest discover -s tests -v
```

14 个单元测试，纯标准库。

## 设计

架构、取舍、备选方案对比：[docs/design.md](./docs/design.md)。

## 限制

- `marked` 从 CDN 加载，`--static` 模式首次渲染仍需联网。
- `/api/finish` 靠「只绑 127.0.0.1 + `Origin` 校验」防外部调用，不适合多人共享环境。
- 前端用 DOMPurify 清洗 marked 渲染出的 HTML，避免 md 里的原生 HTML 事件处理器被触发。

## License

[MIT](./LICENSE)
