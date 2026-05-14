"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "仪表盘", icon: "dashboard" },
  { href: "/analysis", label: "个股分析", icon: "analytics" },
  { href: "/strategy", label: "策略", icon: "query_stats" },
  { href: "/x-brief", label: "X资讯简报", icon: "newspaper" },
  { href: "/stock-detail", label: "股票详情", icon: "monitoring" },
  { href: "/trading-agents", label: "TradingAgents", icon: "psychology" },
  { href: "/portfolio", label: "持仓", icon: "account_balance_wallet" },
  { href: "/backtesting", label: "策略回测", icon: "timeline" },
];

export function NavSidebar() {
  const pathname = usePathname();
  const strategyOpen = pathname === "/strategy" || pathname === "/strategy/wheel";

  return (
    <div className="flex h-full flex-col items-center py-3">
      <ul className="flex w-full flex-1 flex-col items-center gap-1">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <li className="w-full" key={item.href}>
              <Link
                className={`group relative flex w-full justify-center py-3 transition ${
                  active
                    ? "border-l-2 border-[#2962FF] bg-[#0B0E11] text-[#2962FF]"
                    : "text-[#5E6673] hover:bg-[#2B2F36] hover:text-white"
                }`}
                href={item.href}
                title={item.label}
              >
                <span className="material-symbols-outlined text-[19px]">{item.icon}</span>
                <span className="pointer-events-none absolute left-[70px] top-1/2 hidden -translate-y-1/2 rounded border border-[#2B2F36] bg-[#0F1318] px-2 py-1 text-[11px] text-slate-200 group-hover:block">
                  {item.label}
                </span>
              </Link>
              {item.href === "/strategy" && strategyOpen && (
                <div className="mt-1 flex flex-col gap-1 px-1">
                  <Link
                    className={`rounded px-1 py-1 text-center text-[9px] ${
                      pathname === "/strategy"
                        ? "border border-[#3c6396] bg-[#182c4f] text-[#dfeaff]"
                        : "border border-transparent text-[#8ea0be] hover:border-[#2a4067] hover:bg-[#111d32]"
                    }`}
                    href="/strategy"
                  >
                    LRS
                  </Link>
                  <Link
                    className={`rounded px-1 py-1 text-center text-[9px] ${
                      pathname === "/strategy/wheel"
                        ? "border border-[#3c6396] bg-[#182c4f] text-[#dfeaff]"
                        : "border border-transparent text-[#8ea0be] hover:border-[#2a4067] hover:bg-[#111d32]"
                    }`}
                    href="/strategy/wheel"
                  >
                    Wheel
                  </Link>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <div className="mb-1 flex w-full flex-col items-center gap-1">
        <span className="material-symbols-outlined cursor-pointer py-1 text-[18px] text-[#5E6673] hover:text-white">settings</span>
        <span className="material-symbols-outlined cursor-pointer py-1 text-[18px] text-[#5E6673] hover:text-white">help</span>
      </div>
    </div>
  );
}

