"use client";

import { useEffect, useState } from "react";

export default function ApiHealthPage() {
  const [health, setHealth] = useState("checking");
  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
    if (!apiBase) {
      setHealth("missing NEXT_PUBLIC_API_BASE");
      return;
    }
    fetch(`${apiBase}/health`)
      .then((r) => r.json())
      .then(() => setHealth("ok"))
      .catch(() => setHealth("failed"));
  }, []);
  return (
    <div>
      <h1>API 健康检查</h1>
      <p>后端状态：{health}</p>
    </div>
  );
}

