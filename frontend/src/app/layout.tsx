import "./globals.css";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { NavSidebar } from "@/components/nav-sidebar";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <nav className="fixed top-0 z-50 flex h-8 w-full items-center justify-between border-b border-[#2B2F36] bg-[#0B0E11] px-3">
          <div className="flex items-center">
            <span className="mr-3 border-r border-[#2B2F36] pr-3 text-xs font-bold tracking-wide text-white">
              MISSION CONTROL
            </span>
            <div className="flex items-center gap-4 font-mono text-[11px] uppercase tracking-widest">
              <span className="text-emerald-400">S&amp;P +0.42%</span>
              <span className="text-rose-400">NASDAQ -0.12%</span>
              <span className="text-emerald-400">BTC +1.24%</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[#5E6673]">
            <span className="material-symbols-outlined text-[16px]">notifications</span>
            <span className="material-symbols-outlined text-[16px]">wifi</span>
            <span className="material-symbols-outlined text-[16px]">power_settings_new</span>
          </div>
        </nav>

        <div className="pt-8">
          <aside className="fixed left-0 top-8 z-40 flex h-[calc(100vh-32px)] w-16 flex-col border-r border-[#2B2F36] bg-[#161A1E]">
            <Suspense fallback={null}>
              <NavSidebar />
            </Suspense>
          </aside>
          <main className="ml-16 h-[calc(100vh-32px)] overflow-hidden bg-[#0B0E11] p-2">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

