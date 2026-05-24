"use client";

import styles from "./ReportCard.module.css";

interface Report {
  id: string | number;
  title: string;
  competitor?: string;
  confidence?: number;
  created_at?: string;
}

interface ReportCardProps {
  report: Report;
  onClick: () => void;
}

function getConfidenceInfo(confidence: number | undefined) {
  if (confidence === undefined || confidence === null)
    return { label: "N/A", color: "muted", value: "—" };

  const norm = confidence > 1 ? confidence / 100 : confidence;
  const display = confidence > 1 ? Math.round(confidence) + "%" : Math.round(norm * 100) + "%";

  if (norm >= 0.8) return { label: "HIGH", color: "high", value: display };
  if (norm >= 0.5) return { label: "MED", color: "med", value: display };
  return { label: "LOW", color: "low", value: display };
}

export default function ReportCard({ report, onClick }: ReportCardProps) {
  const conf = getConfidenceInfo(report.confidence);
  const dateStr = report.created_at
    ? new Date(report.created_at).toLocaleString()
    : "";

  return (
    <button className={styles.card} onClick={onClick} type="button">
      <div className={styles.top}>
        <span className={styles.title}>{report.title || "Analysis Report"}</span>
        <div className={styles.icon}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
        </div>
      </div>

      <div className={styles.meta}>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Competitor</span>
          <span className={styles.metaValue}>
            {report.competitor || "Unknown"}
          </span>
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Confidence</span>
          <span className={`${styles.confBadge} ${styles[conf.color]}`}>
            {conf.value} {conf.label}
          </span>
        </div>
      </div>

      {dateStr && <span className={styles.date}>{dateStr}</span>}

      <div className={styles.cta}>
        View 4 Docs
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </div>
    </button>
  );
}
