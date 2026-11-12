import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "鳴霖｜2D 世界探索" };

export default function BabylonTrialPage() {
  redirect("/");
}
