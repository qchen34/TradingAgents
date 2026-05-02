"use client";

import { useEffect, useState } from "react";

export default function ApiHealthPage() {
  const [health, setHealth] = useState("checking");
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"}/health`)
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

