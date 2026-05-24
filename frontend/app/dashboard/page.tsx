"use client";

import { useState, useCallback } from "react";
import Pipeline, { type PipelineStatus } from "@/components/dashboard/Pipeline";
import AnalyzeForm from "@/components/dashboard/AnalyzeForm";
import HealthPanel from "@/components/dashboard/HealthPanel";
import CompetitorPanel from "@/components/dashboard/CompetitorPanel";
import ActivityFeed, {
  type ActivityEvent,
} from "@/components/dashboard/ActivityFeed";
import styles from "./page.module.css";

export default function DashboardPage() {
  const [pipelineStatuses, setPipelineStatuses] = useState<PipelineStatus>({});
  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([]);

  const addActivityEvent = useCallback((event: Record<string, unknown>) => {
    setActivityEvents((prev) => {
      const next = [...prev, event as ActivityEvent];
      return next.length > 100 ? next.slice(-100) : next;
    });
  }, []);

  // This will be wired to the WebSocket in Phase 6
  // For now, pipeline status updates come from activity events
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

  // Pipeline and activity handlers are exposed via props/context.
  // WebSocket integration will be wired in Phase 6.

  return (
    <div className={styles.page}>
      {/* Row 1: Analyze Form + Pipeline */}
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
