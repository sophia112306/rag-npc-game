import type { GroundTarget, PlayerPose, TrialDriver } from "./world";

export type MoveDirection = "forward" | "backward" | "left" | "right";
const moveCodes = {
  forward: "KeyW",
  backward: "KeyS",
  left: "KeyA",
  right: "KeyD",
};
const keyFallback: Record<string, string> = {
  w: "KeyW",
  a: "KeyA",
  s: "KeyS",
  d: "KeyD",
  e: "KeyE",
  shift: "ShiftLeft",
  tab: "Tab",
  arrowup: "ArrowUp",
  arrowdown: "ArrowDown",
  arrowleft: "ArrowLeft",
  arrowright: "ArrowRight",
};

/** Physical key codes work with Chinese IMEs; click, keyboard and touch share movement. */
export function createFirstPerson(
  canvas: HTMLCanvasElement,
  driver: TrialDriver,
  onInteract: () => void,
  onToggleJournal: () => void,
  onNotice: (message: string) => void = () => {},
) {
  const pose: PlayerPose = { x: 0, z: 8, yaw: 0, pitch: -0.04 };
  const keys = new Set<string>();
  let paused = false,
    bob = 0;
  let goal: GroundTarget | null = null;
  let drag: { x: number; y: number; travel: number } | null = null;
  const isTyping = (target: EventTarget | null) =>
    target instanceof HTMLElement &&
    !!target.closest("input,textarea,[contenteditable=true],[role=textbox]");
  const focus = () => canvas.focus({ preventScroll: true });
  const down = (event: KeyboardEvent) => {
    if (isTyping(event.target) || paused) return;
    const code = event.code || keyFallback[event.key.toLowerCase()];
    if (!code) return;
    if (
      [
        "KeyW",
        "KeyA",
        "KeyS",
        "KeyD",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
      ].includes(code)
    ) {
      event.preventDefault();
      goal = null;
      focus();
    }
    keys.add(code);
    if (code === "KeyE" && !event.repeat) {
      event.preventDefault();
      onInteract();
    }
    if (code === "Tab" && !event.repeat) {
      event.preventDefault();
      onToggleJournal();
    }
  };
  const up = (event: KeyboardEvent) =>
    keys.delete(event.code || keyFallback[event.key.toLowerCase()]);
  const blur = () => {
    keys.clear();
    drag = null;
    goal = null;
  };
  const pointerDown = (event: PointerEvent) => {
    if (paused || event.button !== 0) return;
    event.preventDefault();
    focus();
    drag = { x: event.clientX, y: event.clientY, travel: 0 };
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
    if (drag)
      drag = {
        x: event.clientX,
        y: event.clientY,
        travel: drag.travel + Math.hypot(dx, dy),
      };
  };
  const pointerUp = (event: PointerEvent) => {
    const click = drag && drag.travel < 6;
    drag = null;
    if (!click || paused) return;
    const target = driver.pickGround(event.clientX, event.clientY);
    if (!target) {
      onNotice("請點石板路或可行走的地面。按住滑鼠拖曳可以環視。");
      return;
    }
    const distance = Math.hypot(target.x - pose.x, target.z - pose.z);
    if (target.interaction && distance <= 3.6) {
      onInteract();
      return;
    }
    if (target.interaction) {
      const stop = 2.7 / Math.max(distance, 0.001);
      target.x += (pose.x - target.x) * stop;
      target.z += (pose.z - target.z) * stop;
    }
    goal = target;
    onNotice(
      target.interaction
        ? "正走向交談地點…"
        : "正在走向你點選的位置；WASD 可隨時接手。",
    );
  };
  const cancel = () => {
    drag = null;
  };
  const context = (event: Event) => event.preventDefault();
  window.addEventListener("keydown", down);
  window.addEventListener("keyup", up);
  window.addEventListener("blur", blur);
  canvas.addEventListener("pointerdown", pointerDown);
  canvas.addEventListener("pointermove", look);
  canvas.addEventListener("pointerup", pointerUp);
  canvas.addEventListener("pointercancel", cancel);
  canvas.addEventListener("contextmenu", context);
  return {
    pose,
    setMove(direction: MoveDirection, pressed: boolean) {
      goal = null;
      if (pressed && !paused) {
        keys.add(moveCodes[direction]);
        focus();
      } else keys.delete(moveCodes[direction]);
    },
    pause(value: boolean) {
      const returning = paused && !value;
      paused = value;
      blur();
      if (returning) focus();
      if (value && document.pointerLockElement === canvas)
        void document.exitPointerLock();
    },
    reset(x: number, z: number) {
      Object.assign(pose, { x, z, yaw: 0, pitch: -0.04 });
      blur();
      focus();
    },
    tick(dt: number) {
      let forward = 0,
        strafe = 0,
        dx = 0,
        dz = 0;
      if (!paused) {
        forward =
          Number(keys.has("KeyW") || keys.has("ArrowUp")) -
          Number(keys.has("KeyS") || keys.has("ArrowDown"));
        strafe = Number(keys.has("KeyD")) - Number(keys.has("KeyA"));
        if (keys.has("ArrowLeft")) pose.yaw -= dt * 1.5;
        if (keys.has("ArrowRight")) pose.yaw += dt * 1.5;
        const speed =
          (keys.has("ShiftLeft") || keys.has("ShiftRight") ? 6 : 3.5) * dt;
        if (goal && !forward && !strafe) {
          const distance = Math.hypot(goal.x - pose.x, goal.z - pose.z);
          if (distance < (goal.interaction ? 0.45 : 0.18)) {
            const interact = goal.interaction;
            goal = null;
            onNotice("已抵達。拖曳環視，或繼續點選地面探索。");
            if (interact) onInteract();
          } else {
            const heading = Math.atan2(goal.x - pose.x, pose.z - goal.z);
            pose.yaw +=
              Math.atan2(
                Math.sin(heading - pose.yaw),
                Math.cos(heading - pose.yaw),
              ) * Math.min(1, dt * 8);
            const step = Math.min(speed, distance);
            dx = ((goal.x - pose.x) / distance) * step;
            dz = ((goal.z - pose.z) / distance) * step;
          }
        } else {
          const length = Math.hypot(forward, strafe) || 1;
          dx =
            ((Math.sin(pose.yaw) * forward + Math.cos(pose.yaw) * strafe) *
              speed) /
            length;
          dz =
            ((-Math.cos(pose.yaw) * forward + Math.sin(pose.yaw) * strafe) *
              speed) /
            length;
        }
      }
      const next = driver.move(pose.x, pose.z, dx, dz);
      const moving = Math.hypot(next.x - pose.x, next.z - pose.z) > 0.001;
      if (goal && !moving && Math.hypot(dx, dz) > 0.01) {
        goal = null;
        onNotice("前方有水岸或物件，請換個位置點選。也可以使用 WASD 移動。");
      }
      pose.x = next.x;
      pose.z = next.z;
      if (moving) bob += dt * 10;
      driver.setView(pose, moving ? Math.sin(bob) * 0.025 : 0);
    },
    dispose() {
      blur();
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
      canvas.removeEventListener("pointerdown", pointerDown);
      canvas.removeEventListener("pointermove", look);
      canvas.removeEventListener("pointerup", pointerUp);
      canvas.removeEventListener("pointercancel", cancel);
      canvas.removeEventListener("contextmenu", context);
      if (document.pointerLockElement === canvas)
        void document.exitPointerLock();
    },
  };
}
