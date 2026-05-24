"use client";

import { useState, type FormEvent } from "react";
import styles from "./AnalyzeForm.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface AnalyzeFormProps {
  onActivityEvent?: (event: Record<string, unknown>) => void;
}

export default function AnalyzeForm({ onActivityEvent }: AnalyzeFormProps) {
  const [competitor, setCompetitor] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!competitor.trim() || !question.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: competitor.trim(),
          custom_question: question.trim(),
        }),
      });

      if (!res.ok) throw new Error("Failed to start analysis");

      onActivityEvent?.({
        agent: "System",
        status: "success",
        message: `Started analysis for ${competitor}: "${question}"`,
      });

      setCompetitor("");
      setQuestion("");
    } catch (err) {
      // TODO(security): Use a modal component instead of console output in production
      onActivityEvent?.({
        agent: "System",
        status: "error",
        message: `Error starting analysis: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div className={styles.headerContent}>
          <span className={styles.headerLabel}>Launch Analysis</span>
          <span className={styles.headerSub}>
            Enter a competitor and question to trigger the intelligence pipeline
          </span>
        </div>
        <div className={styles.iconBox}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
            <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
          </svg>
        </div>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.inputGroup}>
          <label htmlFor="competitor-name" className={styles.inputLabel}>
            Competitor
          </label>
          <input
            id="competitor-name"
            type="text"
            className={`form-input ${styles.input}`}
            placeholder="e.g. Acme Corp"
            value={competitor}
            onChange={(e) => setCompetitor(e.target.value)}
            required
          />
        </div>

        <div className={styles.inputGroup}>
          <label htmlFor="analyze-question" className={styles.inputLabel}>
            Question
          </label>
          <input
            id="analyze-question"
            type="text"
            className={`form-input ${styles.input}`}
            placeholder="e.g. What is their pricing strategy?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
          />
        </div>

        <button
          type="submit"
          className={styles.submitBtn}
          disabled={loading}
        >
          {loading ? (
            <>
              <span className={styles.spinner} />
              Launching…
            </>
          ) : (
            <>
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
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Analyze
            </>
          )}
        </button>
      </form>
    </div>
  );
}
