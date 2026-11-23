# X AI Builder 发现板 · 产品文档 v3.0

> **最后更新**：2026-05-01
> **变更记录**：v3.0 产品方向重写 — 从关注列表日报 → AI builder 项目发现板
> **定位**：主动发现 X 上 AI 开发者正在构建的项目，服务于 B 站内容选题 + 个人学习 + 工具跟踪
> **目标体验**：每次刷新后，在 5 分钟内浏览完最近值得关注的 AI builder 项目，知道谁在做什么、效果怎样、代码在哪里

---

## 一、架构总览

```
[数据采集层]  ← X API（必须，提供 engagement + media）
  ├── 通道 A · 关键词搜索（主力）
  │     搜索词：AI project demo / built with Claude / vibe coding / etc.
  ├── 通道 B · 媒体筛选（视频优先）
  │     filter:videos + AI keywords → 优先找有演示视频的帖子
  └── 通道 C · 趋势扩展
        trending AI keywords → 扩充搜索词池
         │
         ▼ raw post JSON（标准化格式，见 §3）
[L1 · 结构提取层]  ← quick LLM（速度优先）
         │  从帖子正文提取：GitHub 链接 / 项目名 / 技术栈 / 是否有 demo
         ▼ enriched post JSON
[L2 · 项目卡片层]  ← thinking LLM（质量优先）
         │  去重 + 评分 + 生成项目摘要 + 分类打标
         ▼ project_cards JSON（标准 Schema，见 §4）
[L3 · 翻译层]  ← quick LLM（速度优先）
         │  英译中（项目描述、摘要），结构不变
         ▼ translated project_cards JSON
[Next.js 前端]
         │  消费 JSON → 渲染项目发现板
         ▼
[用户浏览]  →  (未来) 收藏 / 标记"已看" → 影响下次推送权重
```

---

## 二、数据采集：为什么必须用 X API

### 2.1 能力对比

| 能力 | Nitter RSS | xint | X API v2 |
|------|-----------|------|----------|
| 帖子正文 | ✅（可能截断） | ✅ 全文 | ✅ 全文 |
| 发布时间 | ✅ | ✅ | ✅ |
| 视频 URL | ❌ | ⚠️ 部分 | ✅ 完整 media |
| 视频缩略图 | ❌ | ❌ | ✅ |
| 点赞数 | ❌ | ❌ | ✅ |
| 转发数 | ❌ | ❌ | ✅ |
| 播放量 | ❌ | ❌ | ✅ |
| 关键词搜索 | ❌ | ✅ | ✅ |
| filter:videos | ❌ | ⚠️ | ✅ |

**结论**：点赞数 + 视频 URL 是本产品核心数据，**只有 X API 能提供**。

### 2.2 X API 接入方案

```bash
# 所需权限：Basic 访问级别（$100/月）或开发者免费额度
# 端点：GET /2/tweets/search/recent  +  media.fields  +  public_metrics

# 环境变量
X_BEARER_TOKEN=xxx   # 所有搜索请求用 Bearer Token，无需用户授权
```

### 2.3 搜索词策略（通道 A + B 核心）

```python
# 分组搜索词，每组每次执行
SEARCH_QUERIES = {
    "builder_demo": [
        "built with AI demo",
        "I built this with Claude",
        "vibe coding project",
        "AI agent demo",
        "open source AI tool",
    ],
    "video_first": [
        # filter:videos 确保帖子含视频
        "AI project demo filter:videos -is:retweet",
        "built with LLM filter:videos -is:retweet",
        "AI app filter:videos lang:en -is:retweet",
    ],
    "platform_specific": [
        "Claude Code project",
        "Cursor built",
        "v0 demo shipped",
        "Windsurf project",
    ],
    "github_signal": [
        "github.com AI project",
        "open sourced AI",
        "just released AI repo",
    ],
}

# 通用过滤参数
COMMON_PARAMS = {
    "min_faves": 50,       # 过滤低质量帖子
    "result_type": "recent",
    "max_results": 100,    # 每次搜索上限
    "since": "24h",        # 时间窗口（可配置）
}
```

### 2.4 数据采集脚本入口（backend）

```python
# web/services/x_builder_data.py
def collect_builder_posts(
    time_window_hours: int = 48,
    min_likes: int = 50,
    video_only: bool = False,
) -> dict:
    """
    返回 raw payload，结构见 §3
    """
    ...
```

