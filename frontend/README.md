# TradingAgents Frontend

Next.js（App Router）+ TypeScript，对接仓库根目录的 FastAPI（`backend/`）。

## 本地启动

```bash
npm ci
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev
```

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

## 样式

使用 Tailwind CSS v4（`tailwindcss`、`@tailwindcss/postcss`，见 [package.json](package.json)）。
