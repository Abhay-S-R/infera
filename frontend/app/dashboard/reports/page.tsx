"use client";

import { useEffect, useState } from "react";
import ReportCard from "@/components/reports/ReportCard";
import ReportDetail from "@/components/reports/ReportDetail";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface Report {
  id: string | number;
  title: string;
  competitor?: string;
  confidence?: number;
  created_at?: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<string | number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  async function fetchReports() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/reports`);
      if (!res.ok) throw new Error("Failed to fetch reports");
      const data = await res.json();
      setReports(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load reports"
      );
    } finally {
      setLoading(false);
    }
  }

  if (selectedId !== null) {
    return (
      <ReportDetail
        reportId={selectedId}
        onBack={() => {
          setSelectedId(null);
          fetchReports();
        }}
      />
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Intelligence Reports</h1>
        <span className={styles.count}>
          {reports.length} report{reports.length !== 1 ? "s" : ""}
        </span>
      </div>

      {loading ? (
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <span>Loading reports…</span>
        </div>
      ) : error ? (
        <div className={styles.error}>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
          <button className={styles.retryBtn} onClick={fetchReports}>
            Retry
          </button>
        </div>
      ) : reports.length === 0 ? (
        <div className={styles.empty}>
          <svg
            width="36"
            height="36"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span>No reports available yet</span>
          <span className={styles.emptyHint}>
            Submit an analysis from the dashboard to generate reports
          </span>
        </div>
      ) : (
        <div className={styles.grid}>
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onClick={() => setSelectedId(report.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
