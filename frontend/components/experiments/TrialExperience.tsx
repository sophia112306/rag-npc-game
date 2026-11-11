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
import { COUNCIL_ROUTE, easeAngle, routeDistanceToPoint, routeHeading, routePoint } from "./route";
import { NPC, START, type Pick, type TrialDriver } from "./world";
import styles from "./TrialExperience.module.css";

type Focus = "npc";
type Controller = { advance: () => void; exit: () => void; reset: () => void };

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

const clueLabels: Record<string, string> = {
  ash_flow_pattern: "灰燼流向",
  burial_fire_cycle: "墓葬與聖火循環",
  ember_current: "餘燼流向烈燚原",
  fissure_map: "裂谷路線",
  forgotten_names: "被遺忘者姓名",
  mummies_seek_remembrance: "木乃伊希望被記住",
  sacred_fire_cycle: "聖火循環",
};

export default function TrialExperience() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controllerRef = useRef<Controller | null>(null);
  const driverRef = useRef<TrialDriver | null>(null);
  const sceneRef = useRef<PlayerScene>(previewScene);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState<0 | 1>(0);
  const [moving, setMoving] = useState(false);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [notice, setNotice] = useState("點擊維達利亞或下方按鈕，角色會沿固定路線接近她。");
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
  const isCouncilScene = currentScene.scene_id === "minglin";

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
    if (state.current_scene.scene_id !== "minglin") {
      setFocus(null);
      setStoryLine(`「${state.current_scene.description}」`);
      if (context === "initial") {
        setNotice("選擇一項行動推進此回合；後端只會保存通過規則驗證的結果。");
      }
    }
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
    let stage: 0 | 1 = 0;
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

    const focusYaw = () => Math.atan2(NPC.x - player.x, player.z - NPC.z);
    const enterInspect = () => {
      turning = null;
      inspecting = "npc";
      driver?.setTalking?.(true);
      walking = false;
      yaw = focusYaw();
      pitch = 0.07;
      setMoving(false);
      setFocus("npc");
      setNotice("對話已觸發。選擇一項由後端依目前故事狀態提供的行動。");
    };
    const exitInspect = () => {
      if (!inspecting) return;
      driver?.setTalking?.(false);
      inspecting = null;
      dragging = false;
      pitch = -0.13;
      yaw = focusYaw();
      setFocus(null);
      setNotice("可再次點擊維達利亞交談，或回到入口重走一次。");
    };
    const advance = (hit?: Pick) => {
      if (!driver || inspecting || turning) return;
      if (stage === 1) {
        if (hit?.kind === "npc") enterInspect();
        return;
      }
      const projected = hit?.kind === "ground" ? routeDistanceToPoint(COUNCIL_ROUTE, hit) : COUNCIL_ROUTE.length;
      destination = Math.max(destination, Math.min(COUNCIL_ROUTE.length, Math.max(progress + 2.3, projected)));
      walking = true;
      setMoving(true);
      setNotice("正在接近維達利亞。鏡頭會隨腳步輕輕起伏。");
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
      setNotice("點擊維達利亞或下方按鈕，角色會沿固定路線接近她。");
    };
    controllerRef.current = { advance: () => advance(), exit: exitInspect, reset };

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
      if (sceneRef.current.scene_id !== "minglin") return;
      const hit = driver.pick(event.clientX, event.clientY);
      if (inspecting) return;
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
          const heading = routeHeading(COUNCIL_ROUTE, Math.min(COUNCIL_ROUTE.length - 0.01, progress + 0.15));
          yaw = easeAngle(yaw, heading, dt * 5.2);
          const difference = Math.abs(Math.atan2(Math.sin(heading - yaw), Math.cos(heading - yaw)));
          if (difference < 0.32) {
            progress = Math.min(destination, progress + dt * 2.85);
            const point = routePoint(COUNCIL_ROUTE, progress);
            player.x = point.x;
            player.z = point.z;
            tookStep = true;
          }
          if (destination - progress < 0.035) {
            walking = false;
            setMoving(false);
            if (COUNCIL_ROUTE.length - progress < 0.04) {
              stage = 1;
              setStep(1);
              progress = 0;
              destination = 0;
              turning = "npc";
              turnTime = 0;
              setNotice("已抵達議會，正在轉向維達利亞。");
            } else {
              setNotice("已沿路走到指定位置。再點前方石板路繼續前進。");
            }
          }
        } else if (turning) {
          const targetYaw = focusYaw();
          yaw = easeAngle(yaw, targetYaw, dt * 7);
          pitch += (0.07 - pitch) * Math.min(1, dt * 7);
          turnTime += dt;
          if (turnTime > 0.6) enterInspect();
        }
        bobWeight += ((tookStep ? 1 : 0) - bobWeight) * Math.min(1, dt * 9);
        if (tookStep) walkPhase += dt * 12;
        const eyeBob = bobWeight * (Math.sin(walkPhase) * 0.043 + Math.sin(walkPhase * 2) * 0.009);
        if (sceneRef.current.scene_id === "minglin") {
          driver.setView(player.x, player.z, yaw, pitch, eyeBob);
        } else {
          driver.setView(START.x, START.z, 0, 0.04);
        }
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

  const goal = step === 0 ? "與維達利亞交談" : "選擇調查方向";
  const publicClues = gameState?.story_progress.public_clue_ids ?? [];
  return (
    <main className={`${styles.stage} ${styles.cool}`}>
      <audio ref={music.audioRef} src={track.src} loop preload="none" onPlay={music.onPlay} onPause={music.onPause} onError={music.onError} />
      <canvas ref={canvasRef} className={styles.canvas} aria-label={isCouncilScene
        ? `${title}視覺原型；點擊維達利亞或按鈕接近她`
        : `${title}故事場景；使用畫面下方選項推進分支`} />
      <div className={styles.vignette} aria-hidden="true" />
      <header className={styles.topbar}>
        <div className={styles.brand}><span className={styles.compass}>✧</span><div><small>{currentScene.region_name} · 視覺故事原型</small><strong>{title}</strong></div></div>
        <div className={styles.toplinks}>
          <span>BABYLON.JS</span>
          <button type="button" onClick={() => void music.toggle()} aria-pressed={music.playing} aria-label={music.error ? `${music.error}點擊重試` : music.playing ? `關閉${track.title}背景音樂` : `播放${track.title}背景音樂`} title={music.error || track.title}>♫ {music.error ? "重試音樂" : music.playing ? "音樂開" : "播放音樂"}</button>
          <Link href="/">返回原版</Link>
        </div>
      </header>
      {isCouncilScene && <div className={styles.reticle} aria-hidden="true">◇</div>}
      <aside className={styles.mission}>
        {isCouncilScene ? <>
          <small>探索目標 · {step === 0 ? "接近議會" : "故事選擇"}</small><strong>{goal}</strong>
          <span>{step === 0 ? "接近維達利亞，抵達後取得目前可用的故事選項。" : "選項由後端依 Session、位置與故事節點提供。"}</span>
        </> : <>
          <small>規則分支（非 AI） · 第 {gameState?.turn_count ?? 0} 回合</small>
          <strong>{gameState?.story_progress.chapter_title ?? currentScene.subtitle}</strong>
          <span>{currentScene.description}</span>
        </>}
      </aside>
      <div className={styles.notice} role="status">{notice}</div>
      {!ready && <div className={styles.loading}>{error ? `無法啟動：${error}` : "正在走進鳴霖森林……"}</div>}
      {ready && isCouncilScene && !focus && step === 0 && <button className={styles.action} type="button" disabled={moving} onClick={() => controllerRef.current?.advance()}>{moving ? "接近維達利亞…" : "接近維達利亞 ↗"}</button>}
      {isCouncilScene && focus && <section className={styles.inspect} aria-label="定點觀察">
        <div className={styles.inspectPortrait}><img src="/images/vidalia.png" alt="維達利亞" /></div>
        <div className={styles.inspectBody}><small>維達利亞 · 第 {gameState?.turn_count ?? 0} 回合</small><p>{storyLine}</p>
          {choices.length > 0 && <div className={styles.storyChoices} aria-label="規則故事行動選項">{choices.map((choice) => <button key={choice.choice_id} type="button" disabled={turnBusy} onClick={() => void selectStoryChoice(choice)}>{choice.label}</button>)}</div>}
          {turnError && <span className={styles.turnError} role="alert">{turnError}</span>}
          <span>故事進度：{gameState?.story_progress.chapter_title ?? "鳴霖異象"}</span>
          <span>目前場景：{currentScene.display_name} · {currentScene.canon_status === "provisional" ? "暫定內容" : "已確認設定"} · {sceneImageStatus === "succeeded" ? "生成場景" : sceneImageStatus === "fallback" ? "版本化場景" : "場景生成中"}</span></div>
        <div className={styles.inspectActions}><button type="button" onClick={() => controllerRef.current?.exit()}>結束對話</button></div>
      </section>}
      {!isCouncilScene && <section className={`${styles.inspect} ${styles.storyInspect}`} aria-label={`${title}規則故事分支`}>
        <div className={styles.inspectBody}>
          <small>{currentScene.display_name} · {gameState?.story_progress.chapter_title ?? currentScene.subtitle}</small>
          <p>{storyLine}</p>
          <div className={styles.storyChoices} aria-label="規則故事行動選項">
            {choices.map((choice) => <button key={choice.choice_id} type="button" disabled={turnBusy} onClick={() => void selectStoryChoice(choice)}>{choice.label}</button>)}
          </div>
          {choices.length === 0 && <span>此節點目前沒有可執行選項。</span>}
          {turnError && <span className={styles.turnError} role="alert">{turnError}</span>}
          <span className={styles.clues}>已成立公開線索：{publicClues.length > 0
            ? publicClues.map((clue) => clueLabels[clue] ?? clue).join("、")
            : "尚無"}</span>
          <span>呈現模式：有狀態的規則分支；接入 B 的 ModelGateway 後才是 AI 自由生成。</span>
        </div>
      </section>}
      <footer className={styles.footer}><span>{isCouncilScene
        ? "目前以完整場景插畫維持一致透視；接近維達利亞後選擇後端提供的故事行動"
        : "每個選項都會經過後端驗證、保存事件與狀態，再由下一回合承接"}</span>{isCouncilScene && <button type="button" onClick={() => controllerRef.current?.reset()}>回到入口 ↺</button>}</footer>
    </main>
  );
}
