"use client";

import { useState, useEffect } from "react";
import ReportCard from "@/components/reports/ReportCard";
import ReportDetail from "@/components/reports/ReportDetail";
import { fetchReports, type Report } from "@/lib/api";
import styles from "./page.module.css";

type View = { type: "list" } | { type: "detail"; reportId: string | number };

export default function ReportsPage() {
  const [view, setView] = useState<View>({ type: "list" });
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (view.type !== "list") return;

      setLoading(true);
      setError(null);
      try {
        const data = await fetchReports();
        setReports(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load reports");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [view]);

  // List View
  if (view.type === "list") {
    if (loading) {
      return (
        <div className={styles.page}>
          <h1 className={styles.title}>Intelligence Reports</h1>
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>Loading reports…</span>
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div className={styles.page}>
          <h1 className={styles.title}>Intelligence Reports</h1>
          <div className={styles.error}>
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p>{error}</p>
            <button
              className={styles.retryBtn}
              onClick={() => setView({ type: "list" })}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    if (reports.length === 0) {
      return (
        <div className={styles.page}>
          <h1 className={styles.title}>Intelligence Reports</h1>
          <div className={styles.empty}>
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            <h2>No Reports Yet</h2>
            <p>
              Submit an analysis from the dashboard to generate your first
              intelligence report.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className={styles.page}>
        <h1 className={styles.title}>Intelligence Reports</h1>
        <div className={styles.grid}>
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onClick={() => setView({ type: "detail", reportId: report.id })}
            />
          ))}
        </div>
      </div>
    );
  }

  // Detail View
  return (
    <div className={styles.page}>
      <ReportDetail
        reportId={view.reportId}
        onBack={() => setView({ type: "list" })}
      />
    </div>
  );
}
