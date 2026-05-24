"use client";

import { useEffect, useRef } from "react";
import styles from "./LargeText.module.css";

export default function LargeText() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    el.style.opacity = "0";
    el.style.transform = "translateY(40px)";
    el.style.transition = "all 0.8s cubic-bezier(0.4, 0, 0.2, 1)";

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const target = entry.target as HTMLElement;
            target.style.opacity = "1";
            target.style.transform = "translateY(0)";
            observer.unobserve(target);
          }
        });
      },
      { threshold: 0.1 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={sectionRef} className={styles.section}>
      <h2>
        THE FUTURE OF <span>DECISION MAKING</span>
      </h2>
      <p>
        Experience a platform where every signal is an opportunity, and every
        insight is autonomously generated. Built for the modern enterprise that
        demands speed, accuracy, and strategic depth.
      </p>
    </div>
  );
}