---

## 三、采集层输出格式（传入 L1）

```json
{
  "fetch_time": "2026-05-01T11:00:00+08:00",
  "query_stats": {
    "total_queries": 12,
    "total_fetched": 234,
    "time_window_hours": 48
  },
  "posts": [
    {
      "post_id": "1917834251234567890",
      "url": "https://x.com/levelsio/status/1917834251234567890",
      "author": {
        "handle": "levelsio",
        "display_name": "Pieter Levels",
        "followers": 524000,
        "verified": false
      },
      "text": "I built a real-time flight tracker using Claude Code + MapLibre. Full source on GitHub 👇\ngithub.com/levelsio/flightai",
      "published_at": "2026-04-30T09:14:22+00:00",
      "metrics": {
        "likes": 2341,
        "reposts": 456,
        "replies": 89,
        "views": 187000,
        "bookmarks": 312
      },
      "media": [
        {
          "type": "video",
          "url": "https://video.twimg.com/ext_tw_video/.../video.mp4",
          "thumbnail_url": "https://pbs.twimg.com/ext_tw_video_thumb/.../img/thumbnail.jpg",
          "duration_ms": 45000
        }
      ],
      "urls_in_text": [
        "https://github.com/levelsio/flightai"
      ],
      "search_query_matched": "built with Claude",
      "is_retweet": false,
      "is_reply": false
    }
  ]
}
```

---

## 四、L1 结构提取（quick LLM）

L1 的任务是**从每条帖子正文中提取结构化字段**，不做筛选和摘要。

### 4.1 每条帖子的提取目标

```json
{
  "post_id": "1917834251234567890",
  "has_demo": true,
  "project_name": "FlightAI",
  "github_url": "https://github.com/levelsio/flightai",
  "tech_stack": ["Claude Code", "MapLibre", "Python"],
  "category": "data_tool",
  "is_genuine_build": true,
  "extraction_confidence": "high"
}
```

### 4.2 category 枚举

| 值 | 说明 |
|----|------|
| `ai_agent` | 自主 agent / 多步骤任务执行 |
| `coding_tool` | 辅助开发 / 代码生成工具 |
| `data_tool` | 数据处理 / 可视化 / 分析工具 |
| `creative_ai` | 图像 / 音频 / 视频生成类 |
| `chatbot_app` | 对话应用 / 知识库问答 |
| `infra_tool` | AI 基础设施 / 部署 / 监控 |
| `game` | AI 游戏 / 互动体验 |
| `other` | 其他 |

### 4.3 `is_genuine_build` 判断规则

L1 标记以下情况为 `false`（后续 L2 直接丢弃）：
- 纯转推 / 纯评论（无实质内容）
- 广告 / 招聘帖
- 只是分享新闻，无自己构建的内容
- 低质水帖（无具体项目描述）

---

## 五、L2 项目卡片层（thinking LLM）

L2 将 L1 enriched posts 聚合为**可渲染的项目卡片**。

### 5.1 L2 输出 Schema（前端直接消费）

```json
{
  "meta": {
    "generated_at": "2026-05-01T12:00:00+08:00",
    "time_window_hours": 48,
    "posts_fetched": 234,
    "projects_extracted": 38,
    "with_video": 22,
    "with_github": 29
  },
  "headline": "今日发现 38 个 AI builder 项目，vibe coding 热度持续，agent 工具占比最高",
  "trending_keywords": ["vibe coding", "Claude Code", "AI agent", "open source"],
  "project_cards": [
    {
      "id": "proj_001",
      "rank": 1,
      "project_name": "FlightAI",
      "project_name_zh": "AI 实时航班追踪",
      "author": {
        "handle": "levelsio",
        "display_name": "Pieter Levels",
        "followers": 524000
      },
      "category": "data_tool",
      "category_label": "数据工具",
      "summary": "用 Claude Code + MapLibre 构建的实时航班追踪可视化工具，开源",
      "why_interesting": "levelsio 的 vibe coding 演示，展示了 Claude Code 在地理可视化项目中的完整工作流",
      "tech_stack": ["Claude Code", "MapLibre", "Python"],
      "github_url": "https://github.com/levelsio/flightai",
      "demo_video": {
        "url": "https://video.twimg.com/ext_tw_video/.../video.mp4",
        "thumbnail_url": "https://pbs.twimg.com/ext_tw_video_thumb/.../img/thumbnail.jpg",
        "duration_s": 45
      },
      "post": {
        "url": "https://x.com/levelsio/status/1917834251234567890",
        "text": "I built a real-time flight tracker using Claude Code + MapLibre...",
        "text_zh": "我用 Claude Code + MapLibre 构建了一个实时航班追踪器...",
        "published_at": "2026-04-30T09:14:22+00:00",
        "likes": 2341,
        "views": 187000,
        "bookmarks": 312
      },
      "quality_score": 9
    }
  ],
  "category_summary": [
    { "category": "ai_agent", "label": "AI Agent", "count": 12 },
    { "category": "coding_tool", "label": "编程工具", "count": 9 },
    { "category": "data_tool", "label": "数据工具", "count": 7 }
  ]
}
```

