"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ApiRequestError,
  DEFAULT_SCENE_VISUAL_PROFILE,
  GAME_SESSION_STORAGE_KEY,
  requestJson,
  resolveSceneImage,
  type GameStateSummary,
  type GameTurnResponse,
  type PlayerChoice,
  type PlayerScene,
} from "../../lib/game-api";
import { getSceneMusic } from "../../lib/scene-music";
import { useSceneMusic } from "../../lib/use-scene-music";
import { COUNCIL_ROUTE, easeAngle, RELIC_ROUTE, routeDistanceToPoint, routeHeading, routePoint } from "./route";
import { NPC, RELIC, START, type Pick, type TrialDriver } from "./world";
import styles from "./TrialExperience.module.css";

type Focus = "npc" | "relic";
type Controller = { advance: () => void; exit: () => void; reset: () => void; record: () => void };

const previewScene: PlayerScene = {
  scene_id: "minglin",
  region_name: "鳴霖",
  display_name: "平衡議會",
  subtitle: "古林中的議會庭",
  description: "維達利亞接見旅人的林間議會庭。",
  background_url: "/game/forest-council.png",
  horizon_url: "/game/forest-eye-backdrop.png",
  visual_profile: DEFAULT_SCENE_VISUAL_PROFILE,
  canon_status: "confirmed",
};

