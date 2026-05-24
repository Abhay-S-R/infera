"use client";

import { useRef, useEffect } from "react";
import styles from "./ActivityFeed.module.css";

export interface ActivityEvent {
  agent?: string;
  node?: string;
  status?: string;
  message?: string;
  summary?: string;
  detail?: string;
  event_type?: string;
  timestamp?: string;
  delivery?: { channels?: DeliveryChannel[] };
  channels?: DeliveryChannel[];
}

interface DeliveryChannel {
  channel: string;
  success?: boolean;
  skipped?: boolean;
  message?: string;
}

interface ActivityFeedProps {
  events: ActivityEvent[];
}

function isArbiterRejection(e: ActivityEvent): boolean {
  const agent = (e.agent || e.node || "").toLowerCase();
  const status = (e.status || "").toLowerCase();
  const eventType = (e.event_type || "").toLowerCase();
  const msg = (e.message || "").toLowerCase();
  if (eventType === "arbiter.rejected") return true;
  if (agent === "arbiter" && (status === "rejected" || status === "retry"))
    return true;
  if (agent === "arbiter" && msg.includes("rejected")) return true;
  return false;
}

function isVerifierRejection(e: ActivityEvent): boolean {
  const agent = (e.agent || e.node || "").toLowerCase();
  const eventType = (e.event_type || "").toLowerCase();
  const msg = (e.message || "").toLowerCase();
  if (eventType === "verifier.rejected") return true;
  if (
    agent === "verifier" &&
    (e.status === "error" || msg.includes("unverified"))
  )
    return true;
  return false;
}

function statusClass(status: string | undefined): string {
  switch (status) {
    case "active":
    case "running":
      return "status-running";
    case "done":
    case "success":
    case "completed":
      return "status-success";
    case "error":
    case "failed":
      return "status-error";
    case "retry":
    case "rejected":
      return "status-retry";
    case "idle":
      return "status-idle";
    default:
      return "status-default";
  }
}

export default function ActivityFeed({ events }: ActivityFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.title}>Live Activity Feed</span>
        <span className={styles.eventCount}>{events.length} events</span>
      </div>

      <div ref={feedRef} className={styles.feed}>
        {events.length === 0 ? (
          <div className={styles.empty}>
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <span>Waiting for activity…</span>
          </div>
        ) : (
          events.map((event, i) => {
            const arbiterReject = isArbiterRejection(event);
            const verifierReject = isVerifierRejection(event);
            const rejection = arbiterReject || verifierReject;
            const isDelivery =
              event.event_type === "delivery.completed" ||
              (event.event_type === "workflow.completed" && event.delivery);

            const agentName =
              event.event_type === "delivery.completed"
                ? "Delivery"
                : event.agent || event.node || "System";

            const displayStatus = event.status
              ? event.status.charAt(0).toUpperCase() + event.status.slice(1)
              : "";

            const timeStr = event.timestamp
              ? new Date(event.timestamp).toLocaleTimeString()
              : new Date().toLocaleTimeString();

            const channels =
              event.channels || event.delivery?.channels;

            return (
              <div
                key={i}
                className={`${styles.item} ${rejection ? styles.rejectionAlert : ""} ${isDelivery ? styles.deliveryEvent : ""}`}
              >
                {/* Rejection banner */}
                {verifierReject && (
                  <div
                    className={`${styles.rejectionBanner} ${styles.verifierBanner}`}
                    role="alert"
                  >
                    <strong>VERIFIER HALTED PIPELINE</strong>
                    <span>Signal failed primary-source verification</span>
                  </div>
                )}
                {arbiterReject && !verifierReject && (
                  <div className={styles.rejectionBanner} role="alert">
                    <strong>ARBITER REJECTED ANALYSIS</strong>
                    <span>Pipeline sent back to Scout for re-research</span>
                  </div>
                )}

                {/* Header row */}
                <div className={styles.itemHeader}>
                  <div className={styles.itemAgent}>
                    <span
                      className={`status-indicator ${statusClass(event.status)}`}
                    />
                    <strong className={styles.agentName}>{agentName}</strong>
                    {displayStatus && (
                      <span
                        className={`badge ${statusClass(event.status)}`}
                      >
                        {displayStatus}
                      </span>
                    )}
                  </div>
                  <span className={styles.itemTime}>{timeStr}</span>
                </div>

                {/* Message body */}
                <div className={styles.itemBody}>
                  {event.message || event.summary || ""}
                </div>

                {/* Detail */}
                {event.detail && (
                  <div className={styles.itemDetail}>{event.detail}</div>
                )}

                {/* Delivery channels */}
                {channels && channels.length > 0 && (
                  <div className={styles.deliveryChannels}>
                    {channels.map((ch, ci) => (
                      <span
                        key={ci}
                        className={`delivery-channel-tag ${ch.skipped ? "delivery-skipped" : ch.success ? "delivery-success" : "delivery-failed"}`}
                        title={ch.message || ""}
                      >
                        {ch.channel}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
