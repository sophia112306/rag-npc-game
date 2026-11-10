import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "鳴霖 · 維達利亞",
  description: "與初代精靈維達利亞對話，踏入鳴霖的平衡議會。",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
