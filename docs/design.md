# commentmd 设计方案

`commentmd` 是一个通用的 AI Agent Skill：Agent 生成 Markdown 文档（技术方案、设计稿、README 等）后，通过一条 slash 命令让人类在浏览器里**划词评论**，提交后返回**结构化 JSON**，Agent 据此逐条响应并修订原文。

版本：v1.0.0  ·  最后更新：2026-07-01

## 1. 目标

- **精确定位**：评论必须锚定到具体的原文片段，而不是段落或整篇。
- **零依赖**：Skill 侧只用 Python 标准库；前端只依赖一个 CDN 上的 `marked`。
- **人机往返闭环**：一条命令拉起 UI，用户提交后自动落盘 JSON、退出服务，Agent 直接读取。

### 非目标（YAGNI）

- 不做多人协作、账号、权限、评论线程回复。
- 不做云端存储；所有数据落在本地文件。
- 不做增删改类型区分（如 CriticMarkup）——只有「评论」一种，用户要「改成 X」就写在评论正文里。
- 不在浏览器里编辑原文。
- 不做「接受 / 拒绝」流程；下游 Agent 自行响应评论。

## 2. 用户流程

1. Agent 或用户输入 `/commentmd 技术方案.md`。
2. Skill 启动本地 HTTP server（`127.0.0.1:3118`，冲突时向上扫描到 3128），并自动打开浏览器标签页。
3. 页面渲染 Markdown。用户任意划选文字 → 弹出「+ 评论」浮层 → 输入意见 → 保存。评论沉淀到右侧固定侧栏，原文对应位置持久高亮。
4. 用户点「完成评论」按钮。浏览器 `POST /api/finish`，服务端写出 `<md名>.comments.json` 到 md 同目录，200ms 后 shutdown。
5. 弹出成功 modal，用户可关闭标签或保留标签。
6. Agent 读回 JSON，按 `quote` / `prefix` / `suffix` 三元组定位原文，逐条响应。

## 3. 架构

```
用户输入 /commentmd <path>
         │
         ▼
   scripts/serve.py <path>
         │
         ├── 读 md 文件，计算 sha256（initial）
         ├── 读 assets/viewer.html 模板
         ├── 把 md 文本 + 元数据注入 HTML（写到 window.__DATA__）
         ├── 启动 http.server 于 127.0.0.1:<port>
         └── webbrowser.open("http://127.0.0.1:<port>")
                                │
                                ▼
                       浏览器加载 viewer.html
                                │
                       ┌────────┴──────────┐
                       │ marked 渲染 md    │
                       │ 用户划词 → 评论   │
                       │ 侧栏管理 + 高亮   │
                       └────────┬──────────┘
                                │ 用户点「完成评论」
                                ▼
                        POST /api/finish
                                │
         ┌──────────────────────┴──────────────────┐
         │ server 再次 sha256(md_path) → current   │
         │ 组装 schema_version=1 的 JSON            │
         │ 写出 <md名>.comments.json 到 md 同目录  │
         │ 打印路径到 stdout                        │
         │ 200ms 后 shutdown                        │
         └──────────────────────┬──────────────────┘
                                ▼
             skill 把 JSON 路径 + 内容交给 Agent
```

### 目录

```
commentmd/
├── skills/
│   └── commentmd/             # 供 `npx skills add` 抓取的完整 skill 目录
│       ├── SKILL.md           # Skill 清单，供支持该约定的 Agent 运行时发现
│       ├── scripts/
│       │   └── serve.py       # HTTP server + 静态导出模式
│       └── assets/
│           └── viewer.html    # 单文件前端
├── tests/
│   ├── fixtures/sample.md
│   └── test_helpers.py        # 纯函数单元测试
└── docs/
    └── design.md              # 本文件
```

安装到 `~/.agents/skills/commentmd/`（推荐 `npx skills add`，或手动 `ln -sfn ~/code/commentmd/skills/commentmd ~/.agents/skills/commentmd` 便于开发）。

## 4. 服务端（`scripts/serve.py`）

### 命令行

```
python3 serve.py <md_path> [--port 3118] [--out PATH] [--static HTML] [--no-browser]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<md_path>` | 必填 | 待评审的 md 文件路径 |
| `--port` | `3118` | 起始端口；被占则扫到 `3128`；全占则退出 1 |
| `--out` | `<md>.comments.json` | 输出 JSON 路径，与 md 同目录同名不同后缀 |
| `--static` | — | 不启 server，写一份自包含 HTML；提交按钮改为「下载 JSON」 |
| `--no-browser` | — | 不自动开浏览器（测试 / headless 用） |

**依赖**：仅 Python stdlib（`http.server` / `webbrowser` / `hashlib` / `json` / `argparse` / `pathlib` / `socket` / `datetime`）。

### 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| `GET` | `/`、`/index.html` | 返回已注入 `window.__DATA__` 的 viewer.html |
| `POST` | `/api/finish` | 接收 `{comments, md_file, md_sha256}`；服务端**重新计算** md 的 sha256，与启动时对比，写出 JSON；200ms 后 shutdown。Body 非合法 JSON → 400；未知路径 → 404 |

