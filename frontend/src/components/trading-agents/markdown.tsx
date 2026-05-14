"use client";

import { useMemo } from "react";
import type { ReactNode } from "react";

type Token =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "blockquote"; text: string }
  | { type: "code"; text: string; lang: string | null }
  | { type: "hr" }
  | { type: "table"; headers: string[]; rows: string[][] };

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((s) => s.trim());
}

function tokenize(md: string): Token[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const tokens: Token[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim() || null;
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++;
      tokens.push({ type: "code", text: buf.join("\n"), lang });
      continue;
    }

    if (/^---+$/.test(line.trim()) || /^\*\*\*+$/.test(line.trim())) {
      tokens.push({ type: "hr" });
      i++;
      continue;
    }

    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      tokens.push({ type: "heading", level: h[1].length, text: h[2] });
      i++;
      continue;
    }

    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      /^\s*\|?[\s\-:|]+\|?\s*$/.test(lines[i + 1]) &&
      lines[i + 1].includes("-")
    ) {
      const headers = parseTableRow(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(parseTableRow(lines[i]));
        i++;
      }
      tokens.push({ type: "table", headers, rows });
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      tokens.push({ type: "ul", items });
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      tokens.push({ type: "ol", items });
      continue;
    }

    if (line.startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        buf.push(lines[i].slice(1).trim());
        i++;
      }
      tokens.push({ type: "blockquote", text: buf.join(" ") });
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    const para: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i]) &&
      !lines[i].startsWith(">") &&
      !lines[i].startsWith("```") &&
      !lines[i].includes("|")
    ) {
      para.push(lines[i]);
      i++;
    }
    tokens.push({ type: "paragraph", text: para.join(" ") });
  }
  return tokens;
}

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let key = 0;
  const regex =
    /(\*\*([\s\S]+?)\*\*)|(__([\s\S]+?)__)|(\*([^*\n]+?)\*)|(_([^_\n]+?)_)|(`([^`]+?)`)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > lastIdx) parts.push(text.slice(lastIdx, m.index));
    if (m[1])
      parts.push(
        <strong key={key++} className="font-semibold text-white">
          {m[2]}
        </strong>,
      );
    else if (m[3])
      parts.push(
        <strong key={key++} className="font-semibold text-white">
          {m[4]}
        </strong>,
      );
    else if (m[5])
      parts.push(
        <em key={key++} className="italic">
          {m[6]}
        </em>,
      );
    else if (m[7])
      parts.push(
        <em key={key++} className="italic">
          {m[8]}
        </em>,
      );
    else if (m[9])
      parts.push(
        <code
          key={key++}
          className="rounded bg-[#1e232b] px-1 py-0.5 font-mono text-[12px] text-[#fbbf24]"
        >
          {m[10]}
        </code>,
      );
    else if (m[11])
      parts.push(
        <a
          key={key++}
          href={m[13]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#60a5fa] underline"
        >
          {m[12]}
        </a>,
      );
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts;
}

export function Md({ text }: { text: string }) {
  const tokens = useMemo(() => tokenize(text), [text]);
  return (
    <div className="markdown-body text-[13px] leading-relaxed text-[#d4d6e0]">
      {tokens.map((tok, idx) => {
        if (tok.type === "heading") {
          const sizes = [
            "text-[18px]",
            "text-[16px]",
            "text-[15px]",
            "text-[13px]",
            "text-[13px]",
            "text-[13px]",
          ];
          const cls = `font-semibold text-white mt-3 mb-1.5 ${
            sizes[tok.level - 1] ?? "text-[13px]"
          }`;
          if (tok.level === 1)
            return (
              <h1 key={idx} className={cls}>
                {renderInline(tok.text)}
              </h1>
            );
          if (tok.level === 2)
            return (
              <h2 key={idx} className={cls}>
                {renderInline(tok.text)}
              </h2>
            );
          if (tok.level === 3)
            return (
              <h3 key={idx} className={cls}>
                {renderInline(tok.text)}
              </h3>
            );
          return (
            <h4 key={idx} className={cls}>
              {renderInline(tok.text)}
            </h4>
          );
        }
        if (tok.type === "paragraph") {
          return (
            <p key={idx} className="my-1.5">
              {renderInline(tok.text)}
            </p>
          );
        }
        if (tok.type === "ul") {
          return (
            <ul key={idx} className="my-1.5 list-disc space-y-0.5 pl-5">
              {tok.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ul>
          );
        }
        if (tok.type === "ol") {
          return (
            <ol key={idx} className="my-1.5 list-decimal space-y-0.5 pl-5">
              {tok.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ol>
          );
        }
        if (tok.type === "blockquote") {
          return (
            <blockquote
              key={idx}
              className="my-1.5 border-l-2 border-[#2B2F36] pl-3 text-[#a8acc0]"
            >
              {renderInline(tok.text)}
            </blockquote>
          );
        }
        if (tok.type === "code") {
          return (
            <pre
              key={idx}
              className="my-2 overflow-x-auto rounded border border-[#2B2F36] bg-[#0f1318] p-3 font-mono text-[12px] text-[#c3c5d8]"
            >
              <code>{tok.text}</code>
            </pre>
          );
        }
        if (tok.type === "hr") {
          return <hr key={idx} className="my-3 border-[#2B2F36]" />;
        }
        if (tok.type === "table") {
          return (
            <div key={idx} className="my-2 overflow-x-auto">
              <table className="min-w-full border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-[#2B2F36]">
                    {tok.headers.map((h, j) => (
                      <th
                        key={j}
                        className="px-2 py-1.5 text-left font-semibold text-white"
                      >
                        {renderInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tok.rows.map((r, ri) => (
                    <tr key={ri} className="border-b border-[#1e232b]">
                      {r.map((c, ci) => (
                        <td key={ci} className="px-2 py-1 text-[#d4d6e0]">
                          {renderInline(c)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
