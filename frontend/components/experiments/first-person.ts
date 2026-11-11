import type { PlayerPose, TrialDriver } from "./world";

/** Input stays local and continuous; only world/story actions spend a turn. */
export function createFirstPerson(
  canvas: HTMLCanvasElement,
  driver: TrialDriver,
  onInteract: () => void,
  onToggleJournal: () => void,
) {
  const pose: PlayerPose = { x: 0, z: 8, yaw: 0, pitch: -0.04 };
  const keys = new Set<string>();
  let paused = false;
  let drag: { x: number; y: number } | null = null;
  let bob = 0;
  const isTyping = (target: EventTarget | null) =>
    target instanceof HTMLElement &&
    !!target.closest("input,textarea,button,[contenteditable=true]");
  const down = (event: KeyboardEvent) => {
    if (isTyping(event.target)) return;
    const key = event.key.toLowerCase();
    if (
      [
        "w",
        "a",
        "s",
        "d",
        "arrowup",
        "arrowdown",
        "arrowleft",
        "arrowright",
        "shift",
        " ",
      ].includes(key)
    )
      event.preventDefault();
    keys.add(key);
    if (key === "e" && !event.repeat) onInteract();
    if (key === "tab" && !event.repeat) {
      event.preventDefault();
      onToggleJournal();
    }
  };
  const up = (event: KeyboardEvent) => keys.delete(event.key.toLowerCase());
  const blur = () => {
    keys.clear();
    drag = null;
  };
  const pointerDown = (event: PointerEvent) => {
    if (paused) return;
    canvas.focus();
    drag = { x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  };
  const look = (event: PointerEvent) => {
    if (paused) return;
    const locked = document.pointerLockElement === canvas;
    if (!locked && !drag) return;
    const dx = locked ? event.movementX : event.clientX - drag!.x;
    const dy = locked ? event.movementY : event.clientY - drag!.y;
    pose.yaw += dx * 0.0026;
    pose.pitch = Math.max(-1.05, Math.min(1.05, pose.pitch - dy * 0.0026));
    if (drag) drag = { x: event.clientX, y: event.clientY };
  };
  const release = () => {
    drag = null;
  };
  const context = (event: Event) => event.preventDefault();
  window.addEventListener("keydown", down);
  window.addEventListener("keyup", up);
  window.addEventListener("blur", blur);
  canvas.addEventListener("pointerdown", pointerDown);
  canvas.addEventListener("pointermove", look);
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("contextmenu", context);
  return {
    pose,
    pause(value: boolean) {
      paused = value;
      keys.clear();
      if (value && document.pointerLockElement === canvas)
        void document.exitPointerLock();
    },
    reset(x: number, z: number) {
      Object.assign(pose, { x, z, yaw: 0, pitch: -0.04 });
      keys.clear();
    },
    tick(dt: number) {
      let forward = 0,
        strafe = 0;
      if (!paused) {
        forward =
          Number(keys.has("w") || keys.has("arrowup")) -
          Number(keys.has("s") || keys.has("arrowdown"));
        strafe = Number(keys.has("d")) - Number(keys.has("a"));
        if (keys.has("arrowleft")) pose.yaw -= dt * 1.5;
        if (keys.has("arrowright")) pose.yaw += dt * 1.5;
      }
      const length = Math.hypot(forward, strafe) || 1;
      const speed = ((keys.has("shift") ? 6 : 3.5) * dt) / length;
      const dx =
        (Math.sin(pose.yaw) * forward + Math.cos(pose.yaw) * strafe) * speed;
      const dz =
        (-Math.cos(pose.yaw) * forward + Math.sin(pose.yaw) * strafe) * speed;
      const next = driver.move(pose.x, pose.z, dx, dz);
      const moving = Math.hypot(next.x - pose.x, next.z - pose.z) > 0.001;
      pose.x = next.x;
      pose.z = next.z;
      if (moving) bob += dt * 10;
      driver.setView(pose, moving ? Math.sin(bob) * 0.025 : 0);
    },
    dispose() {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
      canvas.removeEventListener("pointerdown", pointerDown);
      canvas.removeEventListener("pointermove", look);
      canvas.removeEventListener("pointerup", release);
      canvas.removeEventListener("pointercancel", release);
      canvas.removeEventListener("contextmenu", context);
      if (document.pointerLockElement === canvas)
        void document.exitPointerLock();
    },
  };
}
