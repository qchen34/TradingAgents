# X 简报（x-brief）输入文件说明

刷新接口 `POST /api/v1/x-brief/refresh` 会读取账号列表与可选简报偏好配置，并将缓存与 Markdown 汇总**写回** `data/x_brief/`。

## 文件位置

查找 **`简报配置.md`** 与 **`关注列表.md`** 时，**先** `data/x_brief/`，**再** [`docs/x资讯/`](./x资讯/)（便于与产品文档同目录维护）。同一文件名只在先找到的位置生效。

| 文件 | 作用 |
|------|------|
| `简报配置.md` | 若存在且表格中至少能解析出一行有效 `@handle`，则**优先**作为关注列表与 LLM 偏好上下文 |
| `关注列表.md` | 当未使用有效 `简报配置.md` 时**必须**存在，作为关注账号来源 |
| `data/x_brief/latest.json` 等 | 运行生成，无需手工维护 |

若仅在 `docs/x资讯/简报配置.md` 维护多表账号，**无需**再复制到 `data/x_brief/`。克隆后若无任何配置，仓库内 `data/x_brief/关注列表.md` 仍为最小占位；可按 [`data/x_brief/关注列表.example.md`](../data/x_brief/关注列表.example.md) 扩展。

## Markdown 表格格式（与历史 Claude_input 文档一致）

解析逻辑见 `web/services/x_brief_data.py` 中的 `parse_watchers_from_markdown`。

- 使用管道表：每行至少 **5 个** `|` 字符。
- 某一列单元格以 **`@`** 开头表示 X（Twitter）用户名（handle）；**下一列**为显示名称（可选）。
- 若一行有 **第 7 个**单元格（索引 6），会作为 `score` 字段读入（可选）。
- **不解析表头文字**：只要满足管道表 + `@handle` 即可；常见两种表头语义如下（任选其一风格即可）：

**关注列表风格示例：**

```markdown
| 序号 | 账号 | 名称 | 简介 | 当前分 |
|------|------|------|------|--------|
| 1 | @karpathy | Andrej Karpathy | ... | 10 |
```

**简报配置风格示例：**

```markdown
| 账号 | 名称 | 当前权重 | 偏好内容类型 | 备注 |
|------|------|----------|----------------|------|
| @OpenAI | OpenAI | 高 | 模型发布 | |
```

Handle 须为 Nitter/RSS 可用的 `[A-Za-z0-9_]+`；不符合的账号行会标记为跳过（`invalid_handle_for_nitter`）。

## 数据源与环境变量

- 推文抓取顺序由环境变量 **`X_SOURCE_PRIORITY`** 控制，默认 `nitter,snscrape,rsshub`（见 `x_brief_data._parse_source_priority`）。
- LLM 相关变量见仓库根目录 [`.env.example`](../.env.example) 中的 `XBRIEF_*` 与通用 API Key。

云端部署若无外网或 Nitter 不可用，刷新可能成功但推文为空或部分账号失败，属预期范围；需保证 **`data/x_brief/` 可写** 且存在上述输入文件之一。