export default function TrialExperience() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controllerRef = useRef<Controller | null>(null);
  const driverRef = useRef<TrialDriver | null>(null);
  const sceneRef = useRef<PlayerScene>(previewScene);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [moving, setMoving] = useState(false);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [found, setFound] = useState(false);
  const [notice, setNotice] = useState("點擊石板路或維達利亞，角色會沿固定路線前進。");
  const [sessionId, setSessionId] = useState("");
  const [gameState, setGameState] = useState<GameStateSummary | null>(null);
  const [choices, setChoices] = useState<PlayerChoice[]>([]);
  const [storyLine, setStoryLine] = useState("「旅人，請看看四周。這裡留下的光，或許能告訴我們泉水發生了什麼。」");
  const [turnBusy, setTurnBusy] = useState(false);
  const [turnError, setTurnError] = useState("");
  const [sceneImageStatus, setSceneImageStatus] = useState<"queued" | "processing" | "succeeded" | "fallback">("fallback");
  const currentScene = gameState?.current_scene ?? previewScene;
  const title = currentScene.display_name;
  const track = getSceneMusic(currentScene.scene_id);
  const music = useSceneMusic(track.src, focus ? 0.11 : 0.2);

  function showBackdrop(scene: PlayerScene, context: "initial" | "turn" = "turn") {
    driverRef.current?.setSceneProfile?.(scene.visual_profile);
    const load = driverRef.current?.setBackdrop?.(scene.horizon_url);
    if (!load) return;
    void load.catch(() => {
      const message = context === "initial"
        ? `無法載入${scene.display_name}遠景；目前保留預設場景。`
        : `已抵達${scene.display_name}，但遠景載入失敗；可再試一次或重新整理。`;
      setTurnError(message);
      setNotice(message);
    });
  }

  function applyGameState(state: GameStateSummary, context: "initial" | "turn" = "turn") {
    sceneRef.current = state.current_scene;
    setGameState(state);
    showBackdrop(state.current_scene, context);
  }

  useEffect(() => {
    const id = window.localStorage.getItem(GAME_SESSION_STORAGE_KEY) ?? window.crypto.randomUUID();
    window.localStorage.setItem(GAME_SESSION_STORAGE_KEY, id);
    setSessionId(id);
    let cancelled = false;

    void (async () => {
      try {
        const state = await requestJson<GameStateSummary>("/api/game/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: id }),
        });
        const initialChoices = await requestJson<PlayerChoice[]>(`/api/game/${id}/choices`);
        if (cancelled) return;
        applyGameState(state, "initial");
        setChoices(initialChoices);
      } catch (cause) {
        if (!cancelled) setTurnError(cause instanceof Error ? cause.message : "無法連線到遊戲服務。");
      }
    })();

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!sessionId || !gameState) return;
    let current = true;
    setSceneImageStatus("queued");
    void resolveSceneImage(sessionId, gameState.state_version, () => current)
      .then((job) => {
        if (!current || !job || job.scene_id !== sceneRef.current.scene_id) return;
        setSceneImageStatus(job.status);
        if (!job.image_url) return;
        const load = driverRef.current?.setBackdrop?.(job.image_url);
        if (load) void load.catch(() => {
          if (current) setTurnError("生成場景載入失敗，已保留目前遠景。");
        });
      })
      .catch(() => {
        if (current) setSceneImageStatus("fallback");
      });
    return () => { current = false; };
  }, [gameState?.state_version, sessionId]);

  async function selectStoryChoice(choice: PlayerChoice) {
    if (!sessionId || !gameState || turnBusy) return;
    setTurnBusy(true);
    setTurnError("");
    setNotice(`正在處理「${choice.label}」…`);
    try {
      const turn = await requestJson<GameTurnResponse>("/api/game/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          action_id: window.crypto.randomUUID(),
          message: choice.message,
          input_type: "text",
          target_npc_id: choice.target_npc_id,
          action_mode: choice.action_mode,
          destination_scene_id: choice.destination_scene_id,
          story_choice_id: choice.choice_id,
          expected_state_version: gameState.state_version,
        }),
      });
      applyGameState(turn.state);
      const responseText = turn.story.dialogue.map((line) => line.text).join(" ");
      if (responseText) setStoryLine(`「${responseText}」`);
      setNotice(`第 ${turn.turn_number} 回合完成 · 目前位於${turn.state.current_scene.display_name}`);
      if (choice.action_mode === "movement") controllerRef.current?.exit();
      try {
        const nextChoices = await requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`);
        setChoices(nextChoices);
      } catch {
        setTurnError("行動已完成，但選項暫時無法更新；可重新接近維達利亞或重新整理。");
        setNotice(`第 ${turn.turn_number} 回合已完成 · 選項同步暫時失敗`);
      }
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.code === "STATE_VERSION_CONFLICT") {
        try {
          const [latest, latestChoices] = await Promise.all([
            requestJson<GameStateSummary>(`/api/game/${sessionId}/state`),
            requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`),
          ]);
          applyGameState(latest);
          setChoices(latestChoices);
          setTurnError("偵測到另一頁更新了進度，已同步最新狀態；請再點一次選項。");
          setNotice(`已同步第 ${latest.turn_count} 回合 · 目前位於${latest.current_scene.display_name}`);
        } catch {
          setTurnError("遊戲進度版本衝突，且無法重新同步；請重新整理後再試。");
          setNotice("進度同步失敗，請重新整理頁面。");
        }
      } else {
        const message = cause instanceof Error ? cause.message : "行動送出失敗。";
        setTurnError(message);
        setNotice(`行動未完成：${message}`);
      }
    } finally {
      setTurnBusy(false);
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false;
    let driver: TrialDriver | undefined;
    let frame = 0;
    let last = performance.now();
    const player = { ...START };
    let stage: 0 | 1 | 2 = 0;
    let progress = 0;
    let destination = 0;
    let walking = false;
    let turning: Focus | null = null;
    let turnTime = 0;
    let inspecting: Focus | null = null;
    let yaw = 0;
    let pitch = -0.13;
    let walkPhase = 0;
    let bobWeight = 0;
    let pointerStart: { x: number; y: number } | null = null;
    let dragging = false;

    const activeRoute = () => stage === 0 ? COUNCIL_ROUTE : RELIC_ROUTE;
    const focusYaw = (target: Focus) => {
      const place = target === "npc" ? NPC : RELIC;
      return Math.atan2(place.x - player.x, player.z - place.z);
    };
    const enterInspect = (target: Focus) => {
      turning = null;
      inspecting = target;
      driver?.setTalking?.(target === "npc");
      walking = false;
      yaw = focusYaw(target);
      pitch = target === "npc" ? 0.07 : -0.13;
      setMoving(false);
      setFocus(target);
      setNotice(target === "npc"
        ? "對話已觸發。現在可以拖曳畫面環顧四周；符石在議會右側。"
        : "任務已觸發。拖曳畫面觀察周圍，再點擊符石記錄線索。");
    };
    const exitInspect = () => {
      if (!inspecting) return;
      driver?.setTalking?.(false);
      inspecting = null;
      dragging = false;
      pitch = -0.13;
      yaw = stage === 1 ? 0 : focusYaw("relic");
      setFocus(null);
      setNotice(stage === 1
        ? "點擊石板路或符石，角色會沿右側路線轉彎前進。"
        : "符石線索已查看。需要再觀察可點擊符石，或回到入口重玩。");
    };
    const recordRelic = () => {
      if (inspecting !== "relic" || stage !== 2) return;
      setFound(true);
      setNotice("已記錄命脈符石。這道光可能是泉水異變的線索。");
    };
    const advance = (hit?: Pick) => {
      if (!driver || inspecting || turning) return;
      if (stage === 2) {
        if (hit?.kind === "relic") enterInspect("relic");
        return;
      }
      const route = activeRoute();
      const projected = hit?.kind === "ground" ? routeDistanceToPoint(route, hit) : route.length;
      const minimum = stage === 0 ? 2.3 : 1.2;
      destination = Math.max(destination, Math.min(route.length, Math.max(progress + minimum, projected)));
      walking = true;
      setMoving(true);
      setNotice(stage === 0
        ? "沿石板路前進中。鏡頭會隨腳步輕輕起伏。"
        : "沿固定路線轉向符石。轉彎由場景自動帶領。");
    };
    const reset = () => {
      driver?.setTalking?.(false);
      player.x = START.x;
      player.z = START.z;
      stage = 0;
      progress = 0;
      destination = 0;
      walking = false;
      turning = null;
      inspecting = null;
      yaw = 0;
      pitch = -0.13;
      bobWeight = 0;
      setStep(0);
      setMoving(false);
      setFocus(null);
      setFound(false);
      setNotice("點擊石板路或維達利亞，角色會沿固定路線前進。");
    };
    controllerRef.current = { advance: () => advance(), exit: exitInspect, reset, record: recordRelic };

    const keyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && inspecting) {
        event.preventDefault();
        exitInspect();
      }
    };
    const pointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      pointerStart = { x: event.clientX, y: event.clientY };
      dragging = false;
      canvas.setPointerCapture(event.pointerId);
    };
    const pointerMove = (event: PointerEvent) => {
      if (!pointerStart || !inspecting) return;
      const dx = event.clientX - pointerStart.x;
      const dy = event.clientY - pointerStart.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) dragging = true;
      yaw += dx * 0.0045;
      pitch = Math.max(-0.6, Math.min(0.42, pitch - dy * 0.003));
      pointerStart = { x: event.clientX, y: event.clientY };
    };
    const pointerUp = (event: PointerEvent) => {
      if (!pointerStart || !driver) return;
      const wasDrag = dragging || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 8;
      pointerStart = null;
      dragging = false;
      if (wasDrag) return;
      const hit = driver.pick(event.clientX, event.clientY);
      if (inspecting) {
        if (inspecting === "relic" && hit?.kind === "relic") recordRelic();
        return;
      }
      if (hit) advance(hit);
    };
    const pointerCancel = () => { pointerStart = null; dragging = false; };
    const resize = () => driver?.resize();
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      if (driver) {
        let tookStep = false;
        if (walking) {
          const route = activeRoute();
          const heading = routeHeading(route, Math.min(route.length - 0.01, progress + 0.15));
          yaw = easeAngle(yaw, heading, dt * 5.2);
          const difference = Math.abs(Math.atan2(Math.sin(heading - yaw), Math.cos(heading - yaw)));
          if (difference < 0.32) {
            progress = Math.min(destination, progress + dt * 2.85);
            const point = routePoint(route, progress);
            player.x = point.x;
            player.z = point.z;
            tookStep = true;
          }
          if (destination - progress < 0.035) {
            walking = false;
            setMoving(false);
            if (route.length - progress < 0.04) {
              const target: Focus = stage === 0 ? "npc" : "relic";
              stage = stage === 0 ? 1 : 2;
              setStep(stage);
              progress = 0;
              destination = 0;
              turning = target;
              turnTime = 0;
              setNotice(target === "npc" ? "已抵達議會，正在轉向維達利亞。" : "已抵達符石，正在停下觀察。");
            } else {
              setNotice("已沿路走到指定位置。再點前方石板路繼續前進。");
            }
          }
        } else if (turning) {
          const targetYaw = focusYaw(turning);
          yaw = easeAngle(yaw, targetYaw, dt * 7);
          pitch += ((turning === "npc" ? 0.07 : -0.13) - pitch) * Math.min(1, dt * 7);
          turnTime += dt;
          if (turnTime > 0.6) enterInspect(turning);
        }
        bobWeight += ((tookStep ? 1 : 0) - bobWeight) * Math.min(1, dt * 9);
        if (tookStep) walkPhase += dt * 12;
        const eyeBob = bobWeight * (Math.sin(walkPhase) * 0.043 + Math.sin(walkPhase * 2) * 0.009);
        driver.setView(player.x, player.z, yaw, pitch, eyeBob);
        driver.render();
      }
      frame = requestAnimationFrame(tick);
    };

    window.addEventListener("keydown", keyDown);
    window.addEventListener("resize", resize);
    canvas.addEventListener("pointerdown", pointerDown);
    canvas.addEventListener("pointermove", pointerMove);
    canvas.addEventListener("pointerup", pointerUp);
    canvas.addEventListener("pointercancel", pointerCancel);

    void import("./babylon-driver").then((module) => module.createBabylonDriver(canvas))
      .then((loaded) => {
        if (cancelled) { loaded.dispose(); return; }
        driver = loaded;
        driverRef.current = loaded;
        loaded.setSceneProfile?.(sceneRef.current.visual_profile);
        const backdrop = loaded.setBackdrop?.(sceneRef.current.horizon_url);
        if (backdrop) void backdrop.catch(() => {
          const message = `無法載入${sceneRef.current.display_name}遠景；目前保留預設場景。`;
          setTurnError(message);
          setNotice(message);
        });
        driver.resize();
        driver.setView(player.x, player.z, 0, -0.13);
        setReady(true);
        frame = requestAnimationFrame(tick);
      }).catch((reason) => setError(reason instanceof Error ? reason.message : "3D 場景無法啟動"));

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointerdown", pointerDown);
      canvas.removeEventListener("pointermove", pointerMove);
      canvas.removeEventListener("pointerup", pointerUp);
      canvas.removeEventListener("pointercancel", pointerCancel);
      controllerRef.current = null;
      driverRef.current = null;
      driver?.dispose();
    };
  }, []);

  const goal = step === 0 ? "與維達利亞交談" : found ? "已記錄命脈符石" : "尋找命脈符石";
  const nextAction = step === 0 ? "沿路走向議會" : "轉往議會右側";
  return (
    <main className={`${styles.stage} ${styles.cool}`}>
      <audio ref={music.audioRef} src={track.src} loop preload="none" onPlay={music.onPlay} onPause={music.onPause} onError={music.onError} />
      <canvas ref={canvasRef} className={styles.canvas} aria-label={`${title}第一人稱 3D 場景；點擊路面沿固定路線前進`} />
      <div className={styles.vignette} aria-hidden="true" />
      <header className={styles.topbar}>
        <div className={styles.brand}><span className={styles.compass}>✧</span><div><small>{currentScene.region_name} · 第一人稱試玩</small><strong>{title}</strong></div></div>
        <div className={styles.toplinks}>
          <span>BABYLON.JS</span>
          <button type="button" onClick={() => void music.toggle()} aria-pressed={music.playing} aria-label={music.error ? `${music.error}點擊重試` : music.playing ? `關閉${track.title}背景音樂` : `播放${track.title}背景音樂`} title={music.error || track.title}>♫ {music.error ? "重試音樂" : music.playing ? "音樂開" : "播放音樂"}</button>
          <Link href="/">返回原版</Link>
        </div>
      </header>
      <div className={styles.reticle} aria-hidden="true">◇</div>
      <aside className={styles.mission}>
        <small>探索目標 · {step === 0 ? "01 / 02" : "02 / 02"}</small><strong>{goal}</strong>
        <span>{step === 0 ? "沿石板路前往議會，抵達後自動展開對話。" : "沿右側路線前往符石，抵達後可環顧四周。"}</span>
      </aside>
      <div className={styles.notice} role="status">{notice}</div>
      {!ready && <div className={styles.loading}>{error ? `無法啟動：${error}` : "正在走進鳴霖森林……"}</div>}
      {ready && !focus && step < 2 && <button className={styles.action} type="button" disabled={moving} onClick={() => controllerRef.current?.advance()}>{moving ? "沿路前進中…" : `點擊${nextAction} ↗`}</button>}
      {focus && <section className={styles.inspect} aria-label="定點觀察">
        <div className={styles.inspectPortrait}><img src="/images/vidalia.png" alt="維達利亞" /></div>
        <div className={styles.inspectBody}><small>{focus === "npc" ? `維達利亞 · 第 ${gameState?.turn_count ?? 0} 回合` : "命脈符石 · 調查線索"}</small><p>{focus === "npc" ? storyLine :
          found ? "符石的紋路已記錄。光芒仍在引導你。" : "這枚符石閃著青色微光。拖曳畫面轉頭，仔細看看它的刻痕。"}</p>
          {focus === "npc" && choices.length > 0 && <div className={styles.storyChoices} aria-label="動態行動選項">{choices.map((choice) => <button key={choice.choice_id} type="button" disabled={turnBusy} onClick={() => void selectStoryChoice(choice)}>{choice.label}</button>)}</div>}
          {turnError && <span className={styles.turnError} role="alert">{turnError}</span>}
          <span>故事進度：{gameState?.story_progress.chapter_title ?? "鳴霖異象"}</span>
          <span>目前場景：{currentScene.display_name} · {currentScene.canon_status === "provisional" ? "暫定內容" : "已確認設定"} · {sceneImageStatus === "succeeded" ? "生成場景" : sceneImageStatus === "fallback" ? "版本化場景" : "場景生成中"}</span></div>
        <div className={styles.inspectActions}>{focus === "relic" && !found && <button type="button" onClick={() => controllerRef.current?.record()}>記錄符石</button>}<button type="button" onClick={() => controllerRef.current?.exit()}>結束觀察</button></div>
      </section>}
      <footer className={styles.footer}><span>點擊路面或目標，角色會沿固定路線行走；抵達對話或任務時才能拖曳轉頭</span><button type="button" onClick={() => controllerRef.current?.reset()}>回到入口 ↺</button></footer>
    </main>
  );
}
