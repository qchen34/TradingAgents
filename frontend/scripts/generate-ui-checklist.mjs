/**
 * 从 nav-sidebar NAV 与 src/app 下各 page.tsx 扫描生成 UI 自检步骤 Markdown。
 * 输出：仓库根 docs/generated_ui_checklist.md
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const repoRoot = path.join(frontendRoot, "..");
const outFile = path.join(repoRoot, "docs", "generated_ui_checklist.md");
const navFile = path.join(frontendRoot, "src", "components", "nav-sidebar.tsx");
const appDir = path.join(frontendRoot, "src", "app");
const overridesPath = path.join(__dirname, "ui-checklist-overrides.json");

function parseNavHrefs() {
  const text = fs.readFileSync(navFile, "utf8");
  const items = [];
  const re = /\{\s*href:\s*"([^"]+)"\s*,\s*label:\s*"([^"]*)"/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    items.push({ href: m[1], label: m[2] });
  }
  return items;
}

function collectRoutesFromAppDir() {
  const routes = [];

  function walk(dir, relParts) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const e of entries) {
      const name = e.name;
      if (name === "api" && e.isDirectory()) continue;
      const full = path.join(dir, name);
      if (e.isDirectory()) {
        walk(full, [...relParts, name]);
      } else if (name === "page.tsx") {
        const rel = relParts.join("/");
        const route = rel ? `/${rel.replace(/\\/g, "/")}` : "/";
        routes.push(route);
      }
    }
  }

  walk(appDir, []);
  return [...new Set(routes)].sort();
}

function loadOverrides() {
  if (!fs.existsSync(overridesPath)) {
    return { extraRoutes: [], pathOverrides: {}, subNavRoutes: [] };
  }
  return JSON.parse(fs.readFileSync(overridesPath, "utf8"));
}

function visitPathFor(route, overrides) {
  const o = overrides.pathOverrides?.[route];
  if (o?.visitPath) return o.visitPath;
  return route;
}

function buildSteps() {
  const nav = parseNavHrefs();
  const fromPages = collectRoutesFromAppDir();
  const overrides = loadOverrides();
  /** @type {Set<string>} */
  const covered = new Set();

  /** @type {{ step: number, route: string, visitPath: string, label: string, navEntry: string, actions: string, expect: string, failures: string, optimization: string }[]} */
  const steps = [];

  const push = (route, visitPath, label, navEntry, actions, expect, failures) => {
    if (covered.has(route)) return;
    covered.add(route);
    steps.push({
      step: steps.length + 1,
      route,
      visitPath,
      label,
      navEntry,
      actions,
      expect,
      failures,
      optimization: "（执行自检时填写：体验 / 无障碍 / 性能 / 文案）",
    });
  };

  for (const n of nav) {
    const route = n.href;
    const vp = visitPathFor(route, overrides);
    const note = overrides.pathOverrides?.[route]?.note || "";
    push(
      route,
      vp,
      n.label,
      `侧栏「${n.label}」`,
      `点击侧栏图标进入；实际访问 \`${vp}\`。${note ? " " + note : ""}`,
      "页面无长时间白屏；主工作区出现该页标题或核心控件；控制台无未处理错误（允许已知接口失败提示）。",
      "前端 dev 未启动；API_BASE 错误导致整页报错；路由 404。"
    );
  }

  for (const sn of overrides.subNavRoutes || []) {
    const vp = visitPathFor(sn.path, overrides);
    push(
      sn.path,
      vp,
      sn.label,
      sn.parentNav ? `侧栏策略子项「${sn.label}」` : "子路由",
      sn.actions || `访问 \`${vp}\`（可先点侧栏「策略」展开再点 ${sn.label}）。`,
      sn.expect || "页面与控件可见。",
      sn.failures || "父级未展开时仅能通过 URL 进入。"
    );
  }

  for (const ex of overrides.extraRoutes || []) {
    const vp = ex.visitPath || ex.path;
    push(
      ex.path,
      vp,
      ex.label,
      ex.fromNav ? "侧栏" : "无侧栏（直连）",
      ex.actions,
      ex.expect,
      ex.failures
    );
  }

  for (const r of fromPages) {
    if (covered.has(r)) continue;
    const vp = visitPathFor(r, overrides);
    const label = r === "/" ? "首页" : r;
    push(
      r,
      vp,
      label,
      "路由发现（侧栏无入口）",
      `浏览器打开 \`${vp}\`。`,
      "页面可渲染；无意外 404。",
      "用户难以发现该页，考虑挂到导航或设置内链。"
    );
  }

  steps.forEach((s, i) => {
    s.step = i + 1;
  });
  return steps;
}

function renderMarkdown(steps) {
  const genAt = new Date().toISOString();
  const lines = [];
  lines.push("# 机器生成的 UI 自检步骤清单");
  lines.push("");
  lines.push(
    `> 由 \`frontend/scripts/generate-ui-checklist.mjs\` 生成于 **${genAt}**。请勿手工改本文件内容；修改导航或路由后重新运行 \`npm run ui:checklist\`。`
  );
  lines.push("");
  lines.push("## 环境前提");
  lines.push("");
  lines.push("- 前端：`cd frontend && npm run dev`（默认 http://localhost:3000）");
  lines.push(
    "- 环境变量：`frontend/.env.development` 中配置 `NEXT_PUBLIC_API_BASE`（如 `http://127.0.0.1:8000`），无则多数数据页会报错。"
  );
  lines.push(
    "- 后端（可选）：本仓库 FastAPI `uvicorn backend.api.main:app --port 8000`，以便 Dashboard / 个股追踪 / X 简报等接口可用。"
  );
  lines.push("");
  lines.push("## 逐步检查");
  lines.push("");
  lines.push(
    "| Step | 路由 | 访问 URL | 侧栏/入口 | 操作 | 期望 | 常见失败 | 优化观察（填） |"
  );
  lines.push("|------|------|----------|-------------|------|------|----------|----------------|");
  for (const s of steps) {
    const op = s.optimization.replace(/\|/g, "\\|");
    lines.push(
      `| ${s.step} | \`${s.route}\` | \`${s.visitPath}\` | ${s.navEntry.replace(/\|/g, "\\|")} | ${s.actions.replace(/\|/g, "\\|")} | ${s.expect.replace(/\|/g, "\\|")} | ${s.failures.replace(/\|/g, "\\|")} | ${op} |`
    );
  }
  lines.push("");
  lines.push("## 说明");
  lines.push("");
  lines.push(
    "- 与人工主编检、backlog 的衔接见 [ui_interaction_self_check.md](./ui_interaction_self_check.md)。"
  );
  lines.push("");
  return lines.join("\n");
}

const steps = buildSteps();
const md = renderMarkdown(steps);
fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, md, "utf8");
console.log(`Wrote ${path.relative(repoRoot, outFile)} (${steps.length} steps).`);
