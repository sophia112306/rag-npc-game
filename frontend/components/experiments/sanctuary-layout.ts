/** Shared by terrain shaping, water geometry and shoreline collision. */
export const COUNCIL_LAKE = {
  x: -7.8,
  z: -9.3,
  rx: 3.4,
  rz: 4.5
};
export function insideCouncilLake(x: number, z: number, margin = 0) {
  return ((x - COUNCIL_LAKE.x) / (COUNCIL_LAKE.rx + margin)) ** 2 + ((z - COUNCIL_LAKE.z) / (COUNCIL_LAKE.rz + margin)) ** 2 < 1;
}
