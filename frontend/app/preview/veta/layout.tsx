import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "維塔 · 角色畫面",
  description: "沉睡巨龍維塔的角色畫面。",
};

export default function VetaPreviewLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
