# commentmd Skill — 设计文档

日期：2026-07-01
状态：Draft（待用户批准）

## 1. 目标

给用户一个便捷的方式，把对 Agent 生成的 Markdown 文档（如"技术方案.md"）的审阅意见，以**结构化 JSON** 的形式反馈给 Agent。

用法参考 `skill-creator` 的 `eval-viewer`：一条 slash 命令拉起本地浏览器 UI，用户划词评论，提交后输出 JSON。

## 2. 用户故事

1. Agent 生成 `技术方案.md` 交给用户审阅。
2. 用户在 Qoder CLI 里输入 `/commentmd 技术方案.md`。
3. 系统本地启动一个 HTTP server，自动打开浏览器标签页。
4. 页面渲染出 md 内容。用户可用鼠标划选任意一段文字 → 弹出评论浮层 → 输入意见 → 保存。所有评论以侧栏形式列出，可编辑、可删除。
5. 用户点击「完成评论」按钮。
6. 浏览器 POST 评论到 server，server 写出 `<md名>.comments.json` 到 md 同目录，server 退出。
7. Skill 把 JSON 内容回吐给 Agent 上下文，Agent 逐条响应并修订 md。

## 3. 非目标（YAGNI）

- 不做多人协作、账号、权限。
- 不做评论线程回复。
- 不做云端存储。
- 不做增删改分类（CriticMarkup 那种），只做「评论」一种类型；用户如果想要求改成 X，写在评论内容里即可。
- 不做实时预览编辑（用户不在浏览器里改 md，只做评论）。
- 不做「接受/拒绝」流程（下游 Agent 负责响应）。

## 4. 架构

复刻 skill-creator/eval-viewer 的架构，做最小裁剪。

```
用户输入 /commentmd <path>
         │
         ▼
   scripts/serve.py <path>
         │
         ├── 读 md 文件 + 计算 sha256
         ├── 读 assets/viewer.html 模板
         ├── 把 md 文本 + 元数据注入 HTML（内联为 window.__DATA__）
         ├── 启动 http.server 于 127.0.0.1:3118
         └── webbrowser.open("http://127.0.0.1:3118")
                                │
                                ▼
                       浏览器加载 viewer.html
                                │
                       ┌────────┴──────────┐
                       │ marked 渲染 md    │
                       │ 用户划词 → 评论   │
                       │ 侧栏管理评论      │
                       └────────┬──────────┘
                                │ 用户点「完成评论」
                                ▼
                        POST /api/finish
                                │
         ┌──────────────────────┴──────────────────┐
         │ server 收到 payload                     │
         │ 写出 <md名>.comments.json 到 md 同目录  │
         │ 打印 JSON 路径到 stdout                 │
         │ shutdown server                         │
         └──────────────────────┬──────────────────┘
                                ▼
             skill 把 JSON 路径 + 内容返回给 Agent
```

## 5. 目录结构

以 skill 形式安装到 `~/.agents/skills/commentmd/`：

```
~/.agents/skills/commentmd/
├── SKILL.md            # 触发条件、用法说明（Agent 读取）
├── scripts/
│   └── serve.py        # HTTP server + 静态模式
└── assets/
    └── viewer.html     # 单文件前端（marked 内联或 CDN）
```

## 6. 组件设计

### 6.1 SKILL.md

内容要点：
- Name / description：`commentmd - 打开浏览器让用户对 Markdown 文件划词评论，返回结构化 JSON 反馈`
- 触发条件：用户显式调用 `/commentmd <path>` 或让 Agent 请人审阅 md。
- 用法示例：
  ```
  /commentmd 技术方案.md
  ```
- 内部执行：
  ```bash
  python ~/.agents/skills/commentmd/scripts/serve.py <path>
  ```
- 输出：JSON 路径 + 结构说明。
- 无浏览器环境：追加 `--static <out.html>`，用户点提交后浏览器下载 JSON，人工把 JSON 交回 Agent。

### 6.2 scripts/serve.py

**职责**：读文件、注入模板、起 server、接收提交、写 JSON、退出。

**接口**
```
python serve.py <md_path> [--port 3118] [--out <path>] [--static <html_path>] [--no-browser]
```

- `<md_path>`：待评审的 md 文件绝对/相对路径。必填。
- `--port`：默认 3118（避开 skill-creator 的 3117）。冲突时自动 +1 递增到 3128 之间找空闲端口。
- `--out`：输出 JSON 路径。默认 `<md路径去后缀>.comments.json`。
- `--static <html>`：不启 server，直接写出独立 HTML 到指定路径，提交按钮改为「下载 JSON」。
- `--no-browser`：不自动打开浏览器（用于测试或 headless）。

**依赖**：仅 Python stdlib（`http.server` / `webbrowser` / `hashlib` / `json` / `argparse` / `pathlib`）。

**端点**
- `GET /`：返回渲染后的 viewer.html。
- `POST /api/finish`：接收 `{comments: [...]}`，写 JSON，返回 `{ok: true, path: "..."}`，然后延迟 200ms 关闭 server。
- `POST /api/save`（可选）：草稿保存，行为等同 finish 但不关闭 server。用于「防丢失」。第一版可省略。

**注入数据结构（写入 window.__DATA__）**
```json
{
  "md_file": "/abs/path/技术方案.md",
  "md_name": "技术方案.md",
  "md_content": "# ...\n",
  "md_sha256": "abc123..."
}
```

### 6.3 assets/viewer.html

单文件，所有 CSS/JS 内联。

**依赖**：`marked`（Markdown → HTML）。第一版走 CDN（`https://cdn.jsdelivr.net/npm/marked/marked.min.js`）。如需完全离线，后续再把 marked 编译进 HTML。

