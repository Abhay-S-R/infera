"use client";

import { useEffect, useState } from "react";
import styles from "./ReportDetail.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const TABS = [
  { key: "exec", label: "Executive", icon: "E" },
  { key: "tech", label: "Technical", icon: "T" },
  { key: "sales", label: "Sales", icon: "S" },
  { key: "risk", label: "Risk", icon: "R" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

interface Report {
  id: string | number;
  title?: string;
  competitor?: string;
  confidence?: number;
  documents?: Record<string, string>;
  full_report_markdown?: string;
  content?: string;
  markdown?: string;
}

interface ReportDetailProps {
  reportId: string | number;
  onBack: () => void;
}

function getDocuments(report: Report): Record<TabKey, string> {
  const docs = report.documents || {};
  const fallback =
    report.full_report_markdown || report.content || report.markdown || "";
  return {
    exec: docs.exec || fallback,
    tech: docs.tech || fallback,
    sales: docs.sales || fallback,
    risk: docs.risk || fallback,
  };
}

/**
 * Simple markdown → React elements renderer.
 * Handles headings, paragraphs, bold, lists, and horizontal rules.
 * No dangerouslySetInnerHTML — safe by design.
 */
function renderMarkdown(md: string): React.ReactNode[] {
  if (!md) return [<p key="empty" className={styles.emptyDoc}>No content available for this audience.</p>];

  const lines = md.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let keyCounter = 0;

  function flushList() {
    if (listItems.length === 0) return;
    const items = listItems.map((item, i) => (
      <li key={i}>{renderInline(item)}</li>
    ));
    const listKey = `list-${keyCounter++}`;
    if (listType === "ol") {
      elements.push(<ol key={listKey}>{items}</ol>);
    } else {
      elements.push(<ul key={listKey}>{items}</ul>);
    }
    listItems = [];
    listType = null;
  }

  function renderInline(text: string): React.ReactNode {
    // Handle **bold** and *italic*
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*(.+?)\*\*|\*(.+?)\*)/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      if (match[2]) {
        parts.push(<strong key={match.index}>{match[2]}</strong>);
      } else if (match[3]) {
        parts.push(<em key={match.index}>{match[3]}</em>);
      }
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    return parts.length === 1 ? parts[0] : <>{parts}</>;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Headings
    if (line.startsWith("### ")) {
      flushList();
      elements.push(<h3 key={`h3-${i}`}>{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      flushList();
      elements.push(<h2 key={`h2-${i}`}>{renderInline(line.slice(3))}</h2>);
    } else if (line.startsWith("# ")) {
      flushList();
      elements.push(<h1 key={`h1-${i}`}>{renderInline(line.slice(2))}</h1>);
    }
    // Horizontal rule
    else if (/^---+$/.test(line.trim())) {
      flushList();
      elements.push(<hr key={`hr-${i}`} />);
    }
    // Unordered list
    else if (/^[\s]*[-*]\s/.test(line)) {
      if (listType !== "ul") {
        flushList();
        listType = "ul";
      }
      listItems.push(line.replace(/^[\s]*[-*]\s/, ""));
    }
    // Ordered list
    else if (/^[\s]*\d+\.\s/.test(line)) {
      if (listType !== "ol") {
        flushList();
        listType = "ol";
      }
      listItems.push(line.replace(/^[\s]*\d+\.\s/, ""));
    }
    // Empty line
    else if (line.trim() === "") {
      flushList();
    }
    // Paragraph
    else {
      flushList();
      elements.push(<p key={`p-${i}`}>{renderInline(line)}</p>);
    }
  }
  flushList();

  return elements;
}

function getConfidenceInfo(confidence: number | undefined) {
  if (confidence === undefined || confidence === null)
    return { label: "", value: "", cls: "" };
  const norm = confidence > 1 ? confidence / 100 : confidence;
  const display =
    confidence > 1
      ? Math.round(confidence) + "%"
      : Math.round(norm * 100) + "%";
  if (norm >= 0.8) return { label: "HIGH", value: display, cls: styles.confHigh };
  if (norm >= 0.5) return { label: "MED", value: display, cls: styles.confMed };
  return { label: "LOW", value: display, cls: styles.confLow };
}

export default function ReportDetail({ reportId, onBack }: ReportDetailProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("exec");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/reports/${reportId}`);
        if (!res.ok) throw new Error("Failed to fetch report");
        setReport(await res.json());
      } catch {
        setReport(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [reportId]);

  if (loading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
        <span>Loading report…</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className={styles.errorContainer}>
        <span>Failed to load report details.</span>
        <button className={styles.backBtn} onClick={onBack}>
          ← Back to reports
        </button>
      </div>
    );
  }

  const docs = getDocuments(report);
  const conf = getConfidenceInfo(report.confidence);

  return (
    <div className={styles.detail}>
      {/* Header bar */}
      <div className={styles.detailHeader}>
        <button className={styles.backBtn} onClick={onBack} type="button">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </button>

        <div className={styles.detailTitle}>
          <h2>{report.title || "Report"}</h2>
          {conf.value && (
            <span className={`${styles.confBadge} ${conf.cls}`}>
              {conf.value} {conf.label}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`${styles.tab} ${activeTab === tab.key ? styles.tabActive : ""}`}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            <span className={styles.tabIcon}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div key={activeTab} className={styles.content}>
        {renderMarkdown(docs[activeTab])}
      </div>
    </div>
  );
}
