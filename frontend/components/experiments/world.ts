export const START = { x: 0, z: 8 };
export const NPC = { x: 0, z: -8 };
export const NPC_STOP = { x: 0, z: -3.8 };
export const RELIC = { x: 2.8, z: -5.8 };
export const RELIC_STOP = { x: 2.0, z: -3.6 };
export const EYE_HEIGHT = 1.65;

export const trees = [
  [-8, 8, 1.2], [-5.7, 4, 1.0], [-8.4, -1, 1.3], [-6.4, -7, 1.2],
  [7, 7, 1.2], [5.7, 3, 1.0], [8.2, -2, 1.4], [6.7, -9, 1.1],
] as const;

export const pillars = [
  [-4.3, -7.2, 2.9], [4.3, -7.2, 2.9], [-5.1, -3.8, 1.8], [5.1, -3.8, 1.8],
] as const;

export type Pick = { kind: "ground"; x: number; z: number } | { kind: "npc" | "relic" } | null;
export type TrialDriver = {
  setView: (x: number, z: number, yaw: number, pitch: number, eyeBob?: number) => void;
  setTalking?: (talking: boolean) => void;
  pick: (clientX: number, clientY: number) => Pick;
  render: () => void;
  resize: () => void;
  dispose: () => void;
};

export function clampDestination(x: number, z: number) {
  return { x: Math.max(-3.25, Math.min(3.25, x)), z: Math.max(-6.1, Math.min(8.5, z)) };
}

export function distance(a: { x: number; z: number }, b: { x: number; z: number }) {
  return Math.hypot(a.x - b.x, a.z - b.z);
}
