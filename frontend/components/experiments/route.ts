import { NPC_STOP, RELIC_STOP, START } from "./world";

export type RoutePoint = { x: number; z: number };
export type WalkRoute = { points: RoutePoint[]; distances: number[]; length: number };

const toCouncil = [
  START, { x: 0.1, z: 5.2 }, { x: -0.12, z: 2.2 },
  { x: 0.08, z: -1.4 }, NPC_STOP,
];

const toRelic = [
  NPC_STOP, { x: 0.13, z: -4.35 }, { x: 0.46, z: -5.08 },
  { x: 0.85, z: -5.05 }, { x: 1.5, z: -4.55 }, RELIC_STOP,
];

function smoothPoint(a: RoutePoint, b: RoutePoint, c: RoutePoint, d: RoutePoint, t: number): RoutePoint {
  const t2 = t * t;
  const t3 = t2 * t;
  const coordinate = (p0: number, p1: number, p2: number, p3: number) =>
    0.5 * ((2 * p1) + (-p0 + p2) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
  return { x: coordinate(a.x, b.x, c.x, d.x), z: coordinate(a.z, b.z, c.z, d.z) };
}

function makeRoute(control: RoutePoint[]): WalkRoute {
  const points: RoutePoint[] = [control[0]];
  for (let index = 0; index < control.length - 1; index++) {
    for (let sample = 1; sample <= 12; sample++) {
      points.push(smoothPoint(
        control[Math.max(0, index - 1)], control[index], control[index + 1],
        control[Math.min(control.length - 1, index + 2)], sample / 12
      ));
    }
  }
  const distances = [0];
  for (let index = 1; index < points.length; index++) {
    distances.push(distances[index - 1] + Math.hypot(points[index].x - points[index - 1].x, points[index].z - points[index - 1].z));
  }
  return { points, distances, length: distances[distances.length - 1] };
}

export const COUNCIL_ROUTE = makeRoute(toCouncil);
export const RELIC_ROUTE = makeRoute(toRelic);

export function routePoint(route: WalkRoute, distance: number): RoutePoint {
  const clamped = Math.max(0, Math.min(route.length, distance));
  for (let index = 1; index < route.distances.length; index++) {
    if (clamped <= route.distances[index]) {
      const span = route.distances[index] - route.distances[index - 1];
      const t = span > 0 ? (clamped - route.distances[index - 1]) / span : 0;
      const a = route.points[index - 1];
      const b = route.points[index];
      return { x: a.x + (b.x - a.x) * t, z: a.z + (b.z - a.z) * t };
    }
  }
  return route.points[route.points.length - 1];
}

export function routeHeading(route: WalkRoute, distance: number): number {
  const a = routePoint(route, Math.max(0, distance - 0.05));
  const b = routePoint(route, Math.min(route.length, distance + 0.18));
  return Math.atan2(b.x - a.x, a.z - b.z);
}

export function routeDistanceToPoint(route: WalkRoute, point: RoutePoint): number {
  let nearest = 0;
  let best = Infinity;
  for (let index = 1; index < route.points.length; index++) {
    const a = route.points[index - 1];
    const b = route.points[index];
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const span = dx * dx + dz * dz;
    const t = span ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.z - a.z) * dz) / span)) : 0;
    const x = a.x + dx * t;
    const z = a.z + dz * t;
    const score = (point.x - x) ** 2 + (point.z - z) ** 2;
    if (score < best) {
      best = score;
      nearest = route.distances[index - 1] + Math.sqrt(span) * t;
    }
  }
  return nearest;
}

export function easeAngle(current: number, target: number, strength: number) {
  const delta = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + delta * Math.min(1, strength);
}

