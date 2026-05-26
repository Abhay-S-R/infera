"use client";

import { useState, useCallback } from "react";
import Pipeline, { type PipelineStatus } from "@/components/dashboard/Pipeline";
import AnalyzeForm from "@/components/dashboard/AnalyzeForm";
import HealthPanel from "@/components/dashboard/HealthPanel";
import CompetitorPanel from "@/components/dashboard/CompetitorPanel";
import ActivityFeed, {
  type ActivityEvent,
} from "@/components/dashboard/ActivityFeed";
import { useWebSocket } from "@/hooks/useWebSocket";
import styles from "./page.module.css";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8000";

export default function DashboardPage() {
  const [pipelineStatuses, setPipelineStatuses] = useState<PipelineStatus>({});
  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([]);

  const addActivityEvent = useCallback((event: Record<string, unknown>) => {
    setActivityEvents((prev) => {
      const next = [...prev, event as ActivityEvent];
      return next.length > 100 ? next.slice(-100) : next;
    });
  }, []);

  const handlePipelineUpdate = useCallback(
    (node: string, status: PipelineStatus[string]) => {
      setPipelineStatuses((prev) => {
        // Reset all nodes when sentinel starts (new run)
        if (
          node === "sentinel" &&
          (status === "running" || status === "active")
        ) {
          return { sentinel: status };
        }
        return { ...prev, [node]: status };
      });
    },
    []
  );

  // Handle incoming WebSocket messages → dispatch to activity feed + pipeline
  const handleWsMessage = useCallback(
    (payload: Record<string, unknown>) => {
      addActivityEvent(payload);

      const agentName = (payload.agent || payload.node) as string | undefined;
      const status = payload.status as string | undefined;
      const eventType = payload.event_type as string | undefined;

      // Update pipeline node status
      if (agentName && status) {
        handlePipelineUpdate(
          agentName.toLowerCase(),
          status as PipelineStatus[string]
        );
      }

      // Special case: verifier rejection → mark verifier as error
      if (eventType === "verifier.rejected") {
        handlePipelineUpdate("verifier", "error");
      }
    },
    [addActivityEvent, handlePipelineUpdate]
  );

  // Connect to the WebSocket activity stream
  const { status: wsStatus } = useWebSocket({
    url: `${WS_URL}/ws/activity`,
    onMessage: handleWsMessage,
  });

  return (
    <div className={styles.page}>
      {/* Connection status indicator */}
      {wsStatus === "disconnected" && activityEvents.length > 0 && (
        <div className={styles.wsWarning}>
          <span className={styles.wsWarningDot} />
          WebSocket disconnected — reconnecting…
        </div>
      )}

      {/* Row 1: Analyze Form */}
      <section className={styles.topSection}>
        <div className={styles.formColumn}>
          <AnalyzeForm onActivityEvent={addActivityEvent} />
        </div>
      </section>

      {/* Pipeline */}
      <Pipeline statuses={pipelineStatuses} />

      {/* Row 2: Health + Competitors */}
      <section className={styles.twoColumn}>
        <HealthPanel />
        <CompetitorPanel />
      </section>

      {/* Row 3: Activity Feed */}
      <ActivityFeed events={activityEvents} />
    </div>
  );
}
