import type { AssetKind, WorldScene } from "../../lib/game-api";
import { COUNCIL_LAKE } from "./sanctuary-layout";

export const EYE_HEIGHT = 1.68;
export type PlayerPose = { x: number; z: number; yaw: number; pitch: number };
export type GroundTarget = { x: number; z: number; interaction?: boolean };
export type TrialDriver = {
  pickGround: (clientX: number, clientY: number) => GroundTarget | null;
  setWorld: (world: WorldScene) => Promise<void>;
  setAsset: (kind: AssetKind, url: string) => Promise<void>;
  setView: (pose: PlayerPose, eyeBob: number) => void;
  move: (
    x: number,
    z: number,
    dx: number,
    dz: number,
  ) => { x: number; z: number };
  render: () => void;
  resize: () => void;
  dispose: () => void;
};

/** Shared by terrain vertices, model placement, water and camera feet. */
export function terrainHeight(x: number, z: number, world: WorldScene): number {
  const seed = (world.config.seed % 500) / 31;
  const corridor = Math.min(1, Math.max(0, (Math.abs(x) - 3) / 8));
  const waves =
    Math.sin(x * 0.15 + seed) * Math.cos(z * 0.12 - seed) +
    Math.sin(z * 0.21 + x * 0.08) * 0.35;
  const amplitude =
    world.config.terrain === "dunes"
      ? 2.9
      : world.config.terrain === "rocky"
        ? 3.8
        : 1.8;
  const rim = Math.min(1, Math.max(0, (Math.hypot(x, z + 7) - 42) / 32));
  const canyon =
    world.scene_id === "liuchen_valley"
      ? Math.exp(-Math.pow((x + 20 + Math.sin(z * 0.055) * 4) / 4, 4)) * 8
      : 0;
  const height = (
    waves * amplitude * corridor +
    rim * rim * (world.config.terrain === "rocky" ? 5 : 1.7) -
    canyon
  );
  if (world.scene_id !== "minglin") return height;
  const courtyard = Math.min(1, Math.max(0, (Math.hypot(x, z + 8) - 20) / 14));
  const lakeRadius = Math.hypot(
    (x - COUNCIL_LAKE.x) / COUNCIL_LAKE.rx,
    (z - COUNCIL_LAKE.z) / COUNCIL_LAKE.rz,
  );
  return height * courtyard - Math.max(0, 1 - lakeRadius) * .35;
}
