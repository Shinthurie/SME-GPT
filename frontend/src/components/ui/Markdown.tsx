import React from "react";

// A small, dependency-free markdown renderer for chat/answer text. Handles the
// subset the LLM actually produces — **bold**, *italic*, `code`, headings,
// unordered/ordered lists, --- rules, and blank-line-separated paragraphs — so
// the answers read like a chat app instead of showing raw ** and ---.

const HR = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/;
const H = /^\s*(#{1,6})\s+(.*)$/;
const UL = /^\s*[-*+]\s+/;
const OL = /^\s*\d+\.\s+/;
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;

function renderInline(text: string, k: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0, i = 0, m: RegExpExecArray | null;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${k}b${i}`}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`"))
      out.push(
        <code key={`${k}c${i}`} className="rounded px-1 py-0.5 text-[0.86em]"
          style={{ background: "var(--surface-2)", fontFamily: "ui-monospace, monospace" }}>
          {tok.slice(1, -1)}
        </code>,
      );
    else out.push(<em key={`${k}i${i}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }: { text: string }) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0, key = 0;

  const isSpecial = (ln: string) =>
    HR.test(ln) || H.test(ln) || UL.test(ln) || OL.test(ln);

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    if (HR.test(line)) {
      blocks.push(<hr key={key++} className="my-3" style={{ border: 0, borderTop: "1px solid var(--border)" }} />);
      i++; continue;
    }

    const h = line.match(H);
    if (h) {
      blocks.push(
        <p key={key++} className="mt-1 font-bold" style={{ fontSize: h[1].length <= 2 ? "1.05em" : "1em" }}>
          {renderInline(h[2], `h${key}`)}
        </p>,
      );
      i++; continue;
    }

    if (UL.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && UL.test(lines[i])) {
        items.push(<li key={`${key}li${i}`}>{renderInline(lines[i].replace(UL, ""), `${key}l${i}`)}</li>);
        i++;
      }
      blocks.push(<ul key={key++} className="list-disc space-y-1 pl-5">{items}</ul>);
      continue;
    }

    if (OL.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && OL.test(lines[i])) {
        items.push(<li key={`${key}li${i}`}>{renderInline(lines[i].replace(OL, ""), `${key}o${i}`)}</li>);
        i++;
      }
      blocks.push(<ol key={key++} className="list-decimal space-y-1 pl-5">{items}</ol>);
      continue;
    }

    // Paragraph: consecutive plain lines, internal newlines kept as <br>.
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !isSpecial(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    const nodes: React.ReactNode[] = [];
    para.forEach((p, idx) => {
      if (idx > 0) nodes.push(<br key={`${key}br${idx}`} />);
      nodes.push(...renderInline(p, `${key}p${idx}`));
    });
    blocks.push(<p key={key++}>{nodes}</p>);
  }

  return <div className="space-y-2">{blocks}</div>;
}
