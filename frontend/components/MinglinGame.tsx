"use client";

import { useEffect, useRef } from "react";
import type Phaser from "phaser";

export type GameCommand = { dx: number; dy: number };
export const MIN_MAP_ZOOM = 1;
export const MAX_MAP_ZOOM = 2.2;
export const MAP_ZOOM_STEP = 0.2;
type ZoomCommand = { kind: "step"; amount: number } | { kind: "reset" };

export function movePlayer(command: GameCommand) {
  window.dispatchEvent(new CustomEvent<GameCommand>("minglin:move", { detail: command }));
}

export function turnPlayer(steps: number) {
  window.dispatchEvent(new CustomEvent<number>("minglin:turn", { detail: steps }));
}

export function zoomMap(command: ZoomCommand) {
  window.dispatchEvent(new CustomEvent<ZoomCommand>("minglin:zoom", { detail: command }));
}

export function interactWithNpc() {
  window.dispatchEvent(new Event("minglin:interact"));
}

type Props = {
  paused: boolean;
  onNearChange: (near: boolean) => void;
  onInteract: () => void;
  onZoomChange: (zoom: number) => void;
};

type Destination = { x: number; y: number; talkAfterArrival: boolean };
type PolygonObject = { x: number; y: number; polygon?: { x: number; y: number }[] };
const directions = [
  { texture: "traveler-back", flipX: false },
  { texture: "traveler", flipX: false },
  { texture: "traveler-side", flipX: false },
  { texture: "traveler-front-quarter", flipX: false },
  { texture: "traveler-front", flipX: false },
  { texture: "traveler-front-quarter", flipX: true },
  { texture: "traveler-side", flipX: true },
  { texture: "traveler", flipX: true },
] as const;

