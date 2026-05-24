"use client";

import { useRouter } from "next/navigation";
import styles from "./CTAButton.module.css";

export default function CTAButton() {
  const router = useRouter();

  return (
    <section className={styles.section}>
      <button
        className={styles.button}
        onClick={() => router.push("/dashboard")}
      >
        LAUNCH SYSTEM
      </button>
    </section>
  );
}
