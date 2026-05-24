"use client";

import { useEffect, useRef } from "react";
import styles from "./Hero.module.css";

export default function Hero() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleEnded = () => {
      video.classList.add(styles.faded);
    };

    video.addEventListener("ended", handleEnded);

    // Ensure video plays (browsers sometimes block autoplay)
    video.play().catch(() => {
      /* autoplay blocked — silent fallback */
    });

    return () => {
      video.removeEventListener("ended", handleEnded);
    };
  }, []);

  return (
    <section className={styles.hero}>
      <video
        ref={videoRef}
        className={styles.video}
        autoPlay
        muted
        playsInline
      >
        <source src="/VideoProject.mp4" type="video/mp4" />
      </video>

      <div className={styles.overlay} />

      <div className={styles.content}>
        <h1 className={styles.title}>
          INTELLIGENCE <br /> <span>AT SCALE.</span>
        </h1>
        <p className={styles.subtitle}>
          Multi-agent autonomous systems designed for continuous competitive
          awareness.
        </p>

        <div className={styles.scrollIndicator}>
          <div className={styles.mouse} />
          <span>SCROLL TO EXPLORE</span>
        </div>
      </div>
    </section>
  );
}