**布局**
```
┌────────────────────────────────────────────────────┐
│ Header: 文件名 · [完成评论] 按钮 · 评论计数        │
├──────────────────────────────┬─────────────────────┤
│                              │  Comments 侧栏      │
│      Markdown 渲染区         │  ┌───────────────┐  │
│      （用户划词的目标）      │  │ 引用文本 …   │  │
│                              │  │ 评论内容 …   │  │
│                              │  │ [编辑][删除] │  │
│                              │  └───────────────┘  │
│                              │  ...                │
└──────────────────────────────┴─────────────────────┘
```

**核心交互**
1. 页面加载：`marked.parse(window.__DATA__.md_content)` 注入渲染区。
2. `mouseup` 监听：若 `window.getSelection().toString().trim().length > 0` → 在选区旁弹出「+ 评论」小按钮。
3. 点小按钮 → 展开评论输入框（textarea + 保存/取消）。
4. 保存 → 生成 comment 对象加入 `comments[]`，高亮选区，侧栏展示。
5. 点侧栏卡片 → 滚动到对应位置并闪烁高亮。
6. 编辑/删除卡片 → 更新 `comments[]` 与高亮。
7. 「完成评论」按钮 → `fetch('/api/finish', {method:'POST', body: JSON.stringify({comments})})` → 显示「已提交，可以关闭标签页」。

**选区序列化（TextQuoteSelector 简化版）**
从 `window.getSelection().getRangeAt(0)` 拿到选中文本 `exact`。用 `range.startContainer` + `range.startOffset` 结合渲染区完整 `textContent` 找到全局偏移，然后取：
- `prefix`：偏移前 32 字符
- `suffix`：偏移后 32 字符

如果 `exact` 在全文出现多次，靠 `prefix + suffix` 消歧。这三元组足够 Agent 后续用 fuzzy match 定位到修订后的原文。

**高亮实现**
不修改 DOM 树结构（避免影响后续选区计算），用一个 overlay 层根据 Range 的 `getClientRects()` 画绝对定位的半透明色块；侧栏点击时用同一个 Range 滚动。

**兜底**：若在跨块选区/复杂表格里 Range 拿不到干净的偏移，退化为「只记 exact，前后文留空，Agent 用 exact 全文搜索」。

### 6.4 输出 JSON Schema

```json
{
  "schema_version": 1,
  "md_file": "/abs/path/技术方案.md",
  "md_sha256": "abc123...",
  "created_at": "2026-07-01T10:00:00Z",
  "comment_count": 3,
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

- `id`：递增 `c1..cN`，与用户看到的顺序一致。
- `quote/prefix/suffix`：选区三元组。
- `comment`：用户输入，允许多行。
- 时间戳由前端生成（用户机器时钟），不依赖 server（server 只负责写文件）。

## 7. 数据流与失败模式

| 场景 | 行为 |
|------|------|
| 端口 3118 被占 | 递增到 3128 找空闲，还找不到就报错退出 |
| 用户直接关闭浏览器不点提交 | server 保持运行；用户可重新打开或 Ctrl+C 中止 skill；此时 JSON 不产生 |
| 用户点「完成评论」但零评论 | 仍然写 JSON（`comments: []`），Agent 视为「用户无异议」 |
| md 文件在 server 运行期间被外部修改 | 提交时 sha256 与初始不一致 → JSON 里额外加 `md_changed_during_review: true` 字段警示 Agent |
| 选区跨越渲染区外的元素（如侧栏） | 忽略该 mouseup，不弹按钮 |
| 静态模式提交 | 浏览器 `download` 一个 `<md名>.comments.json` 文件，用户告诉 Agent 文件路径 |

## 8. 测试计划

**手工**
1. 单段落纯文本 md：能划词、能评论、能提交、JSON 结构正确。
2. 多段落 + 代码块 + 列表 + 表格：所有位置都能划选。
3. 同一 quote 在文档中重复出现：JSON 里的 `prefix/suffix` 能唯一定位。
4. 零评论提交：JSON 生成成功、`comments: []`。
5. 端口冲突：自动切换到 3119。
6. `--static` 模式：HTML 独立可用，下载 JSON 内容正确。
7. `--no-browser`：手动访问 URL 也能用。

**自动化（可选）**
不做单元测试。用 Playwright 写 1 个 e2e 就够，第一版可以省略。

## 9. 里程碑

- **M1**：serve.py 骨架 + viewer.html 能渲染 md + 「完成评论」直接返回空 JSON。跑通端到端。
- **M2**：划词 + 评论浮层 + 侧栏 CRUD + 高亮 overlay。
- **M3**：选区三元组序列化 + sha256 变更检测 + 端口冲突处理。
- **M4**：`--static` 模式 + 打包 SKILL.md 挂到 `~/.agents/skills/commentmd/`。

## 10. 未来可能扩展（不在本次实现范围）

- 评论分类（question / suggestion / todo）。
- 快捷键（`c` 唤起评论框、`Enter` 保存）。
- 支持一次评审多个 md（`/commentmd file1.md file2.md`）。
- 评论持久化：即便用户不点完成，也自动 debounce 保存到临时文件。
- 把响应式改稿也放到 UI 里（分栏对比修订版）。

---

## 附：与备选方案的对比记录

| 方案 | 结果 | 原因 |
|------|------|------|
| A. Python http.server + 划词 UI | ✅ 采用 | 与 skill-creator 生态一致，交互最自然 |
| B. 段落粒度评论 | ❌ 否决 | 粒度太粗，用户想指出某句话时要靠描述 |
| C. CriticMarkup 编辑器 | ❌ 否决 | 用户已明确「编辑标记不便捷」 |
| D. Hypothesis 云服务 | ❌ 否决 | 需要账号 + 扩展 + 云端存储，重 |
