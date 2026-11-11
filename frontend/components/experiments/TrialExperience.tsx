"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiRequestError,
  GAME_SESSION_STORAGE_KEY,
  requestJson,
  resolveApiAsset,
  type GameStateSummary,
  type GameTurnResponse,
  type PlayerChoice,
  type SceneAssetJob,
} from "../../lib/game-api";
import { getSceneMusic } from "../../lib/scene-music";
import { useSceneMusic } from "../../lib/use-scene-music";
import { createFirstPerson } from "./first-person";
import type { TrialDriver } from "./world";
import styles from "./TrialExperience.module.css";

type ActionInput = {
  message: string;
  input_type: "text";
  action_mode: "scene_command" | "dialogue" | "interaction" | "movement";
  target_npc_id: string | null;
  destination_scene_id: string | null;
  story_choice_id: string | null;
};
type Pending = {
  key: string;
  action_id: string;
  expected_state_version: number;
  input: ActionInput;
};

export default function TrialExperience() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const driverRef = useRef<TrialDriver | null>(null);
  const controlsRef = useRef<ReturnType<typeof createFirstPerson> | null>(null);
  const stateRef = useRef<GameStateSummary | null>(null);
  const interactionRef = useRef<() => void>(() => {});
  const journalRef = useRef<() => void>(() => {});
  const pendingRef = useRef<Pending | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [state, setState] = useState<GameStateSummary | null>(null);
  const [ready, setReady] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(
    "WASD 自由移動，拖曳滑鼠環視；走近人物或地標後按 E。",
  );
  const [choices, setChoices] = useState<PlayerChoice[]>([]);
  const [panel, setPanel] = useState(false);
  const [journal, setJournal] = useState(false);
  const [command, setCommand] = useState("");
  const [npcMessage, setNpcMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState(
    "泉水近來沉默得太久了。旅人，靠近些，說說你看見了什麼。",
  );
  const [distance, setDistance] = useState(14);
  const [poseLabel, setPoseLabel] = useState("0.0, 8.0");
  const [assetJobs, setAssetJobs] = useState<SceneAssetJob[]>([]);
  const scene = state?.current_scene;
  const world = state?.world_scene;
  const layoutKey = world
    ? `${state?.session_id}:${world.scene_id}:${world.config.revision}:${world.config.seed}`
    : "";
  const track = getSceneMusic(scene?.scene_id ?? "minglin");
  const music = useSceneMusic(track.src, panel ? 0.1 : 0.18);
  const near = distance <= 3.6;

  function applyState(next: GameStateSummary) {
    const previous = stateRef.current;
    stateRef.current = next;
    setState(next);
    if (previous?.current_scene_id !== next.current_scene_id) {
      controlsRef.current?.reset(
        next.world_scene.spawn_x,
        next.world_scene.spawn_z,
      );
      setPanel(false);
      setLine(next.current_scene.description);
    }
  }

  async function sync(id: string) {
    const next = await requestJson<GameStateSummary>("/api/game/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: id }),
    });
    applyState(next);
    setChoices(await requestJson<PlayerChoice[]>(`/api/game/${id}/choices`));
  }

  useEffect(() => {
    const id =
      window.localStorage.getItem(GAME_SESSION_STORAGE_KEY) ??
      window.crypto.randomUUID();
    window.localStorage.setItem(GAME_SESSION_STORAGE_KEY, id);
    setSessionId(id);
    void sync(id).catch((cause) =>
      setError(cause instanceof Error ? cause.message : "無法連線遊戲服務"),
    );
  }, []);

  interactionRef.current = () => {
    if (!stateRef.current) return;
    const current = stateRef.current.world_scene;
    const pose = controlsRef.current?.pose;
    if (
      !pose ||
      Math.hypot(
        pose.x - current.interaction_x,
        pose.z - current.interaction_z,
      ) > 3.6
    ) {
      setNotice("請先走近人物或發光地標，距離 3.6 公尺內按 E 互動。");
      return;
    }
    setPanel((value) => !value);
  };
  journalRef.current = () => setJournal((value) => !value);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false,
      frame = 0,
      last = performance.now(),
      hud = 0;
    let driver: TrialDriver | undefined;
    let controls: ReturnType<typeof createFirstPerson> | undefined;
    const resize = () => driver?.resize();
    window.addEventListener("resize", resize);
    void import("./babylon-driver")
      .then((m) => m.createBabylonDriver(canvas))
      .then((loaded) => {
        if (cancelled) {
          loaded.dispose();
          return;
        }
        driver = loaded;
        driverRef.current = loaded;
        controls = createFirstPerson(
          canvas,
          loaded,
          () => interactionRef.current(),
          () => journalRef.current(),
        );
        controlsRef.current = controls;
        const current = stateRef.current?.world_scene;
        if (current) controls.reset(current.spawn_x, current.spawn_z);
        const tick = (now: number) => {
          const dt = Math.min((now - last) / 1000, 0.05);
          last = now;
          controls!.tick(dt);
          loaded.render();
          if (now - hud > 200) {
            hud = now;
            const pose = controls!.pose;
            const w = stateRef.current?.world_scene;
            setPoseLabel(`${pose.x.toFixed(1)}, ${pose.z.toFixed(1)}`);
            if (w)
              setDistance(
                Math.hypot(pose.x - w.interaction_x, pose.z - w.interaction_z),
              );
            canvas.dataset.playerX = pose.x.toFixed(3);
            canvas.dataset.playerZ = pose.z.toFixed(3);
            canvas.dataset.yaw = pose.yaw.toFixed(3);
          }
          frame = requestAnimationFrame(tick);
        };
        loaded.resize();
        setReady(true);
        frame = requestAnimationFrame(tick);
      })
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "3D 引擎啟動失敗"),
      );
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      controls?.dispose();
      driver?.dispose();
      controlsRef.current = null;
      driverRef.current = null;
    };
  }, []);

  useEffect(() => {
    controlsRef.current?.pause(panel || journal || !sceneReady || !state);
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPanel(false);
        setJournal(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [ready, panel, journal, sceneReady, state?.session_id]);

  useEffect(() => {
    if (!ready || !world || !driverRef.current) return;
    let current = true;
    setSceneReady(false);
    void driverRef.current
      .setWorld(world)
      .then(() => {
        if (current) setSceneReady(true);
      })
      .catch((cause) => {
        if (current) {
          setError(
            `場景模型載入失敗：${cause instanceof Error ? cause.message : "請重新整理"}`,
          );
          setSceneReady(true);
        }
      });
    return () => {
      current = false;
    };
  }, [ready, layoutKey]);

  useEffect(() => {
    if (!ready || !sceneReady || !world || !state || !sessionId) return;
    let current = true;
    const applied = new Map<string, string>();
    const run = async () => {
      let jobs = await requestJson<SceneAssetJob[]>(
        `/api/game/${sessionId}/scene-assets`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_state_version: state.state_version }),
        },
      );
      while (current) {
        setAssetJobs(jobs);
        for (const job of jobs) {
          if (
            !current ||
            job.seed !== stateRef.current?.world_scene.config.seed
          )
            return;
          if (
            job.status === "succeeded" &&
            job.model_url &&
            applied.get(job.kind) !== job.model_url
          ) {
            await driverRef.current?.setAsset(
              job.kind,
              resolveApiAsset(job.model_url),
            );
            applied.set(job.kind, job.model_url);
          }
        }
        if (
          jobs.every((j) => j.status === "succeeded" || j.status === "fallback")
        )
          return;
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (!current) return;
        jobs = await Promise.all(
          jobs.map((job) =>
            requestJson<SceneAssetJob>(
              `/api/game/${sessionId}/scene-assets/${job.job_id}`,
            ),
          ),
        );
      }
    };
    void run().catch((cause) => {
      if (current)
        setNotice(
          `新模型暫時無法更新，已保留可玩的場景。${cause instanceof Error ? cause.message : ""}`,
        );
    });
    return () => {
      current = false;
    };
  }, [ready, sceneReady, layoutKey, sessionId]);

  async function send(input: ActionInput) {
    const snapshot = stateRef.current;
    if (!snapshot || busy) return;
    const key = JSON.stringify(input);
    const previous = pendingRef.current;
    const pending =
      previous?.key === key &&
      previous.expected_state_version === snapshot.state_version
        ? previous
        : {
            key,
            action_id: window.crypto.randomUUID(),
            expected_state_version: snapshot.state_version,
            input,
          };
    pendingRef.current = pending;
    setBusy(true);
    setError("");
    try {
      const turn = await requestJson<GameTurnResponse>("/api/game/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          action_id: pending.action_id,
          expected_state_version: pending.expected_state_version,
          ...input,
        }),
      });
      pendingRef.current = null;
      applyState(turn.state);
      const result = turn.story.dialogue.map((l) => l.text).join(" ");
      setLine(result);
      setNotice(result);
      setCommand("");
      if (input.action_mode === "scene_command") setJournal(false);
      setChoices(
        await requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`),
      );
    } catch (cause) {
      if (
        cause instanceof ApiRequestError &&
        cause.code === "STATE_VERSION_CONFLICT"
      ) {
        pendingRef.current = null;
        await sync(sessionId);
        setError("另一頁已更新進度，現在已同步；請再送一次。");
      } else {
        setError(
          cause instanceof Error ? cause.message : "行動沒有完成，請重試。",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  function select(choice: PlayerChoice) {
    void send({
      message: choice.message,
      input_type: "text",
      action_mode: choice.action_mode,
      target_npc_id: choice.target_npc_id,
      destination_scene_id: choice.destination_scene_id,
      story_choice_id: choice.story_choice_id,
    });
  }

  async function restartJourney() {
    if (busy) return;
    const id = window.crypto.randomUUID();
    window.localStorage.setItem(GAME_SESSION_STORAGE_KEY, id);
    pendingRef.current = null;
    stateRef.current = null;
    setState(null);
    setSceneReady(false);
    setSessionId(id);
    setPanel(false);
    setJournal(false);
    setBusy(true);
    setError("");
    setAssetJobs([]);
    try {
      await sync(id);
      setNotice("新的旅程已開始。WASD 移動，走近維達利亞後按 E。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "無法建立旅程");
    } finally {
      setBusy(false);
    }
  }

  function submitCommand(event: FormEvent) {
    event.preventDefault();
    const message = command.trim();
    if (!message) return;
    void send({
      message,
      input_type: "text",
      action_mode: "scene_command",
      target_npc_id: null,
      destination_scene_id: null,
      story_choice_id: null,
    });
  }

  const completed = assetJobs.filter(
    (job) => job.status === "succeeded",
  ).length;
  return (
    <main className={styles.stage}>
      <audio
        ref={music.audioRef}
        src={track.src}
        loop
        preload="none"
        onPlay={music.onPlay}
        onPause={music.onPause}
        onError={music.onError}
      />
      <canvas
        ref={canvasRef}
        tabIndex={0}
        className={styles.canvas}
        aria-label="第一人稱探索場景，WASD 移動，拖曳環視，E 互動"
      />
      <div className={styles.vignette} />
      <header className={styles.header}>
        <div className={styles.brand}>
          <span>✧</span>
          <div>
            <small>{scene?.region_name ?? "鳴霖"} · 第一人稱探索</small>
            <h1>{scene?.display_name ?? "正在進入世界"}</h1>
          </div>
        </div>
        <nav>
          <button disabled={busy} onClick={() => void restartJourney()}>
            新旅程
          </button>
          <button onClick={() => setJournal(true)}>
            世界指令 <kbd>Tab</kbd>
          </button>
          <button onClick={() => void music.toggle()}>
            {music.playing ? "♫ 音樂開" : "♫ 播放音樂"}
          </button>
          <Link href="/">2D 版</Link>
        </nav>
      </header>
      <div className={styles.crosshair} aria-hidden>
        ·
      </div>
      <aside className={styles.objective}>
        <small>當前旅程 · 第 {state?.turn_count ?? 0} 回合</small>
        <strong>{state?.story_progress.chapter_title ?? "鳴霖異象"}</strong>
        <p>
          {world?.interaction_label} · {distance.toFixed(1)} m
        </p>
        <span>
          {world?.config.time_of_day === "night"
            ? "夜晚"
            : world?.config.time_of_day === "dusk"
              ? "黃昏"
              : "白天"}{" "}
          · 場景版本 {world?.config.revision ?? 0}
        </span>
      </aside>
      <div className={styles.coordinates} aria-label="玩家位置">
        ⌖ {poseLabel}
      </div>
      {ready && sceneReady && !panel && !journal && (
        <div className={styles.interaction}>
          <button disabled={!near} onClick={() => interactionRef.current()}>
            <kbd>E</kbd>{" "}
            {near
              ? world?.interaction_label
              : `走近${world?.npc_id ? "人物" : "地標"}後互動`}
          </button>
        </div>
      )}
      <footer className={styles.footer}>
        <span>
          <kbd>W A S D</kbd> 移動 <kbd>Shift</kbd> 奔跑 · 滑鼠拖曳環視{" "}
          <button
            onClick={async () => {
              try {
                await canvasRef.current?.requestPointerLock();
              } catch {
                setNotice("這個瀏覽器未啟用滑鼠鎖定；按住滑鼠拖曳仍可環視。");
              }
            }}
          >
            鎖定滑鼠
          </button>{" "}
          · <kbd>Esc</kbd> 釋放
        </span>
        <span>
          {assetJobs.some(
            (j) => j.status === "queued" || j.status === "processing",
          )
            ? `3D 模型生成中 ${completed}/${assetJobs.length}`
            : completed
              ? `新 3D 模型已載入 ${completed}/${assetJobs.length}`
              : "3D 場景就緒"}
        </span>
      </footer>
      {!panel && !journal && (
        <div className={styles.notice} role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className={styles.error} role="alert">
          {error}
          <button onClick={() => setError("")}>關閉</button>
        </div>
      )}
      {(!ready || !state || !sceneReady) && !error && (
        <div className={styles.loading}>
          <span>✧</span>
          <h2>正在建構可探索的世界</h2>
          <p>載入地形、光照與生成模型…</p>
        </div>
      )}
      {panel && (
        <section className={styles.dialogue} aria-label="地標互動">
          {world?.npc_id && (
            <img
              src={`/images/${world.npc_id}.png`}
              alt={world.npc_id === "vidalia" ? "維達利亞" : "門梅司文托"}
            />
          )}
          <div>
            <small>
              {world?.npc_id === "vidalia"
                ? "維達利亞"
                : world?.npc_id === "menmesvento"
                  ? "門梅司文托"
                  : scene?.display_name}
            </small>
            <p>{line}</p>
            <div className={styles.choices}>
              {choices.map((choice) => (
                <button
                  key={choice.choice_id}
                  disabled={busy}
                  onClick={() => select(choice)}
                >
                  {choice.label}
                </button>
              ))}
            </div>
            {world?.npc_id && (
              <form
                className={styles.npcForm}
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!npcMessage.trim()) return;
                  void send({
                    message: npcMessage.trim(),
                    input_type: "text",
                    action_mode: "dialogue",
                    target_npc_id: world.npc_id,
                    destination_scene_id: null,
                    story_choice_id: null,
                  });
                  setNpcMessage("");
                }}
              >
                <input
                  aria-label="對角色說話"
                  placeholder="也可以直接說出你的想法…"
                  value={npcMessage}
                  onChange={(event) => setNpcMessage(event.target.value)}
                  maxLength={2000}
                />
                <button disabled={busy || !npcMessage.trim()}>送出</button>
              </form>
            )}
          </div>
          <button
            className={styles.close}
            onClick={() => setPanel(false)}
            aria-label="結束互動"
          >
            ✕
          </button>
        </section>
      )}
      {journal && (
        <div className={styles.modal}>
          <section
            className={styles.journal}
            role="dialog"
            aria-modal="true"
            aria-label="世界指令"
          >
            <button
              className={styles.close}
              onClick={() => setJournal(false)}
              aria-label="關閉世界指令"
            >
              ✕
            </button>
            <small>WORLD ATELIER</small>
            <h2>讓世界回應你的指令</h2>
            <p>
              調整當前場景的日夜、天氣、地形和物件。指令通過後端驗證後保存，新生成的
              3D 模型會逐一加入場景。
            </p>
            <form onSubmit={submitCommand}>
              <label htmlFor="world-command">想改變什麼？</label>
              <textarea
                id="world-command"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="例如：生成 6 個符石，變成夜晚並起霧"
                maxLength={2000}
                autoFocus
              />
              <button disabled={busy || !command.trim()}>
                {busy ? "正在重建…" : "生成場景變化 ↗"}
              </button>
            </form>
            <div className={styles.examples}>
              {[
                "生成 6 個符石，變成夜晚並起霧",
                "白天、放晴，生成 30 棵樹",
                "生成 2 座祭壇，黃昏、岩石地形",
              ].map((example) => (
                <button key={example} onClick={() => setCommand(example)}>
                  {example}
                </button>
              ))}
            </div>
            <p className={styles.hint}>
              場景變化會保存到這個遊戲。旅行仍需先取得線索並走到地標互動。模型生成期間可以繼續探索。
            </p>
          </section>
        </div>
      )}
    </main>
  );
}
