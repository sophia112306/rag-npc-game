"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import MinglinGame, { interactWithNpc, movePlayer, turnPlayer, zoomMap, MIN_MAP_ZOOM, MAX_MAP_ZOOM, MAP_ZOOM_STEP } from "../components/MinglinGame";

type CharacterProfile = {
  npc_id: string;
  name: string;
  romanized_name: string;
  title: string;
  scene_name: string;
  portrait_url: string;
  description: string;
  greeting: string;
};

type GameTurnResponse = {
  turn_number: number;
  state: { state_version: number; updated_at: string };
  story: { dialogue: { speaker_name: string; text: string }[] };
};

type GameStateSummary = {
  turn_count: number;
  state_version: number;
  updated_at: string;
};

type Capabilities = {
  generation_mode: "rule_based" | "external_model";
  dynamic_dialogue: boolean;
};

type PlayerQuest = {
  quest_id: string;
  title: string;
  status: "offered" | "active" | "completed" | "failed" | "cancelled";
};

type PlayerChoice = {
  choice_id: string;
  label: string;
  message: string;
  target_npc_id: string;
  action_mode: "dialogue" | "interaction" | "movement";
};

type ChatMessage = {
  id: string;
  speaker: string;
  text: string;
  kind: "npc" | "player";
};

type PendingAction = {
  actionId: string;
  text: string;
  inputType: "text" | "speech_transcript";
  targetNpcId: string;
  actionMode: PlayerChoice["action_mode"];
  expectedStateVersion: number;
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

class ApiRequestError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
  }
}

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";
const storageKey = "vidalia-game-session";
const conversationKey = (id: string) => `vidalia-conversation:${id}`;
const previewProfile: CharacterProfile = {
  npc_id: "vidalia",
  name: "維達利亞",
  romanized_name: "Vidalia",
  title: "初代精靈・平衡議會調解人",
  scene_name: "鳴霖・平衡議會",
  portrait_url: "/images/vidalia.png",
  description: "鳴霖的精靈領袖與史官，守護命脈之泉，也在世界異象中尋找平衡。",
  greeting: "旅人，歡迎來到鳴霖。命脈之泉近來沉默得太久了；你願意告訴我，你沿途看見了什麼嗎？",
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, init);
  } catch {
    throw new Error("無法連線到遊戲服務，請確認後端已啟動。");
  }
  if (!response.ok) {
    let detail: { code?: string; message?: string } | undefined;
    try {
      const payload = (await response.json()) as { detail?: { code?: string; message?: string } };
      detail = payload.detail;
    } catch { /* Non-JSON failures use the generic status message below. */ }
    throw new ApiRequestError(
      detail?.message ?? `遊戲服務回應 ${response.status}，請稍後重試。`,
      response.status,
      detail?.code,
    );
  }
  return (await response.json()) as T;
}

