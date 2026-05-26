"use client";

import { useEffect, useRef, useCallback, useState } from "react";

interface UseWebSocketOptions {
  /** WebSocket URL, e.g. ws://127.0.0.1:8000/ws/activity */
  url: string;
  /** Called with each parsed message payload */
  onMessage: (payload: Record<string, unknown>) => void;
  /** Delay (ms) before reconnect after close/error. Default: 5000 */
  reconnectDelay?: number;
  /** Whether the hook should connect. Default: true */
  enabled?: boolean;
}

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/**
 * Custom hook for a reconnecting WebSocket connection.
 *
 * Handles:
 * - Auto-connect on mount
 * - Auto-reconnect with configurable delay
 * - Nested payload extraction: { type: "activity", payload: {...} }
 * - Clean teardown on unmount
 */
export function useWebSocket({
  url,
  onMessage,
  reconnectDelay = 5000,
  enabled = true,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  // Keep the callback reference fresh without causing reconnects
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    try {
      setStatus("connecting");
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        setStatus("connected");
        onMessageRef.current({
          agent: "System",
          status: "success",
          message: "Connected to activity stream",
          timestamp: new Date().toISOString(),
        });
      };

      socket.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as Record<
            string,
            unknown
          >;

          // Handle nested format: { type: "activity", payload: {...} }
          let payload = data;
          if (
            data.type === "activity" &&
            data.payload &&
            typeof data.payload === "object"
          ) {
            payload = data.payload as Record<string, unknown>;
          }

          const eventType =
            (data.type as string) || (payload.event_type as string) || "";
          onMessageRef.current({ ...payload, event_type: eventType });
        } catch {
          // Silently drop unparseable messages
        }
      };

      socket.onclose = () => {
        setStatus("disconnected");
        wsRef.current = null;
        // Auto-reconnect after delay
        reconnectTimer.current = setTimeout(connect, reconnectDelay);
      };

      socket.onerror = () => {
        // onclose will fire after onerror, which triggers reconnect
        socket.close();
      };
    } catch {
      setStatus("disconnected");
      reconnectTimer.current = setTimeout(connect, reconnectDelay);
    }
  }, [url, reconnectDelay]);

  useEffect(() => {
    if (!enabled) return;

    connect();

    return () => {
      // Clean teardown
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      if (wsRef.current) {
        // Prevent reconnect on intentional close
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setStatus("disconnected");
    };
  }, [connect, enabled]);

  return { status };
}
