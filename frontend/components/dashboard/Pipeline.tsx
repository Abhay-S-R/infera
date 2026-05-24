"use client";

import styles from "./Pipeline.module.css";

export interface PipelineStatus {
  [node: string]: "idle" | "running" | "active" | "done" | "error" | "retry";
}

interface PipelineProps {
  statuses: PipelineStatus;
}

const NODES = [
  { key: "sentinel", label: "Sentinel", icon: "S" },
  { key: "verifier", label: "Verifier", icon: "V" },
  { key: "scout", label: "Scout", icon: "Sc" },
  { key: "strategist", label: "Strategist", icon: "St" },
  { key: "arbiter", label: "Arbiter", icon: "A" },
  { key: "scribe", label: "Scribe", icon: "W" },
];

function getNodeClass(status: string | undefined): string {
  switch (status) {
    case "running":
    case "active":
      return styles.running;
    case "done":
      return styles.done;
    case "error":
      return styles.error;
    case "retry":
      return styles.retry;
    default:
      return styles.idle;
  }
}

export default function Pipeline({ statuses }: PipelineProps) {
  const showRetryArc =
    statuses["arbiter"] === "retry" || statuses["scout"] === "retry";

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.title}>Agent Pipeline</span>
        <span className={styles.subtitle}>Real-time orchestration</span>
      </div>

      <div className={styles.pipeline}>
        {/* Retry arc (Arbiter → Scout) */}
        <div
          className={`${styles.retryArc} ${showRetryArc ? styles.retryArcVisible : ""}`}
        />

        {NODES.map((node, i) => (
          <div key={node.key} className={styles.nodeGroup}>
            {/* Node */}
            <div className={styles.nodeContainer}>
              <div
                className={`${styles.node} ${getNodeClass(statuses[node.key])}`}
              >
                <span className={styles.nodeIcon}>{node.icon}</span>
              </div>

              {/* Glow ring for active nodes */}
              {(statuses[node.key] === "running" ||
                statuses[node.key] === "active") && (
                <div className={styles.glowRing} />
              )}
              {statuses[node.key] === "retry" && (
                <div className={styles.glowRingOrange} />
              )}
            </div>

            <span className={styles.nodeLabel}>{node.label}</span>

            <span
              className={`${styles.nodeStatus} ${statuses[node.key] === "running" || statuses[node.key] === "active" ? styles.nodeStatusActive : ""} ${statuses[node.key] === "done" ? styles.nodeStatusDone : ""} ${statuses[node.key] === "error" ? styles.nodeStatusError : ""}`}
            >
              {statuses[node.key]
                ? statuses[node.key].charAt(0).toUpperCase() +
                  statuses[node.key].slice(1)
                : "Idle"}
            </span>

            {/* Connector line */}
            {i < NODES.length - 1 && (
              <div className={styles.connector}>
                <div
                  className={`${styles.connectorLine} ${statuses[NODES[i].key] === "done" ? styles.connectorDone : ""}`}
                />
                <div className={styles.connectorArrow} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