export default function Home() {
  const [profile, setProfile] = useState(previewProfile);
  const [sessionId, setSessionId] = useState("");
  const [dialogueOpen, setDialogueOpen] = useState(false);
  const [nearNpc, setNearNpc] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "speech_transcript">("text");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [ttsSupported, setTtsSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [lastNpcSpeech, setLastNpcSpeech] = useState("");
  const [busy, setBusy] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [restartConfirm, setRestartConfirm] = useState(false);
  const [turnNumber, setTurnNumber] = useState(0);
  const [stateVersion, setStateVersion] = useState(1);
  const [generationMode, setGenerationMode] = useState<Capabilities["generation_mode"]>("rule_based");
  const [questLabel, setQuestLabel] = useState("與維達利亞交談");
  const [playerChoices, setPlayerChoices] = useState<PlayerChoice[]>([]);
  const [mapZoom, setMapZoom] = useState(MIN_MAP_ZOOM);
  const endRef = useRef<HTMLDivElement>(null);
  const pendingActionRef = useRef<PendingAction | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);

  useEffect(() => {
    const id = window.localStorage.getItem(storageKey) ?? window.crypto.randomUUID();
    window.localStorage.setItem(storageKey, id);
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    setVoiceSupported(Boolean(speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition));
    setTtsSupported("speechSynthesis" in window);
    void initialize(id);
    return () => {
      recognitionRef.current?.stop();
      window.speechSynthesis?.cancel();
    };
  }, []);

  useEffect(() => {
    if (dialogueOpen) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, dialogueOpen]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHelpOpen(false);
        setRestartConfirm(false);
        setDialogueOpen(false);
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  async function initialize(id: string) {
    setSessionId(id);
    setBusy(true);
    setInitializing(true);
    setError("");
    setReady(false);
    try {
      const [character, state, capabilities] = await Promise.all([
        requestJson<CharacterProfile>("/api/characters/vidalia"),
        requestJson<GameStateSummary>("/api/game/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: id }),
        }),
        requestJson<Capabilities>("/api/capabilities"),
      ]);
      setProfile(character);
      setGenerationMode(capabilities.generation_mode);
      const [quests, choices] = await Promise.all([
        requestJson<PlayerQuest[]>(`/api/game/${id}/quests`),
        requestJson<PlayerChoice[]>(`/api/game/${id}/choices`),
      ]);
      setQuestLabel(quests[0] ? `${quests[0].status === "offered" ? "任務提議" : "目前任務"}：${quests[0].title}` : "與維達利亞交談");
      setPlayerChoices(choices);
      setTurnNumber(state.turn_count);
      setStateVersion(state.state_version);
      const fallback: ChatMessage[] = [{ id: window.crypto.randomUUID(), speaker: character.name, text: character.greeting, kind: "npc" }];
      let restored = fallback;
      try {
        const cached = JSON.parse(window.localStorage.getItem(conversationKey(id)) ?? "null");
        if (cached?.turn_number === state.turn_count && cached?.updated_at === state.updated_at &&
          Array.isArray(cached.messages) && cached.messages.length > 0 &&
          cached.messages.every((message: ChatMessage) => typeof message.id === "string" &&
            typeof message.speaker === "string" && typeof message.text === "string" &&
            (message.kind === "npc" || message.kind === "player"))) {
          restored = cached.messages;
        }
      } catch { /* A missing or old browser record starts with the greeting. */ }
      setMessages(restored);
      setLastNpcSpeech(restored.filter((message) => message.kind === "npc").at(-1)?.text ?? character.greeting);
      setReady(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "無法連線到後端。");
      setMessages([{ id: window.crypto.randomUUID(), speaker: previewProfile.name, text: previewProfile.greeting, kind: "npc" }]);
    } finally {
      setBusy(false);
      setInitializing(false);
    }
  }

  const openDialogue = useCallback(() => {
    setHelpOpen(false);
    setDialogueOpen(true);
  }, []);

  function toggleListening() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("這個瀏覽器不支援語音轉文字，仍可使用文字輸入。");
      return;
    }
    setError("");
    const recognition = new Recognition();
    recognition.lang = "zh-TW";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript?.trim();
      if (transcript) {
        setInput(transcript);
        setInputType("speech_transcript");
      }
    };
    recognition.onerror = (event) => {
      const message = event.error === "not-allowed"
        ? "麥克風權限未開啟；你可以在瀏覽器設定允許後再試。"
        : "語音辨識沒有成功，請再試一次或使用文字輸入。";
      setError(message);
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  function speakLastResponse() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    if (!ttsSupported || !lastNpcSpeech) {
      setError("這個瀏覽器目前無法播放語音。");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(lastNpcSpeech);
    utterance.lang = "zh-TW";
    utterance.rate = 1;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    const pending = pendingActionRef.current;
    const retryingPending = pending?.text === text && pending.inputType === inputType && pending.expectedStateVersion === stateVersion;
    void sendAction(
      text,
      inputType,
      retryingPending ? pending.targetNpcId : "vidalia",
      retryingPending ? pending.actionMode : "dialogue",
    );
  }

  function selectChoice(choice: PlayerChoice) {
    void sendAction(choice.message, "text", choice.target_npc_id, choice.action_mode);
  }

  async function sendAction(
    text: string,
    actionInputType: "text" | "speech_transcript",
    targetNpcId: string,
    actionMode: PlayerChoice["action_mode"],
  ) {
    if (!text || !ready || busy) return;

    setInput("");
    setInputType("text");
    setBusy(true);
    setError("");
    setMessages((current) => [...current, { id: window.crypto.randomUUID(), speaker: "你", text, kind: "player" }]);
    const pending = pendingActionRef.current;
    const canRetryPending = pending?.text === text && pending.inputType === actionInputType && pending.targetNpcId === targetNpcId && pending.actionMode === actionMode && pending.expectedStateVersion === stateVersion;
    const actionId = canRetryPending ? pending.actionId : window.crypto.randomUUID();
    pendingActionRef.current = { actionId, text, inputType: actionInputType, targetNpcId, actionMode, expectedStateVersion: stateVersion };

    try {
      const turn = await requestJson<GameTurnResponse>("/api/game/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          action_id: actionId,
          message: text,
          input_type: actionInputType,
          target_npc_id: targetNpcId,
          action_mode: actionMode,
          expected_state_version: stateVersion,
        }),
      });
      pendingActionRef.current = null;
      setTurnNumber(turn.turn_number);
      setStateVersion(turn.state.state_version);
      try {
        const [quests, choices] = await Promise.all([
          requestJson<PlayerQuest[]>(`/api/game/${sessionId}/quests`),
          requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`),
        ]);
        setQuestLabel(quests[0] ? `${quests[0].status === "offered" ? "任務提議" : "目前任務"}：${quests[0].title}` : "與維達利亞交談");
        setPlayerChoices(choices);
      } catch { /* The committed turn remains valid if the optional quest refresh fails. */ }
      const nextMessages: ChatMessage[] = [...messages, { id: window.crypto.randomUUID(), speaker: "你", text, kind: "player" }, ...turn.story.dialogue.map((line) => ({
        id: window.crypto.randomUUID(), speaker: line.speaker_name, text: line.text, kind: "npc" as const,
      }))];
      setMessages(nextMessages);
      setLastNpcSpeech(turn.story.dialogue.filter((line) => line.speaker_name !== "系統").map((line) => line.text).join("\n"));
      try {
        window.localStorage.setItem(conversationKey(sessionId), JSON.stringify({ turn_number: turn.turn_number, updated_at: turn.state.updated_at, messages: nextMessages }));
      } catch { /* The current conversation still works when browser storage is unavailable. */ }
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.code === "STATE_VERSION_CONFLICT") {
        pendingActionRef.current = null;
        try {
          const latest = await requestJson<GameStateSummary>(`/api/game/${sessionId}/state`);
          setTurnNumber(latest.turn_count);
          setStateVersion(latest.state_version);
          setError("遊戲進度已在其他請求中更新，請確認內容後重新送出。");
        } catch {
          setError("遊戲進度版本衝突，且無法重新取得最新狀態。請稍後重試。");
        }
      } else {
        if (cause instanceof ApiRequestError && cause.code === "ACTION_ID_CONFLICT") {
          pendingActionRef.current = null;
        }
        setError(cause instanceof Error ? cause.message : "送出失敗，請稍後再試。");
      }
      setInput(text);
      setMessages(messages);
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    const id = window.crypto.randomUUID();
    window.localStorage.setItem(storageKey, id);
    setDialogueOpen(false);
    setRestartConfirm(false);
    setHelpOpen(false);
    setNearNpc(false);
    setInput("");
    setInputType("text");
    pendingActionRef.current = null;
    void initialize(id);
  }

  const previewLine = turnNumber > 0
    ? messages.filter((message) => message.kind === "npc").at(-1)?.text
    : "……你來了。";

  return (
    <main className="game-page">
      <section className="map-stage" aria-label="斜俯視的鳴霖遊戲地圖">
        {sessionId && <MinglinGame key={sessionId} paused={dialogueOpen || helpOpen || restartConfirm || initializing || !ready} onNearChange={setNearNpc} onInteract={openDialogue} onZoomChange={setMapZoom} />}
        <div className="scene-vignette" aria-hidden="true" />

        <header className="location-banner" aria-label="目前場景">
          <svg className="compass-mark" viewBox="0 0 72 72" fill="none" aria-hidden="true">
            <circle cx="36" cy="36" r="24" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="36" cy="36" r="16" stroke="currentColor" strokeWidth="0.8" />
            <path d="M36 3l6 27 27 6-27 6-6 27-6-27L3 36l27-6L36 3Z" stroke="currentColor" strokeWidth="1.7" />
            <path d="M36 22l4 10 10 4-10 4-4 10-4-10-10-4 10-4 4-10Z" fill="currentColor" />
          </svg>
          <div className="location-copy"><strong>鳴霖</strong><span>命脈之泉 · 平衡議會</span></div>
          <span className="location-ornament" aria-hidden="true">✧</span>
        </header>

        <aside className="quest-banner" aria-label="目前任務">
          <span className="quest-emblem" aria-hidden="true">◇</span>
          <span>{questLabel}</span>
          <button type="button" className="help-button" onClick={() => setHelpOpen(true)} aria-label="查看操作說明" title="操作說明">?</button>
          <button type="button" className="restart-button" onClick={() => setRestartConfirm(true)} disabled={busy} aria-label="重新開始遊戲" title="重新開始">↺</button>
        </aside>

        {!dialogueOpen && nearNpc && (
          <button type="button" className="near-prompt" onClick={interactWithNpc}>
            <kbd>E</kbd> 與維達利亞交談
          </button>
        )}

        <div className="zoom-controls" aria-label="地圖縮放">
          <button type="button" onClick={() => zoomMap({ kind: "step", amount: MAP_ZOOM_STEP })} disabled={!ready || mapZoom >= MAX_MAP_ZOOM} aria-label="放大地圖" title="放大地圖">＋</button>
          <button type="button" className="zoom-level" onClick={() => zoomMap({ kind: "reset" })} disabled={!ready || mapZoom <= MIN_MAP_ZOOM} aria-label="恢復地圖原始大小" title="恢復原始大小">{Math.round(mapZoom * 100)}%</button>
          <button type="button" onClick={() => zoomMap({ kind: "step", amount: -MAP_ZOOM_STEP })} disabled={!ready || mapZoom <= MIN_MAP_ZOOM} aria-label="縮小地圖" title="縮小地圖">−</button>
        </div>

        {!dialogueOpen && <p className="control-hint">左鍵移動　·　右鍵轉向　·　Q／R 轉身　·　滾輪縮放</p>}

        <div className="touch-controls" aria-label="移動控制">
          <button type="button" className="touch-turn-left" onClick={() => turnPlayer(-1)} aria-label="向左轉身">↶</button>
          <button type="button" className="touch-up" onClick={() => movePlayer({ dx: 0, dy: -1 })} aria-label="向上移動">▲</button>
          <button type="button" className="touch-turn-right" onClick={() => turnPlayer(1)} aria-label="向右轉身">↷</button>
          <button type="button" className="touch-left" onClick={() => movePlayer({ dx: -1, dy: 0 })} aria-label="向左移動">◀</button>
          <button type="button" className="touch-down" onClick={() => movePlayer({ dx: 0, dy: 1 })} aria-label="向下移動">▼</button>
          <button type="button" className="touch-right" onClick={() => movePlayer({ dx: 1, dy: 0 })} aria-label="向右移動">▶</button>
        </div>

        <section className={`dialogue-panel ${dialogueOpen ? "is-open" : "is-preview"}`} aria-label="與維達利亞對話">
          <div className="dialogue-portrait">
            <Image src={profile.portrait_url} alt="維達利亞肖像" fill sizes="(max-width: 640px) 90px, 175px" />
          </div>
          <div className="dialogue-main">
            <div className="dialogue-heading">
              <div><h1>{profile.name}</h1><span className="turn-indicator">第 {String(turnNumber).padStart(2, "0")} 回合</span><span className={`generation-badge mode-${generationMode}`}>{generationMode === "external_model" ? "AI 動態" : "規則動態"}</span></div>
              {dialogueOpen && <button type="button" className="close-dialogue" onClick={() => setDialogueOpen(false)} aria-label="關閉對話">✕</button>}
            </div>

            {dialogueOpen ? (
              <>
                <div className="dialogue-history" aria-live="polite">
                  {messages.map((message) => <p key={message.id} className={`line-${message.kind}`}><span>{message.speaker}：</span>{message.text}</p>)}
                  {busy && ready && <p className="thinking">維達利亞正在思索……</p>}
                  <div ref={endRef} />
                </div>
                {playerChoices.length > 0 && (
                  <div className="dialogue-choices" aria-label="可選行動">
                    {playerChoices.map((choice) => (
                      <button key={choice.choice_id} type="button" disabled={!ready || busy} onClick={() => selectChoice(choice)}>
                        {choice.label}
                      </button>
                    ))}
                  </div>
                )}
                {error && <p className="dialogue-error" role="alert">{error}</p>}
                <form className="dialogue-form" onSubmit={submit}>
                  <label htmlFor="dialogue-input" className="sr-only">對維達利亞說話</label>
                  <input id="dialogue-input" value={input} onChange={(event) => { setInput(event.target.value); setInputType("text"); }} placeholder={ready ? (listening ? "正在聆聽……" : "說出你的想法……") : "等待後端連線……"} disabled={!ready || busy || listening} maxLength={2000} />
                  <button type="button" className={`voice-button ${listening ? "is-listening" : ""}`} onClick={toggleListening} disabled={!ready || busy || !voiceSupported} aria-label={listening ? "停止語音辨識" : "使用麥克風輸入"} title={voiceSupported ? "語音轉文字" : "瀏覽器不支援語音辨識"}>{listening ? "■" : "🎙"}</button>
                  <button type="button" className={`voice-button ${speaking ? "is-speaking" : ""}`} onClick={speakLastResponse} disabled={!ttsSupported || !lastNpcSpeech} aria-label={speaking ? "停止播放 NPC 回覆" : "播放 NPC 最近回覆"} title={speaking ? "停止播放" : "播放 NPC 最近回覆"}>{speaking ? "■" : "🔊"}</button>
                  <button type="submit" disabled={!ready || busy || !input.trim()}>送出 ↗</button>
                </form>
              </>
            ) : (
              <div className="dialogue-preview">
                <p>{previewLine}</p>
                <button type="button" className="talk-button" onClick={openDialogue}>對話 <span aria-hidden="true">❯</span></button>
              </div>
            )}
          </div>
        </section>

        {initializing && (
          <div className="game-overlay" role="status" aria-live="polite">
            <div className="game-overlay-card"><span className="overlay-rune">✧</span><h2>正在進入鳴霖</h2><p>命脈之泉的聲音，正漸漸清晰……</p><span className="loading-line" /></div>
          </div>
        )}

        {!initializing && !ready && (
          <div className="game-overlay" role="alert">
            <div className="game-overlay-card"><span className="overlay-rune">✧</span><h2>暫時無法進入鳴霖</h2><p>{error || "遊戲服務暫時沒有回應。"}</p><button type="button" onClick={() => void initialize(sessionId)}>重新連線</button></div>
          </div>
        )}

        {helpOpen && (
          <div className="game-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setHelpOpen(false); }}>
            <section className="game-overlay-card help-card" role="dialog" aria-modal="true" aria-label="操作說明">
              <button type="button" className="overlay-close" onClick={() => setHelpOpen(false)} aria-label="關閉說明">✕</button>
              <span className="overlay-rune">✧</span><h2>旅人指南</h2>
              <dl><div><dt>移動</dt><dd>左鍵點林間步道，或使用 WASD／方向鍵。角色會朝移動方向轉身。</dd></div><div><dt>縮放</dt><dd>滑鼠滾輪、右側 ＋／－，或手機雙指縮放。點倍率可恢復全景。</dd></div><div><dt>轉身</dt><dd>右鍵點想面對的方向，或按 Q／R 原地轉身；手機可用 ↶／↷。</dd></div><div><dt>交談</dt><dd>點擊維達利亞，或靠近後按 E。</dd></div><div><dt>返回</dt><dd>按 Esc 關閉對話與說明。</dd></div></dl>
              <button type="button" onClick={() => setHelpOpen(false)}>繼續探索</button>
            </section>
          </div>
        )}

        {restartConfirm && (
          <div className="game-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setRestartConfirm(false); }}>
            <section className="game-overlay-card" role="dialog" aria-modal="true" aria-label="重新開始遊戲">
              <span className="overlay-rune">✧</span><h2>重新開始旅程？</h2><p>角色會回到鳴霖入口，對話回合也會從頭開始。</p>
              <div className="overlay-actions"><button type="button" className="secondary-button" onClick={() => setRestartConfirm(false)}>繼續目前旅程</button><button type="button" onClick={restart}>重新開始</button></div>
            </section>
          </div>
        )}
      </section>
    </main>
  );
}