### 注入到浏览器的元数据

服务端在渲染 viewer.html 时把如下对象注入 `window.__DATA__`：

```json
{
  "md_file": "/abs/path/技术方案.md",
  "md_name": "技术方案.md",
  "md_content": "# ...\n",
  "md_sha256": "abc..."
}
```

同时注入 `window.__MODE__`，值为 `"server"` 或 `"static"`。

### 关键实现要点

- **端口扫描**：从 `--port` 起 `socket.bind()` 探测，找到第一个能绑上的端口。
- **文件变更检测**：服务端在启动时算一次 `md_sha256`（initial），在收到 `/api/finish` 时**再算一次**（current），两者不等则 JSON 里置 `md_changed_during_review: true`。**不能**信任浏览器回传的 sha——浏览器只会原样回吐启动时收到的值。
- **XSS 防线**：`inject_template` 把注入到 `<script>` 里的 JSON payload 中的 `</` 替换成 `<\/`，避免 md 内容里的 `</script>` 提前闭合注入块。测试通过「不包含未转义 `</script>`」验证。
- **Shutdown 延迟**：写完 JSON 后先把响应 flush 给浏览器，再在守护线程里 `time.sleep(0.2)` 后 `server.shutdown()`，确保客户端收到 200。

## 5. 前端（`assets/viewer.html`）

单文件，所有 CSS/JS 内联，从 CDN 加载两个依赖：`marked`（Markdown → HTML）和 `DOMPurify`（清洗 HTML 中的可执行属性）。

### 布局

```
┌──────────────────────────────────────────────────────┐
│ Header (sticky top): 文件名 · N 条评论 · [完成评论]  │
├──────────────────────────────┬───────────────────────┤
│                              │ 侧栏 (sticky)          │
│   Markdown 渲染区            │ ┌───────────────────┐ │
│   ├─ 已评论文字持久高亮      │ │ 引用片段…         │ │
│   └─ 划词时弹「+ 评论」按钮  │ │ 评论正文…         │ │
│                              │ │ [编辑] [删除]     │ │
│                              │ └───────────────────┘ │
│                              │ ...                   │
└──────────────────────────────┴───────────────────────┘
```

- **侧栏**：`position: sticky; top: 53px; height: calc(100vh - 53px)`——正文再长，侧栏永远铺满视口。加评论后新卡片自动 `scrollIntoView`。
- **高亮 overlay**：`#app` 内挂一个 `#highlights` 容器，`pointer-events: none`；每次评论增删触发 `renderHighlights()`，用 `findQuoteRange` + `getClientRects()` 画淡黄色块。不修改 DOM 树结构，避免影响后续选区计算。`window.resize` 用 rAF 节流重绘。
- **提交后模态框**：两个按钮「保留标签」「关闭标签」；关闭走 `window.close()`，失败降级为「请手动关闭」。

### 选区序列化（TextQuoteSelector 简化版）

对 `window.getSelection().getRangeAt(0)`：

1. `exact = range.toString()`——**必须用 Range 版本**而非 `Selection.toString()`，因为后者对表格选区会插入 `\t` 和额外的 `\n`，与 `app.textContent` 对不上，导致 `findQuoteRange` 定位失败、高亮画不出来。
2. `prefix`：`textContent` 里选区起点前 32 字符。
3. `suffix`：选区终点后 32 字符。

三元组足够让 Agent 在原文有轻微修改后用 fuzzy match 重定位。

### 划词交互

- `mouseup` 检测选区完全落在 `#app` 内（`app.contains(range.startContainer) && app.contains(range.endContainer)`），否则忽略。
- 起浮动按钮，用 `getClientRects()` 定位到选区末尾右下方。
- 点按钮开评论 popover：textarea + 保存 / 取消；保存时空文本被拒绝。
- 保存后：分配 `id = "c<N>"`，`state.comments` 递增；触发侧栏 render、highlights render、`scrollSidebarTo`。

### id 管理

- 新增：`state.nextId` 自增，`c1, c2, c3, ...`。
- 删除：**重新压缩** id 使剩余评论仍是连续的 `c1..cN`（保持数组顺序），`nextId = N + 1`。这样提交出去的 JSON 里不会出现 `c1, c3, c7` 这种跳号。

## 6. 输出 JSON

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

- `schema_version`：向后兼容锚点。
- `md_sha256`：服务端启动时的初始哈希。
- `md_changed_during_review`：服务端在提交时重算的哈希与初始不等时为 `true`。
- `created_at`（顶层）：JSON 落盘时间，UTC ISO 8601 带 `Z`。
- `comments[].created_at`：浏览器 `Date.now()` 时间，可能带毫秒。
- `comment_count: 0` 是合法状态，表示「用户无异议」。

## 7. 失败模式

