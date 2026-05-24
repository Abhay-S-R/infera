import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Infera — Autonomous Intelligence Core",
  description:
    "Multi-agent autonomous systems designed for continuous competitive awareness.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
