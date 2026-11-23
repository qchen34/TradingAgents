# TradingAgents Vercel 部署手册（前端 + API 对接）

本文档整理当前项目在 Vercel 上线所需的完整配置，覆盖：

- Vercel 项目创建与构建配置
- 前端环境变量（尤其 API 配置）
- 后端部署与联通检查
- 常见报错与排障流程

适用仓库结构：

- 前端：`frontend`（Next.js）
- 后端：`backend`（FastAPI）
- 共享业务：`web/services` 等（由 FastAPI 导入）

### 仓库根目录 Python 依赖（自建后端时用）

在服务器/容器内从**仓库根目录**安装核心依赖（与 `pyproject.toml` 一致）：

```bash
pip install -r requirements.txt
# 等价：pip install -e .
```

---

## 1. 架构说明（建议）

当前项目推荐采用“前后端分离”部署：

1. **Vercel 仅部署 Next.js 前端**（目录 `frontend`）
2. **FastAPI 后端独立部署**（Render/Railway/Fly.io/云主机均可）
3. 前端通过 `NEXT_PUBLIC_API_BASE` 调用后端 API

原因：

- 当前后端包含 Python 依赖、文件读写和长任务，更适合常驻服务
- Vercel 适合静态与 Serverless 前端，不适合当前后端形态直接搬迁

---

## 2. Vercel 前端部署（必须项）

### 2.1 创建项目

在 Vercel 中导入本仓库后，关键配置如下：

- **Framework Preset**: `Next.js`
- **Root Directory**: `frontend`
- **Install Command**: `npm ci`
- **Build Command**: `npm run build`
- **Output Directory**: 留空（使用 Next.js 默认）

> `Root Directory` 必须是 `frontend`，否则会出现 `Missing script: "build"`。

### 2.2 必配环境变量

在 Vercel -> Project -> Settings -> Environment Variables 中添加：

```bash
NEXT_PUBLIC_API_BASE=https://your-backend-api.example.com
```

说明：

- 值必须是**完整后端域名**（协议 + 域名）
- 不要以 `/` 结尾（避免路径拼接出现双斜杠）
- 前端构建时/运行时都会读取该变量

---

## 3. 后端 API 部署要求（必须项）

前端依赖以下后端接口（示例）：

- `GET /health`
- `GET /api/v1/dashboard`
- `POST /api/v1/dashboard/refresh`
- `POST /api/v1/quotes/batch`
- `GET /api/v1/x-brief/latest`
- `POST /api/v1/x-brief/refresh`
- `POST /api/v1/strategy/lrs/chat`
- `GET /api/v1/wheel/profiles`
- `POST /api/v1/wheel/evaluate`
- `GET /api/v1/backtest/periods`
- `POST /api/v1/backtest/jobs`
- `GET /api/v1/backtest/jobs/{job_id}`

本地启动命令（用于联调）：

```bash
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

若后端部署到公网，至少保证：

- `https://your-backend-api.example.com/health` 可访问
- 返回 `{"success":true,...}` 或可识别健康响应
- API 服务具备稳定的 Python 运行环境与依赖

### 3.1 X 资讯简报（`x-brief`）

刷新依赖仓库内可写目录 **`data/x_brief/`**（输出与缓存），以及**可读**的账号来源：优先 **`data/x_brief/`** 下的 `简报配置.md` / `关注列表.md`，若无则回退到 **`docs/x资讯/`** 下同文件名（与产品文档一并维护）。格式见 **[docs/x_brief.md](./x_brief.md)**。

---

## 4. CORS 与安全建议

当前代码中 CORS 为 `allow_origins=["*"]`，便于开发联调，但生产建议收敛为前端域名白名单。

建议生产配置：

- 仅允许你的 Vercel 域名（例如 `https://xxx.vercel.app`）
- 如有自定义域名，也加入白名单

---

## 5. 部署前检查清单（Checklist）

发布前逐项确认：

1. [ ] `frontend` 下 `npm run build` 本地可通过  
2. [ ] Vercel 项目 `Root Directory=frontend`  
3. [ ] Vercel 已配置 `NEXT_PUBLIC_API_BASE`  
4. [ ] 后端公网地址可访问 `/health`  
5. [ ] 后端证书有效（HTTPS）  
6. [ ] 前端访问页面后，Network 中 API 请求指向公网后端而非 `127.0.0.1`

---

## 6. 常见报错与处理

### 6.1 `Missing script: "build"`

原因：Vercel 在仓库根目录构建，而不是 `frontend`。  
处理：将 Root Directory 改为 `frontend`，重新部署。

### 6.2 页面加载后 API 全部失败

常见原因：

- 未配置 `NEXT_PUBLIC_API_BASE`
- 配置成了本地地址（如 `http://127.0.0.1:8000`）
- 后端未部署或域名不可达

处理：

1. 检查 Vercel 环境变量
2. 打开浏览器 Network，确认请求域名
3. 手工访问后端 `/health`

### 6.3 `CORS` 报错

原因：后端未放行当前前端域名。  
处理：在 FastAPI CORS 配置中加入对应前端域名。

### 6.4 Vercel 部署成功但页面异常

排查顺序：

1. Vercel Deploy Logs（构建阶段）
2. Browser Console（前端运行时）
3. Browser Network（API 请求）
4. 后端服务日志（FastAPI）

---

## 7. 推荐部署流程（一次到位）

1. 先部署后端，拿到公网 URL（确认 `/health`）
2. 再部署 Vercel 前端，并设置 `NEXT_PUBLIC_API_BASE`
3. 前端上线后逐页验证：
   - Dashboard
   - X Brief
   - Strategy / Wheel
   - Backtesting
4. 观察后端日志，确认接口调用正常

---

## 8. 可选增强项

- 增加 `frontend/.env.example`（仅包含 `NEXT_PUBLIC_API_BASE=`）
- 在 Vercel 设置 Preview/Production 分环境 API 地址
- 在后端增加 `/health/details`（依赖检查）
- 在前端增加启动时 API 连通性提示页

