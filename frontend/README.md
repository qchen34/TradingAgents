# TradingAgents Frontend

Next.js（App Router）+ TypeScript，对接仓库根目录的 FastAPI（`backend/`）。

## 本地启动

```bash
npm ci
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev
```

若在开发中刷新页面出现 `__webpack_modules__[moduleId] is not a function` 或 `Cannot find module './331.js'`：

1. 一条命令处理（**先**释放 3000 端口，**再**删 `.next`，**再**启动）：`npm run dev:clean`
2. 若提示 `EADDRINUSE`：说明还有旧 `next dev` 未退出；在跑前端的终端 Ctrl+C，或再执行一次 `npm run dev:clean`
3. 不要在 dev 进程仍运行时执行 `npm run build`（会污染 `.next`）

顺序要点：**不要**在旧 dev 还在跑时只删 `.next`——那样更容易 webpack 报错；应停进程 + 清缓存 + 重启。

**必须**设置 `NEXT_PUBLIC_API_BASE` 为后端根地址（无尾斜杠），与 [src/lib/api.ts](src/lib/api.ts) 中逻辑一致。未设置时，请求会失败并提示配置环境变量。

生产/ Vercel：在平台环境变量中设置同一变量，指向已部署的 API 域名（如 `https://api.example.com`）。

## 构建

```bash
npm ci
npm run build
```

若在同步盘（如 iCloud Desktop）上出现 webpack cache `.next/cache` 读超时，请在仓库本地磁盘克隆后再构建；本项目已在 `next.config.mjs` 关闭 webpack persistent cache 以降低此类概率。

类型检查（不依赖 webpack pack cache）：

```bash
npx tsc -p tsconfig.json --noEmit
```

## UI 自检清单（生成）

根据侧栏与 `src/app/**/page.tsx` 生成逐步检查表（写入仓库根 `docs/generated_ui_checklist.md`）：

```bash
npm run ui:checklist
```

说明见仓库根 [docs/ui_interaction_self_check.md](../docs/ui_interaction_self_check.md)；补充 query 等见 [scripts/ui-checklist-overrides.json](scripts/ui-checklist-overrides.json)。

## 样式

使用 Tailwind CSS v4（`tailwindcss`、`@tailwindcss/postcss`，见 [package.json](package.json)）。