export default function MinglinGame({ paused, onNearChange, onInteract, onZoomChange }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  const nearRef = useRef(onNearChange);
  const interactRef = useRef(onInteract);
  const zoomRef = useRef(onZoomChange);

  useEffect(() => { pausedRef.current = paused; }, [paused]);
  useEffect(() => { nearRef.current = onNearChange; }, [onNearChange]);
  useEffect(() => { interactRef.current = onInteract; }, [onInteract]);
  useEffect(() => { zoomRef.current = onZoomChange; }, [onZoomChange]);

  useEffect(() => {
    let game: Phaser.Game | undefined;
    let cancelled = false;

    void import("phaser").then(({ default: PhaserEngine }) => {
      if (cancelled || !mountRef.current) return;

      class MinglinScene extends PhaserEngine.Scene {
        private player?: Phaser.GameObjects.Image;
        private playerShadow?: Phaser.GameObjects.Ellipse;
        private npc?: Phaser.GameObjects.Image;
        private walkable?: Phaser.Geom.Polygon;
        private destination?: Destination;
        private cursorKeys?: Phaser.Types.Input.Keyboard.CursorKeys;
        private movementKeys?: Record<string, Phaser.Input.Keyboard.Key>;
        private turnKeys?: Record<string, Phaser.Input.Keyboard.Key>;
        private facing = 1;
        private wasNear = false;
        private pinchStart?: { distance: number; zoom: number };
        private touchStarts = new Map<number, { x: number; y: number }>();
        private suppressTouchTap = false;

        constructor() { super("minglin"); }

        preload() {
          this.load.tilemapTiledJSON("minglin-map", "/game/minglin.tmj");
          this.load.image("minglin-forest", "/game/forest-council.png");
          this.load.image("traveler", "/game/traveler.png");
          this.load.image("traveler-back", "/game/traveler-back.png");
          this.load.image("traveler-front", "/game/traveler-front.png");
          this.load.image("traveler-front-quarter", "/game/traveler-front-quarter.png");
          this.load.image("traveler-side", "/game/traveler-side.png");
          this.load.image("vidalia", "/game/vidalia-cutout.png");
        }

        create() {
          this.cameras.main.setBounds(0, 0, 1672, 941);
          zoomRef.current(MIN_MAP_ZOOM);
          this.add.image(0, 0, "minglin-forest").setOrigin(0).setDisplaySize(1672, 941).setDepth(0);

          const map = this.make.tilemap({ key: "minglin-map" });
          const path = map.getObjectLayer("Walkable")?.objects[0] as PolygonObject | undefined;
          if (path?.polygon) {
            this.walkable = new PhaserEngine.Geom.Polygon(
              path.polygon.map((point) => ({ x: path.x + point.x, y: path.y + point.y }))
            );
          }

          const actors = map.getObjectLayer("Actors")?.objects;
          const spawn = actors?.find((item) => item.name === "player_spawn");
          const vidalia = actors?.find((item) => item.name === "vidalia");
          const playerX = spawn?.x ?? 835;
          const playerY = spawn?.y ?? 535;
          const npcX = vidalia?.x ?? 1055;
          const npcY = vidalia?.y ?? 375;

          this.playerShadow = this.add.ellipse(playerX, playerY + 3, 38, 13, 0x151a10, 0.42).setDepth(playerY - 1);
          this.player = this.add.image(playerX, playerY, "traveler").setOrigin(0.5, 1).setDisplaySize(56, 100).setDepth(playerY);
          this.add.ellipse(npcX, npcY + 4, 40, 12, 0x232119, 0.35).setDepth(npcY - 1);
          this.npc = this.add.image(npcX, npcY, "vidalia").setOrigin(0.5, 1).setDisplaySize(52, 132).setDepth(npcY);

          const marker = this.add.text(npcX, npcY - 149, "◇", {
            color: "#ffe496", fontSize: "31px", fontFamily: "Georgia, serif",
            stroke: "#3f3519", strokeThickness: 4,
          }).setOrigin(0.5).setDepth(npcY + 1);
          this.tweens.add({ targets: marker, y: npcY - 155, duration: 1150, yoyo: true, repeat: -1, ease: "Sine.InOut" });

          this.cursorKeys = this.input.keyboard?.createCursorKeys();
          this.movementKeys = this.input.keyboard?.addKeys("W,A,S,D") as Record<string, Phaser.Input.Keyboard.Key> | undefined;
          this.turnKeys = this.input.keyboard?.addKeys("Q,R") as Record<string, Phaser.Input.Keyboard.Key> | undefined;
          this.input.mouse?.disableContextMenu();

          const talk = () => {
            if (!pausedRef.current && this.isNearNpc()) interactRef.current();
          };
          const touchMove = (event: Event) => {
            if (pausedRef.current) return;
            this.destination = undefined;
            const { dx, dy } = (event as CustomEvent<GameCommand>).detail;
            this.tryMove(dx * 36, dy * 36);
          };
          const touchTurn = (event: Event) => {
            if (pausedRef.current) return;
            this.destination = undefined;
            this.setFacing(this.facing + (event as CustomEvent<number>).detail);
          };
          const zoomControl = (event: Event) => {
            const command = (event as CustomEvent<ZoomCommand>).detail;
            this.setMapZoom(command.kind === "reset" ? MIN_MAP_ZOOM : this.cameras.main.zoom + command.amount);
          };
          const wheelZoom = (pointer: Phaser.Input.Pointer, _over: unknown, _dx: number, dy: number) => {
            if (dy === 0) return;
            this.setMapZoom(this.cameras.main.zoom * Math.exp(-dy * 0.0015), pointer.x, pointer.y);
          };
          const activatePointer = (pointer: Phaser.Input.Pointer) => {
            if (pointer.wasTouch) {
              this.touchStarts.set(pointer.id, { x: pointer.x, y: pointer.y });
              this.updatePinch();
              return;
            }
            handleMapPointer(pointer);
          };
          const movePointer = (pointer: Phaser.Input.Pointer) => {
            if (pointer.wasTouch) this.updatePinch();
          };
          const releasePointer = (pointer: Phaser.Input.Pointer) => {
            if (!pointer.wasTouch) return;
            const start = this.touchStarts.get(pointer.id);
            this.touchStarts.delete(pointer.id);
            if (!this.suppressTouchTap && start &&
              PhaserEngine.Math.Distance.Between(start.x, start.y, pointer.x, pointer.y) < 12) {
              handleMapPointer(pointer);
            }
            if (!this.touchPointers().length) {
              this.pinchStart = undefined;
              this.suppressTouchTap = false;
            }
          };
          const handleMapPointer = (pointer: Phaser.Input.Pointer) => {
            if (pausedRef.current || !this.npc || !this.player) return;
            const world = this.worldAt(pointer.x, pointer.y);
            const x = world.x;
            const y = world.y;
            if (pointer.rightButtonDown()) {
              this.destination = undefined;
              this.faceToward(x - this.player.x, y - this.player.y);
              return;
            }
            const clickedNpc = Math.abs(x - this.npc.x) < 64 && y > this.npc.y - 150 && y < this.npc.y + 23;
            if (clickedNpc) {
              if (this.isNearNpc()) {
                this.faceToward(this.npc.x - this.player.x, this.npc.y - this.player.y);
                interactRef.current();
              } else {
                this.destination = { x: this.npc.x - 78, y: this.npc.y + 61, talkAfterArrival: true };
                this.faceToward(this.destination.x - this.player.x, this.destination.y - this.player.y);
              }
            } else if (this.canWalk(x, y)) {
              this.destination = { x, y, talkAfterArrival: false };
              this.faceToward(x - this.player.x, y - this.player.y);
            }
          };

          this.input.keyboard?.on("keydown-E", talk);
          this.input.on("pointerdown", activatePointer);
          this.input.on("pointermove", movePointer);
          this.input.on("pointerup", releasePointer);
          this.input.on("pointerupoutside", releasePointer);
          this.input.on("wheel", wheelZoom);
          window.addEventListener("minglin:move", touchMove);
          window.addEventListener("minglin:turn", touchTurn);
          window.addEventListener("minglin:zoom", zoomControl);
          window.addEventListener("minglin:interact", talk);
          this.events.once("shutdown", () => {
            this.input.keyboard?.off("keydown-E", talk);
            this.input.off("pointerdown", activatePointer);
            this.input.off("pointermove", movePointer);
            this.input.off("pointerup", releasePointer);
            this.input.off("pointerupoutside", releasePointer);
            this.input.off("wheel", wheelZoom);
            window.removeEventListener("minglin:move", touchMove);
            window.removeEventListener("minglin:turn", touchTurn);
            window.removeEventListener("minglin:zoom", zoomControl);
            window.removeEventListener("minglin:interact", talk);
          });
          this.refreshNearState();
        }

        private canWalk(x: number, y: number) {
          return !!this.walkable && PhaserEngine.Geom.Polygon.Contains(this.walkable, x, y);
        }

        private worldAt(x: number, y: number) {
          const camera = this.cameras.main;
          return {
            x: camera.scrollX + camera.width / 2 + (x - camera.width / 2) / camera.zoom,
            y: camera.scrollY + camera.height / 2 + (y - camera.height / 2) / camera.zoom,
          };
        }

        private setMapZoom(value: number, x = this.cameras.main.width / 2, y = this.cameras.main.height / 2) {
          const camera = this.cameras.main;
          const next = Math.round(PhaserEngine.Math.Clamp(value, MIN_MAP_ZOOM, MAX_MAP_ZOOM) * 100) / 100;
          if (next === camera.zoom) return;
          const before = this.worldAt(x, y);
          camera.setZoom(next);
          camera.setScroll(
            camera.clampX(before.x - camera.width / 2 - (x - camera.width / 2) / next),
            camera.clampY(before.y - camera.height / 2 - (y - camera.height / 2) / next)
          );
          this.keepPlayerVisible();
          zoomRef.current(next);
        }

        private keepPlayerVisible() {
          if (!this.player) return;
          const camera = this.cameras.main;
          if (camera.zoom <= MIN_MAP_ZOOM) return;
          const halfWidth = camera.width / (2 * camera.zoom);
          const halfHeight = camera.height / (2 * camera.zoom);
          const centerX = camera.scrollX + camera.width / 2;
          const centerY = camera.scrollY + camera.height / 2;
          const left = centerX - halfWidth + 150 / camera.zoom;
          const right = centerX + halfWidth - 150 / camera.zoom;
          const top = centerY - halfHeight + 100 + 40 / camera.zoom;
          const bottom = centerY + halfHeight - 230 / camera.zoom;
          const shiftX = this.player.x < left ? this.player.x - left : this.player.x > right ? this.player.x - right : 0;
          const shiftY = this.player.y < top ? this.player.y - top : this.player.y > bottom ? this.player.y - bottom : 0;
          if (shiftX || shiftY) {
            camera.setScroll(camera.clampX(camera.scrollX + shiftX), camera.clampY(camera.scrollY + shiftY));
          }
        }

        private touchPointers() {
          return [this.input.pointer1, this.input.pointer2].filter((pointer): pointer is Phaser.Input.Pointer =>
            !!pointer && pointer.isDown && pointer.wasTouch);
        }

        private updatePinch() {
          const pointers = this.touchPointers();
          if (pointers.length !== 2) return;
          const [first, second] = pointers;
          const distance = PhaserEngine.Math.Distance.Between(first.x, first.y, second.x, second.y);
          if (!this.pinchStart) {
            this.pinchStart = { distance, zoom: this.cameras.main.zoom };
            this.destination = undefined;
            this.suppressTouchTap = true;
          } else if (this.pinchStart.distance > 0) {
            this.setMapZoom(this.pinchStart.zoom * distance / this.pinchStart.distance,
              (first.x + second.x) / 2, (first.y + second.y) / 2);
          }
        }

        private setFacing(index: number) {
          if (!this.player) return;
          const nextFacing = (index + directions.length) % directions.length;
          if (nextFacing === this.facing) return;
          this.facing = nextFacing;
          const direction = directions[this.facing];
          this.player.setTexture(direction.texture).setDisplaySize(56, 100).setFlipX(direction.flipX);
        }

        private faceToward(dx: number, dy: number) {
          if (Math.abs(dx) + Math.abs(dy) < 0.001) return;
          const angle = Math.atan2(dx, -dy);
          this.setFacing(Math.round(angle / (Math.PI / 4)));
        }

        private isNearNpc() {
          return !!this.player && !!this.npc &&
            PhaserEngine.Math.Distance.Between(this.player.x, this.player.y, this.npc.x, this.npc.y) < 125;
        }

        private refreshNearState() {
          const near = this.isNearNpc();
          if (near !== this.wasNear) {
            this.wasNear = near;
            nearRef.current(near);
          }
        }

        private tryMove(dx: number, dy: number) {
          if (!this.player || !this.playerShadow || !this.npc || pausedRef.current) return false;
          this.faceToward(dx, dy);
          const nextX = this.player.x + dx;
          const nextY = this.player.y + dy;
          if (!this.canWalk(nextX, nextY)) return false;
          if (PhaserEngine.Math.Distance.Between(nextX, nextY, this.npc.x, this.npc.y) < 31) return false;
          this.player.setPosition(nextX, nextY).setDepth(nextY);
          this.playerShadow.setPosition(nextX, nextY + 3).setDepth(nextY - 1);
          this.keepPlayerVisible();
          this.refreshNearState();
          return true;
        }

        update(_time: number, delta: number) {
          if (pausedRef.current || !this.player) return;
          if (this.turnKeys && PhaserEngine.Input.Keyboard.JustDown(this.turnKeys.Q)) {
            this.destination = undefined;
            this.setFacing(this.facing - 1);
          }
          if (this.turnKeys && PhaserEngine.Input.Keyboard.JustDown(this.turnKeys.R)) {
            this.destination = undefined;
            this.setFacing(this.facing + 1);
          }
          const keys = this.movementKeys;
          const arrows = this.cursorKeys;
          const dx = keys && arrows ? Number(arrows.right.isDown || keys.D.isDown) - Number(arrows.left.isDown || keys.A.isDown) : 0;
          const dy = keys && arrows ? Number(arrows.down.isDown || keys.S.isDown) - Number(arrows.up.isDown || keys.W.isDown) : 0;
          const speed = Math.min(delta, 40) * 0.2;

          if (dx || dy) {
            this.destination = undefined;
            const factor = dx && dy ? Math.SQRT1_2 : 1;
            this.tryMove(dx * speed * factor, dy * speed * factor);
            return;
          }

          if (!this.destination) return;
          const distance = PhaserEngine.Math.Distance.Between(this.player.x, this.player.y, this.destination.x, this.destination.y);
          if (distance <= 5) {
            const shouldTalk = this.destination.talkAfterArrival && this.isNearNpc();
            this.destination = undefined;
            if (shouldTalk) interactRef.current();
            return;
          }

          const step = Math.min(distance, speed);
          const moved = this.tryMove(
            (this.destination.x - this.player.x) / distance * step,
            (this.destination.y - this.player.y) / distance * step
          );
          if (!moved) this.destination = undefined;
          else if (this.destination?.talkAfterArrival && this.isNearNpc()) {
            this.destination = undefined;
            interactRef.current();
          }
        }
      }

      game = new PhaserEngine.Game({
        type: PhaserEngine.AUTO,
        parent: mountRef.current,
        width: 1672,
        height: 941,
        backgroundColor: "#17251b",
        scale: { mode: PhaserEngine.Scale.ENVELOP, autoCenter: PhaserEngine.Scale.CENTER_BOTH },
        input: { activePointers: 2, mouse: { preventDefaultWheel: true }, touch: { capture: true } },
        scene: [MinglinScene],
        render: { pixelArt: false, antialias: true },
      });
    });

    return () => {
      cancelled = true;
      game?.destroy(true);
    };
  }, []);

  return <div className="game-canvas" ref={mountRef} aria-label="鳴霖森林遊戲地圖，點擊地面可移動，滾輪或雙指可縮放" />;
}
