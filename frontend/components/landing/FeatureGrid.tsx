"use client";

import { useEffect, useRef } from "react";
import styles from "./FeatureGrid.module.css";

const FEATURES = [
  {
    num: "01",
    title: "Autonomous Monitoring",
    desc: "Real-time analysis across news, competitors, and market signals without human intervention.",
  },
  {
    num: "02",
    title: "Agent Orchestration",
    desc: "Specialized agents collaborate asynchronously to validate and reason through complex data.",
  },
  {
    num: "03",
    title: "Strategic Reasoning",
    desc: "Deep analytical frameworks applied to every signal, transforming raw data into actionable intelligence.",
  },
  {
    num: "04",
    title: "Autonomous Execution",
    desc: "Webhook-driven workflows that react to identified opportunities in real-time.",
  },
];

export default function FeatureGrid() {
  const cardsRef = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target as HTMLElement;
            el.style.opacity = "1";
            el.style.transform = "translateY(0)";
            observer.unobserve(el);
          }
        });
      },
      { threshold: 0.1 }
    );

    cardsRef.current.forEach((el) => {
      if (el) {
        el.style.opacity = "0";
        el.style.transform = "translateY(40px)";
        el.style.transition = "all 0.8s cubic-bezier(0.4, 0, 0.2, 1)";
        observer.observe(el);
      }
    });

    return () => observer.disconnect();
  }, []);

  return (
    <div className={styles.grid}>
      {FEATURES.map((feat, i) => (
        <div
          key={feat.num}
          ref={(el) => {
            cardsRef.current[i] = el;
          }}
          className={styles.card}
        >
          <span className={styles.cardNum}>{feat.num}</span>
          <h3 className={styles.cardTitle}>{feat.title}</h3>
          <p className={styles.cardDesc}>{feat.desc}</p>
        </div>
      ))}
    </div>
  );
}