| 场景 | 行为 |
|------|------|
| 端口 3118 被占 | 递增扫描到 3128，取第一个空闲端口；全占则 `error: no free port`，退出 1 |
| md 文件不存在 | `error: not a file`，退出 1 |
| 用户直接关浏览器不提交 | Server 继续跑；用户可重开浏览器或 Ctrl+C 中止（退出 130） |
| 用户零评论提交 | 写 `{"comment_count": 0, "comments": []}`，Agent 视为「无异议」 |
| md 文件在审阅期间被外部修改 | 提交时 `md_changed_during_review: true`，Agent 需自行判断如何合并 |
| 划选跨越渲染区外的元素（如侧栏） | 忽略该 mouseup，不弹按钮 |
| POST body 非合法 JSON | 400，server 保持运行 |
| POST `Origin` 缺失或不匹配 | 403，server 保持运行 |
| POST `Content-Type` 非 `application/json` | 415，server 保持运行 |
| POST body > 1 MiB | 413，server 保持运行 |
| 静态模式提交 | 浏览器下载 `<md名>.comments.json`，用户告知 Agent 文件路径 |

## 8. 安全边界

`commentmd` 假设运行在**单机、单用户**的开发者机器上。默认威胁模型：

**已防御**

- **CSRF / DNS rebinding**：`/api/finish` 校验请求头 `Origin` 必须等于本次运行的 `http://127.0.0.1:<port>`；DNS rebinding 攻击虽能改 Host，改不了 Origin。
- **简单跨源 POST 绕过预检**：`Content-Type` 必须是 `application/json`，从而强制触发 CORS 预检；`text/plain` 和 `application/x-www-form-urlencoded` 的简单请求会被拒。
- **Markdown 里的 HTML 事件处理器**：前端在把 `marked` 渲染结果塞进 `innerHTML` 之前，先过 `DOMPurify.sanitize` 去掉所有可执行属性。
- **注入 `<script>` breakout**：`inject_template` 把注入到 `<script>` 里的 JSON payload 中的 `</` 替换成 `<\/`，md 里的 `</script>` 不能提前闭合注入块。
- **客户端伪造 `md_file`**：输出 JSON 里的 `md_file` 由服务端上下文写入，忽略客户端 payload；单元测试 `test_ignores_client_supplied_md_file` 覆盖此路径。
- **POST body 泛洪**：body 上限 1 MiB，超限 413。

**未防御 / 假设不成立时的风险**

- 多用户共享机器：其他本机用户可以直接访问 `127.0.0.1:<port>`。
- 用户在审阅期间从命令行主动 `curl` 攻击性 payload。这些访问自带正确 `Origin` 也能通过校验。
- DOMPurify 或 marked 自身的 0-day。

## 9. 已知限制

- `--static` 模式仍从 CDN 加载 marked + DOMPurify，离线首次渲染需联网。要真正离线需把两者内联进 HTML。
- 「编辑」按钮用浏览器 `prompt()`，多行评论会被压成一行。应改为跟「新增」相同的 popover。
- 浏览器阻止 `window.close()` 时只能提示手动关，无法自动关 tab。
- `scripts/serve.py` 里 `import` 语句是随着任务追加时散布在文件中间的，不符合 PEP 8。收敛到顶部即可。

## 10. 测试策略

**单元测试**（`tests/test_helpers.py`，`python3 -m unittest discover -s tests -v`）

覆盖所有纯函数 helper：`compute_sha256`、`find_free_port`（含忙碌端口跳过、全占抛错）、`build_page_data`、`resolve_output_path`、`inject_template`（含 `</script>` 转义验证）、`write_output_json`（含 sha 匹配、sha 不匹配、真实文件被修改、客户端伪造 md_file 被忽略四个场景）、`write_static_html`。当前 15/15 通过。

**手工冒烟**

- 单段落 md：划词、评论、提交、JSON 结构。
- 富格式 md：代码块、列表、表格、blockquote 都能划选和高亮。
- 同 quote 重复出现：`prefix + suffix` 消歧。
- 零评论提交：JSON 生成成功。
- 端口冲突：自动切换到 3119。
- `--static` 模式：HTML 独立可用，下载 JSON 内容正确。
- 文件在审阅期间被修改：`md_changed_during_review: true`。
- 跨源 POST 被拒（curl 带错误 Origin → 403；缺 Origin → 403；错误 Content-Type → 415）。

## 11. 备选方案

选型阶段考虑过的其他做法：

| 方案 | 结论 | 原因 |
|------|------|------|
| A. Python http.server + 划词 UI | 采用 | 与 skill-creator 生态一致；交互最接近 Google Docs 批注，用户零学习成本 |
| B. 段落粒度评论 | 否决 | 只能对整段评论，用户想指出某句话时要靠描述，粒度太粗 |
| C. CriticMarkup 编辑器 | 否决 | 用户要在源码里插 `{>>...<<}` 标记，交互不「便捷」，用户已明确反对 |
| D. Hypothesis 云服务 | 否决 | 需要账号 + 浏览器扩展 + 云端存储，重且离线不可用 |
| E. 语雀 / 钉钉文档评论 | 否决 | 依赖外部平台账号 + 网络；把本地 md 上传下载一遍成本远超收益 |
