import type { Metadata } from "next";
import TrialExperience from "../../../components/experiments/TrialExperience";

export const metadata: Metadata = { title: "Babylon.js 3D 試玩｜鳴霖" };

export default function BabylonTrialPage() {
  return <TrialExperience />;
}