### 5.2 quality_score 评分规则（1-10）

| 维度 | 权重 | 说明 |
|------|------|------|
| 点赞数 | 30% | 1000+ → 满分；<100 → 低分 |
| 有视频 demo | 20% | 有 +2 分 |
| 有 GitHub | 20% | 有 +2 分 |
| 作者粉丝量 | 15% | 10万+ → 加分 |
| 技术栈清晰度 | 15% | LLM 判断项目描述是否具体 |

前端默认按 `quality_score` 降序排列，用户可切换为"最新"。

---

## 六、前端规格（Next.js）

### 6.1 CSS 变量（继承现有深色主题）

```css
:root {
  /* 继承 v2.1 全部变量，新增 */
  --video-badge: rgba(239,68,68,0.15);
  --video-badge-text: #fca5a5;
  --github-badge: rgba(34,197,94,0.12);
  --github-badge-text: #86efac;
  --likes-color: #f472b6;
  --views-color: #94a3b8;
}
```

### 6.2 页面整体结构

```
<BuilderDiscoveryPage>
  ├── <Header>
  │     ├── 标题："AI Builder 发现" + 日期范围
  │     ├── headline（LLM 生成的一句话总结）
  │     └── StatsBar：采集 N 条 · 项目 N 个 · 有视频 N · 有 GitHub N
  ├── <TrendingBar>        ← 热词 chip 列表（来自 trending_keywords）
  ├── <FilterBar>          ← 分类筛选 + 排序切换
  │     ├── 分类 tabs：全部 / AI Agent / 编程工具 / 数据工具 / 创意 AI / ...
  │     ├── 筛选开关：[仅有视频] [仅有 GitHub]
  │     └── 排序：热度优先 / 最新优先
  ├── <ProjectCardGrid>    ← 响应式卡片网格
  │     └── <ProjectCard × N>
  └── <Footer>             ← 数据来源说明 + 刷新按钮
```

### 6.3 ProjectCard 组件规格

```
┌──────────────────────────────────────────────────────┐
│  [▶ 视频]  缩略图（点击播放/跳转）            [AI Agent] │
│                                                       │
│  FlightAI                                             │  ← 项目名（大）
│  AI 实时航班追踪可视化工具                              │  ← 一句话描述
│                                                       │
│  @levelsio · 524K followers                           │  ← 作者行
│  Claude Code  MapLibre  Python                        │  ← 技术栈 chip
│                                                       │
│  ❤️ 2,341   👁 187K   🔖 312                           │  ← engagement
│                                                       │
│  [▶ 查看视频]  [GitHub ↗]  [原帖 ↗]                    │  ← 操作行
└──────────────────────────────────────────────────────┘
```

**字段映射**：

| 数据字段 | UI 位置 | 缺失时 |
|---------|---------|--------|
| `demo_video.thumbnail_url` | 卡片顶部封面图 | 显示灰色占位符 |
| `demo_video.url` | 点击封面 → 新标签页 | 隐藏封面区 |
| `project_name_zh` | 卡片标题 | fallback 到 `project_name` |
| `summary` | 副标题 | 截断 `post.text_zh` 前 60 字 |
| `author.handle` + `followers` | 作者行 | — |
| `tech_stack[]` | chip 列表（最多 4 个） | 不显示 |
| `post.likes` | ❤️ 数字 | "—" |
| `post.views` | 👁 数字 | 隐藏 |
| `github_url` | [GitHub ↗] 按钮 | 按钮隐藏 |
| `post.url` | [原帖 ↗] 按钮 | 总显示 |
| `category_label` | 右上角 badge | "其他" |

