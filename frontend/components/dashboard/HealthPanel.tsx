"use client";

import { useEffect, useState } from "react";
import styles from "./HealthPanel.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface HealthStats {
  active_workflows: number;
  total_reports: number;
  recent_completions: {
    competitor?: string;
    title?: string;
    completed_at?: string;
  }[];
}

export default function HealthPanel() {
  const [stats, setStats] = useState<HealthStats | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch(`${API_URL}/api/health/stats`);
        if (!res.ok) throw new Error("Health endpoint unavailable");
        const data = await res.json();
        setStats(data);
        setOnline(true);
      } catch {
        setOnline(false);
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.headerLabel}>System Health</span>
        <div
          className={`${styles.statusBadge} ${online ? styles.statusOnline : styles.statusOffline}`}
        >
          <span className={styles.statusDot} />
          {online ? "Online" : "Offline"}
        </div>
      </div>

      {online && stats ? (
        <>
          <div className={styles.statRow}>
            <div className={styles.stat}>
              <span className={styles.statValue}>
                {stats.active_workflows}
              </span>
              <span className={styles.statLabel}>Active Workflows</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statValue}>{stats.total_reports}</span>
              <span className={styles.statLabel}>Total Reports</span>
            </div>
          </div>

          <div className={styles.completions}>
            <span className={styles.completionsTitle}>
              Recent Completions
            </span>
            {stats.recent_completions.length === 0 ? (
              <span className={styles.empty}>No recent completions</span>
            ) : (
              stats.recent_completions.slice(0, 5).map((c, i) => (
                <div key={i} className={styles.completionItem}>
                  <span className="status-indicator status-success" />
                  <span className={styles.completionName}>
                    {c.competitor || c.title || "Analysis"}
                  </span>
                  <span className={styles.completionTime}>
                    {c.completed_at
                      ? new Date(c.completed_at).toLocaleTimeString()
                      : ""}
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      ) : !online ? (
        <div className={styles.offlineMsg}>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19.69 14a6.9 6.9 0 0 0 .31-2V5l-8-3-3.16 1.18" />
            <path d="M4.73 4.73 4 5v7c0 6 8 10 8 10a20.29 20.29 0 0 0 5.62-4.38" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
          <span>Unable to reach backend</span>
          <span className={styles.retryHint}>Retrying every 10s…</span>
        </div>
      ) : null}
    </div>
  );
}
