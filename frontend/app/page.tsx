import Hero from "@/components/landing/Hero";
import FeatureGrid from "@/components/landing/FeatureGrid";
import LargeText from "@/components/landing/LargeText";
import CTAButton from "@/components/landing/CTAButton";
import styles from "./page.module.css";

export default function LandingPage() {
  return (
    <main>
      <Hero />

      <section className={styles.scrollContent}>
        <div className={styles.container}>
          <FeatureGrid />
          <LargeText />
        </div>
      </section>

      <CTAButton />

      <div className={styles.bottomGlow} />
    </main>
  );
}