**展开态**（点击卡片 body 展开）：

```
┌──────────────────────────────────────────────────────┐
│  ... 折叠态内容 ...                                    │
│  ──────────── 原帖内容 ────────────                   │
│  I built a real-time flight tracker using             │  ← 原文
│  Claude Code + MapLibre. Full source...               │
│                                                       │
│  [翻译] 我用 Claude Code + MapLibre 构建了...          │  ← 中文译文
│                                                       │
│  💡 why interesting:                                  │
│  levelsio 的 vibe coding 演示，展示了 Claude Code...   │  ← LLM 洞见
└──────────────────────────────────────────────────────┘
```

### 6.4 FilterBar 行为规范

- 分类 tab 切换：前端过滤（不重新请求）
- "仅有视频"：`demo_video != null`
- "仅有 GitHub"：`github_url != null`
- 排序切换：`quality_score` desc（默认）↔ `post.published_at` desc

---

## 七、后端 API 设计

### 7.1 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/builder/latest` | 读取最近一次结果（缓存） |
| `POST` | `/api/v1/builder/refresh` | 触发全流程刷新 |
| `GET` | `/api/v1/builder/categories` | 返回本次分类统计 |

### 7.2 刷新请求 Body

```json
{
  "time_window_hours": 48,
  "min_likes": 50,
  "video_only": false,
  "max_results_per_query": 100
}
```

### 7.3 环境变量

```bash
# .env（新增）
X_BEARER_TOKEN=xxx            # X API Bearer Token，必须
X_MIN_LIKES=50                # 全局最低点赞阈值
X_TIME_WINDOW_HOURS=48        # 搜索时间窗口

# 继承 v2.1
XBRIEF_ORCHESTRATOR_PROVIDER=siliconflow
XBRIEF_ORCHESTRATOR_MODEL=Pro/MiniMaxAI/MiniMax-M2.5
XBRIEF_ORCHESTRATOR_BASE_URL=https://api.siliconflow.cn/v1
```

---

## 八、迁移说明（v2 → v3）

| 组件 | v2 状态 | v3 处理 |
|------|---------|---------|
| `x_brief_data.py`（RSS 采集） | 保留 | 新建 `x_builder_data.py` 替代，旧文件不删（备用） |
| `x_brief_llm.py`（L1+L2） | 保留 | 新建 `x_builder_llm.py`，两套 LLM 逻辑独立 |
| `x_brief_renderer.py` | 保留 | 新建 `x_builder_renderer.py` |
| `/api/v1/x-brief/*` | 保留 | 新增 `/api/v1/builder/*`，旧端点不删 |
| `frontend/x-brief/page.tsx` | 保留 | 新建 `frontend/builder/page.tsx` |
| `简报配置.md`（关注列表） | 保留 | 不再作为主要数据源，仅备用 |

> 新旧两套并行，互不影响，可随时回退。

---

## 九、已知约束与风险

| 问题 | 说明 | 缓解方案 |
|------|------|---------|
| X API 费用 | Basic $100/月，免费额度仅 1500 requests/月 | 批量聚合查询，控制频率 |
| 视频直链有效期 | twimg.com 视频直链可能几小时后失效 | 前端直接链接到原帖，不缓存视频 |
| GitHub 链接提取率 | 帖子正文可能用 t.co 短链，L1 需展开 | 采集层展开所有 t.co 链接 |
| 重复项目 | 同一项目可能被多个帖子提及 | L2 用 github_url 去重；无 GitHub 时用项目名去重 |
| 英文 bias | 搜索词以英文为主 | 可增加中文搜索词组 |

---

## 十、后续迭代方向

1. **视频本地存储**：定时将 twimg 视频下载到本地，避免链接失效
2. **作者画像**：积累 builder 信息（擅长方向、历史项目），丰富推荐上下文
3. **GitHub Stars 追踪**：定期查询 GitHub API，追踪项目热度变化
4. **用户收藏**：前端支持"收藏项目"，写入本地 JSON
5. **搜索词自进化**：L2 每次运行后建议新搜索词，人工确认后加入配置
