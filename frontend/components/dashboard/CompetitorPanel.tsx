"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import styles from "./CompetitorPanel.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface Competitor {
  id?: string;
  name: string;
}

export default function CompetitorPanel() {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [input, setInput] = useState("");

  async function fetchCompetitors() {
    try {
      const res = await fetch(`${API_URL}/api/competitors`);
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.competitors || [];
      setCompetitors(
        list.map((c: string | Competitor) =>
          typeof c === "string" ? { name: c, id: c } : { name: c.name || String(c), id: c.id || c.name || String(c) }
        )
      );
    } catch {
      /* silent — panel just shows empty */
    }
  }

  useEffect(() => {
    fetchCompetitors();
  }, []);

  async function addCompetitor() {
    const name = input.trim();
    if (!name) return;
    try {
      const res = await fetch(`${API_URL}/api/competitors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) return;
      setInput("");
      fetchCompetitors();
    } catch {
      /* silent */
    }
  }

  async function removeCompetitor(id: string) {
    try {
      const res = await fetch(
        `${API_URL}/api/competitors/${encodeURIComponent(id)}`,
        { method: "DELETE" }
      );
      if (!res.ok) return;
      fetchCompetitors();
    } catch {
      /* silent */
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addCompetitor();
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.headerLabel}>Tracked Competitors</span>
        <span className={styles.count}>{competitors.length}</span>
      </div>

      {/* Add input */}
      <div className={styles.addRow}>
        <input
          type="text"
          className={`form-input ${styles.addInput}`}
          placeholder="Add competitor…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          className={styles.addBtn}
          onClick={addCompetitor}
          disabled={!input.trim()}
        >
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
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      {/* List */}
      <div className={styles.list}>
        {competitors.length === 0 ? (
          <span className={styles.empty}>No competitors tracked yet</span>
        ) : (
          competitors.map((c) => (
            <div key={c.id} className={styles.item}>
              <div className={styles.itemInfo}>
                <span className="status-indicator status-success" />
                <span className={styles.itemName}>{c.name}</span>
              </div>
              <button
                className={styles.removeBtn}
                onClick={() => removeCompetitor(c.id || c.name)}
                title="Remove"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
