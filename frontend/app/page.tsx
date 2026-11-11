"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import MinglinGame, { interactWithNpc, movePlayer, turnPlayer, zoomMap, MIN_MAP_ZOOM, MAX_MAP_ZOOM, MAP_ZOOM_STEP, type NpcId } from "../components/MinglinGame";
import WorldMap from "../components/WorldMap";
import { getSceneMusic } from "../lib/scene-music";
import { useSceneMusic } from "../lib/use-scene-music";
import {
  ApiRequestError,
  DEFAULT_SCENE_VISUAL_PROFILE,
  GAME_SESSION_STORAGE_KEY,
  requestJson,
  resolveSceneImage,
  type Capabilities,
  type GameStateSummary,
  type GameTurnResponse,
  type PlayerChoice,
  type PlayerScene,
  type PlayerNavigation,
} from "../lib/game-api";

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

type ChatMessage = {
  id: string;
  speaker: string;
  text: string;
  kind: "npc" | "player";
  npcId?: NpcId;
};

type PendingAction = {
  actionId: string;
  text: string;
  inputType: "text" | "speech_transcript";
  targetNpcId: string | null;
  actionMode: PlayerChoice["action_mode"];
  destinationSceneId: string | null;
  storyChoiceId: string | null;
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

const conversationKey = (id: string) => `vidalia-conversation:${id}`;
const legacyNpcDialogue: Record<string, string> = {
  "這裡是鳴霖的平衡議會。泉水在第一次入侵後停止擴張，而現在出現的失序值得重新調查。": "這裡是鳴霖的平衡議會。命脈之泉已經很久沒有向外延伸；最近又出現異象，我還不知道兩者是否相關。",
  "人族長老害怕失去輪迴，木乃伊則害怕被世界遺忘。他們都可能注意到唯一連著維塔意識的外來者。": "人族長老與流塵谷的居民都在留意這場異象。各自為何而來，還需要查證。",
  "結界若破裂，人族就失去下一世。長老想控制維塔的力量，但他真正知道多少仍需要證據。": "我們只知道長老會最近在泉水附近活動；他們的目的尚無確證。",
  "他們想被能返回外界的你記住。那不等於復活，卻是他們對抗遺忘的方式。": "流塵谷的人很重視記憶與名字。若你遇見他們，先聽他們說自己的故事。",
  "你沒有把長老的說法直接當成真相，而是記下他對失去下一世的恐懼與控制規則的企圖。": "長老會也在關注聖火，但你還沒有足夠證據判斷他們的目的。",
  "他們沒有因此獲得外部復活，卻把被你記住視為在世界之外留下存在的唯一方式。": "他們希望自己的名字不只留在沙裡。你記住了其中幾個，卻還不知道這份請求背後的原因。",
  "符石的缺口組成一張不穩定的裂隙地圖；它足以在追殺或崩塌發生時指向流塵谷。": "符石的缺口指向流塵谷。你記下這條暫定路線，準備前往查探。",
  "符石路徑在腳下崩解，你借助地圖標出的地理優勢甩開封閉路線，進入流塵谷。": "符石路徑在腳下崩解，你循著先前記下的風沙方向穿過裂隙，進入流塵谷。",
};

function migrateRecordedDialogue(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => {
    if (message.kind === "player" && message.text === "我把符石間的風沙軌跡拼成一張路線圖。") {
      return { ...message, text: "我從符石間的風沙軌跡辨認流塵谷的方向。" };
    }
    if (message.kind === "player" && message.text === "我依照裂隙地圖進入流塵谷。") {
      return { ...message, text: "我沿著符石間辨認的風沙方向進入流塵谷。" };
    }
    if (message.kind !== "npc") return message;
    const text = (legacyNpcDialogue[message.text] ?? message.text)
      .replaceAll("Demo 完成：長老的企圖", "Demo 完成：長老的行蹤")
      .replaceAll("裂隙地圖", "流塵谷的路標");
    return text === message.text ? message : { ...message, text };
  });
}

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

const previewAndreProfile: CharacterProfile = {
  npc_id: "andre",
  name: "安德烈",
  romanized_name: "Andre",
  title: "鳴霖精靈・邊界調查官",
  scene_name: "鳴霖・平衡議會",
  portrait_url: "/images/andre.png",
  description: "長年在各地邊界調查的精靈，正在查找命脈之泉與林地異象的線索。",
  greeting: "我剛從林地邊緣回來。最近的地脈有些異動；你在路上看見什麼異常嗎？",
};

const previewMenmesventoProfile: CharacterProfile = {
  npc_id: "menmesvento",
  name: "門梅司文托",
  romanized_name: "Menmesvento",
  title: "流塵谷隱者・古卷守護者",
  scene_name: "流塵谷",
  portrait_url: "/images/menmesvento.png",
  description: "在流塵谷記錄名字與記憶的隱者，言談沉靜，常攜著一本古卷。",
  greeting: "風沙會掩去腳印，名字卻值得留下。旅人，你是從哪條路來的？",
};

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

export default function Home() {
  const [profiles, setProfiles] = useState<Record<NpcId, CharacterProfile>>({ vidalia: previewProfile, andre: previewAndreProfile, menmesvento: previewMenmesventoProfile });
  const [activeNpcId, setActiveNpcId] = useState<NpcId>("vidalia");
  const [sessionId, setSessionId] = useState("");
  const [dialogueOpen, setDialogueOpen] = useState(false);
  const [nearNpcId, setNearNpcId] = useState<NpcId | null>(null);
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
  const [worldMapOpen, setWorldMapOpen] = useState(false);
  const [restartConfirm, setRestartConfirm] = useState(false);
  const [turnNumber, setTurnNumber] = useState(0);
  const [stateVersion, setStateVersion] = useState(1);
  const [scene, setScene] = useState<PlayerScene>(previewScene);
  const [navigation, setNavigation] = useState<PlayerNavigation | null>(null);
  const [sceneImageUrl, setSceneImageUrl] = useState(previewScene.background_url);
  const [sceneImageStatus, setSceneImageStatus] = useState<"queued" | "processing" | "succeeded" | "fallback">("fallback");
  const [generationMode, setGenerationMode] = useState<Capabilities["generation_mode"]>("rule_based");
  const [questLabel, setQuestLabel] = useState("與維達利亞交談");
  const [playerChoices, setPlayerChoices] = useState<PlayerChoice[]>([]);
  const [andreChoices, setAndreChoices] = useState<PlayerChoice[]>([]);
  const [menmesventoChoices, setMenmesventoChoices] = useState<PlayerChoice[]>([]);
  const [mapZoom, setMapZoom] = useState(MIN_MAP_ZOOM);
  const endRef = useRef<HTMLDivElement>(null);
  const pendingActionRef = useRef<PendingAction | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const sceneMusic = getSceneMusic(scene.scene_id);
  const music = useSceneMusic(sceneMusic.src, speaking ? 0.07 : dialogueOpen ? 0.11 : 0.2);
  const displayNpcId = dialogueOpen ? activeNpcId : nearNpcId ?? activeNpcId;
  const profile = profiles[displayNpcId];
  const visibleMessages = messages.filter((message) => (message.npcId ?? "vidalia") === displayNpcId);
  const visibleChoices = activeNpcId === "andre" ? andreChoices
    : activeNpcId === "menmesvento" ? [...menmesventoChoices, ...playerChoices]
      : playerChoices;

  useEffect(() => {
    if (scene.scene_id === "liuchen_valley") {
      setActiveNpcId("menmesvento");
      setLastNpcSpeech(previewMenmesventoProfile.greeting);
    } else if (scene.scene_id === "minglin") {
      setActiveNpcId("vidalia");
    }
    setNearNpcId(null);
  }, [scene.scene_id]);

  useEffect(() => {
    const id = window.localStorage.getItem(GAME_SESSION_STORAGE_KEY) ?? window.crypto.randomUUID();
    window.localStorage.setItem(GAME_SESSION_STORAGE_KEY, id);
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
    if (!ready || !sessionId) return;
    let current = true;
    setSceneImageUrl(scene.background_url);
    setSceneImageStatus("queued");
    void resolveSceneImage(sessionId, stateVersion, () => current)
      .then((job) => {
        if (!current || !job || job.scene_id !== scene.scene_id) return;
        setSceneImageStatus(job.status);
        if (job.image_url) setSceneImageUrl(job.image_url);
      })
      .catch(() => {
        if (current) setSceneImageStatus("fallback");
      });
    return () => { current = false; };
  }, [ready, scene.background_url, scene.scene_id, sessionId, stateVersion]);

  useEffect(() => {
    if (dialogueOpen) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, dialogueOpen]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHelpOpen(false);
        setWorldMapOpen(false);
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
      const [character, andre, menmesvento, state, capabilities] = await Promise.all([
        requestJson<CharacterProfile>("/api/characters/vidalia"),
        requestJson<CharacterProfile>("/api/characters/andre"),
        requestJson<CharacterProfile>("/api/characters/menmesvento"),
        requestJson<GameStateSummary>("/api/game/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: id }),
        }),
        requestJson<Capabilities>("/api/capabilities"),
      ]);
      setProfiles({ vidalia: character, andre, menmesvento });
      setGenerationMode(capabilities.generation_mode);
      const [choices, andreOptions, menmesventoOptions] = await Promise.all([
        requestJson<PlayerChoice[]>(`/api/game/${id}/choices`),
        requestJson<PlayerChoice[]>(`/api/game/${id}/choices?npc_id=andre`),
        requestJson<PlayerChoice[]>(`/api/game/${id}/choices?npc_id=menmesvento`),
      ]);
      setQuestLabel(`故事進度：${state.story_progress.chapter_title}`);
      setPlayerChoices(choices);
      setAndreChoices(andreOptions);
      setMenmesventoChoices(menmesventoOptions);
      setTurnNumber(state.turn_count);
      setStateVersion(state.state_version);
      setScene(state.current_scene);
      setNavigation(state.navigation ?? null);
      const fallback: ChatMessage[] = [{ id: window.crypto.randomUUID(), speaker: character.name, text: character.greeting, kind: "npc" }];
      let restored = fallback;
      try {
        const cached = JSON.parse(window.localStorage.getItem(conversationKey(id)) ?? "null");
        if (cached?.turn_number === state.turn_count && cached?.updated_at === state.updated_at &&
          Array.isArray(cached.messages) && cached.messages.length > 0 &&
          cached.messages.every((message: ChatMessage) => typeof message.id === "string" &&
            typeof message.speaker === "string" && typeof message.text === "string" &&
            (message.kind === "npc" || message.kind === "player"))) {
          restored = migrateRecordedDialogue(cached.messages);
          if (restored.some((message, index) => message !== cached.messages[index])) {
            window.localStorage.setItem(conversationKey(id), JSON.stringify({ ...cached, messages: restored }));
          }
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

  const openDialogue = useCallback((npcId: NpcId) => {
    setActiveNpcId(npcId);
    setLastNpcSpeech(messages.filter((message) => message.kind === "npc" && (message.npcId ?? "vidalia") === npcId).at(-1)?.text ?? profiles[npcId].greeting);
    setHelpOpen(false);
    setDialogueOpen(true);
  }, [messages, profiles]);

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
      retryingPending ? pending.targetNpcId : activeNpcId,
      retryingPending ? pending.actionMode : "dialogue",
      retryingPending ? pending.destinationSceneId : null,
      retryingPending ? pending.storyChoiceId : null,
    );
  }

  function selectChoice(choice: PlayerChoice) {
    void sendAction(
      choice.message,
      "text",
      choice.target_npc_id,
      choice.action_mode,
      choice.destination_scene_id,
      choice.story_choice_id,
    );
  }

  async function sendAction(
    text: string,
    actionInputType: "text" | "speech_transcript",
    targetNpcId: string | null,
    actionMode: PlayerChoice["action_mode"],
    destinationSceneId: string | null,
    storyChoiceId: string | null,
  ) {
    if (!text || !ready || busy) return;

    setInput("");
    setInputType("text");
    setBusy(true);
    setError("");
    const messageNpcId: NpcId = targetNpcId === "andre" || targetNpcId === "menmesvento" ? targetNpcId : activeNpcId;
    setMessages((current) => [...current, { id: window.crypto.randomUUID(), speaker: "你", text, kind: "player", npcId: messageNpcId }]);
    const pending = pendingActionRef.current;
    const canRetryPending = pending?.text === text && pending.inputType === actionInputType && pending.targetNpcId === targetNpcId && pending.actionMode === actionMode && pending.destinationSceneId === destinationSceneId && pending.storyChoiceId === storyChoiceId && pending.expectedStateVersion === stateVersion;
    const actionId = canRetryPending ? pending.actionId : window.crypto.randomUUID();
    pendingActionRef.current = { actionId, text, inputType: actionInputType, targetNpcId, actionMode, destinationSceneId, storyChoiceId, expectedStateVersion: stateVersion };

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
          destination_scene_id: destinationSceneId,
          story_choice_id: storyChoiceId,
          expected_state_version: stateVersion,
        }),
      });
      pendingActionRef.current = null;
      setTurnNumber(turn.turn_number);
      setStateVersion(turn.state.state_version);
      setScene(turn.state.current_scene);
      setNavigation(turn.state.navigation ?? null);
      setQuestLabel(`故事進度：${turn.state.story_progress.chapter_title}`);
      try {
        const choices = await requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`);
        setPlayerChoices(choices);
      } catch { /* The committed turn remains valid if the optional quest refresh fails. */ }
      const nextMessages: ChatMessage[] = [...messages, { id: window.crypto.randomUUID(), speaker: "你", text, kind: "player", npcId: messageNpcId }, ...turn.story.dialogue.map((line) => ({
        id: window.crypto.randomUUID(), speaker: line.speaker_name, text: line.text, kind: "npc" as const, npcId: messageNpcId,
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
          setScene(latest.current_scene);
          setNavigation(latest.navigation ?? null);
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
    window.localStorage.setItem(GAME_SESSION_STORAGE_KEY, id);
    setDialogueOpen(false);
    setRestartConfirm(false);
    setHelpOpen(false);
    setWorldMapOpen(false);
    setNearNpcId(null);
    setActiveNpcId("vidalia");
    setInput("");
    setInputType("text");
    pendingActionRef.current = null;
    void initialize(id);
  }

  const previewLine = displayNpcId === "vidalia" && turnNumber === 0
    ? "……你來了。"
    : visibleMessages.filter((message) => message.kind === "npc").at(-1)?.text ?? profile.greeting;

  return (
    <main className="game-page">
      <audio
        ref={music.audioRef}
        src={sceneMusic.src}
        loop
        preload="none"
        onPlay={music.onPlay}
        onPause={music.onPause}
        onError={music.onError}
      />
      <section className="map-stage" aria-label={`斜俯視的${scene.region_name}遊戲地圖`}>
        {sessionId && <MinglinGame key={`${sessionId}:${scene.scene_id}:${sceneImageUrl}`} backgroundUrl={sceneImageUrl} sceneId={scene.scene_id} sceneName={scene.region_name} paused={dialogueOpen || helpOpen || worldMapOpen || restartConfirm || initializing || !ready} onNearChange={setNearNpcId} onInteract={openDialogue} onZoomChange={setMapZoom} />}
        <div className="scene-vignette" aria-hidden="true" />

        <header className="location-banner" aria-label="目前場景">
          <svg className="compass-mark" viewBox="0 0 72 72" fill="none" aria-hidden="true">
            <circle cx="36" cy="36" r="24" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="36" cy="36" r="16" stroke="currentColor" strokeWidth="0.8" />
            <path d="M36 3l6 27 27 6-27 6-6 27-6-27L3 36l27-6L36 3Z" stroke="currentColor" strokeWidth="1.7" />
            <path d="M36 22l4 10 10 4-10 4-4 10-4-10-10-4 10-4 4-10Z" fill="currentColor" />
          </svg>
          <div className="location-copy"><strong>{scene.region_name}</strong><span>{scene.display_name} · {scene.subtitle} · {sceneImageStatus === "succeeded" ? "生成場景" : sceneImageStatus === "fallback" ? "版本化場景" : "場景生成中"}</span></div>
          <span className="location-ornament" aria-hidden="true">✧</span>
        </header>

        <WorldMap sceneId={scene.scene_id} sceneName={`${scene.region_name}・${scene.display_name}`} expanded={worldMapOpen} onExpandedChange={setWorldMapOpen} navigation={navigation} />

        <button
          type="button"
          className={`music-toggle ${music.playing ? "is-playing" : ""}`}
          onClick={() => void music.toggle()}
          aria-label={music.error ? `${music.error}點擊重試` : music.playing ? `關閉${sceneMusic.title}背景音樂` : `播放${sceneMusic.title}背景音樂`}
          aria-pressed={music.playing}
          title={music.error || (music.playing ? `關閉${sceneMusic.title}背景音樂` : `播放${sceneMusic.title}背景音樂`)}
        >♫ {music.error ? "重試音樂" : music.playing ? "音樂開" : "播放音樂"}</button>

        <aside className="quest-banner" aria-label="目前任務">
          <span className="quest-emblem" aria-hidden="true">◇</span>
          <span>{questLabel}</span>
          <button type="button" className="help-button" onClick={() => setHelpOpen(true)} aria-label="查看操作說明" title="操作說明">?</button>
          <button type="button" className="restart-button" onClick={() => setRestartConfirm(true)} disabled={busy} aria-label="重新開始遊戲" title="重新開始">↺</button>
        </aside>

        {!dialogueOpen && nearNpcId && (
          <button type="button" className="near-prompt" onClick={interactWithNpc}>
            <kbd>E</kbd> 與{profiles[nearNpcId].name}交談
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

        <section className={`dialogue-panel ${dialogueOpen ? "is-open" : "is-preview"}`} aria-label={`與${profile.name}對話`}>
          <div className="dialogue-portrait">
            <Image src={profile.portrait_url} alt={`${profile.name}肖像`} fill sizes="(max-width: 640px) 90px, 175px" />
          </div>
          <div className="dialogue-main">
            <div className="dialogue-heading">
              <div><h1>{profile.name}</h1><span className="turn-indicator">第 {String(turnNumber).padStart(2, "0")} 回合</span><span className={`generation-badge mode-${generationMode}`}>{generationMode === "external_model" ? "AI 動態" : "規則動態"}</span></div>
              {dialogueOpen && <button type="button" className="close-dialogue" onClick={() => setDialogueOpen(false)} aria-label="關閉對話">✕</button>}
            </div>

            {dialogueOpen ? (
              <>
                <div className="dialogue-history" aria-live="polite">
                  {visibleMessages.length === 0 && <p className="line-npc"><span>{profile.name}：</span>{profile.greeting}</p>}
                  {visibleMessages.map((message) => <p key={message.id} className={`line-${message.kind}`}><span>{message.speaker}：</span>{message.text}</p>)}
                  {busy && ready && <p className="thinking">{profile.name}正在思索……</p>}
                  <div ref={endRef} />
                </div>
                {visibleChoices.length > 0 && (
                  <div className="dialogue-choices" aria-label="可選行動">
                    {visibleChoices.map((choice) => (
                      <button key={choice.choice_id} type="button" disabled={!ready || busy} onClick={() => selectChoice(choice)}>
                        {choice.label}
                      </button>
                    ))}
                  </div>
                )}
                {error && <p className="dialogue-error" role="alert">{error}</p>}
                <form className="dialogue-form" onSubmit={submit}>
                  <label htmlFor="dialogue-input" className="sr-only">對{profile.name}說話</label>
                  <input id="dialogue-input" value={input} onChange={(event) => { setInput(event.target.value); setInputType("text"); }} placeholder={ready ? (listening ? "正在聆聽……" : "說出你的想法……") : "等待後端連線……"} disabled={!ready || busy || listening} maxLength={2000} />
                  <button type="button" className={`voice-button ${listening ? "is-listening" : ""}`} onClick={toggleListening} disabled={!ready || busy || !voiceSupported} aria-label={listening ? "停止語音辨識" : "使用麥克風輸入"} title={voiceSupported ? "語音轉文字" : "瀏覽器不支援語音辨識"}>{listening ? "■" : "🎙"}</button>
                  <button type="button" className={`voice-button ${speaking ? "is-speaking" : ""}`} onClick={speakLastResponse} disabled={!ttsSupported || !lastNpcSpeech} aria-label={speaking ? "停止播放 NPC 回覆" : "播放 NPC 最近回覆"} title={speaking ? "停止播放" : "播放 NPC 最近回覆"}>{speaking ? "■" : "🔊"}</button>
                  <button type="submit" disabled={!ready || busy || !input.trim()}>送出 ↗</button>
                </form>
              </>
            ) : (
              <div className="dialogue-preview">
                <p>{previewLine}</p>
                <button type="button" className="talk-button" onClick={() => openDialogue(displayNpcId)}>對話 <span aria-hidden="true">❯</span></button>
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
              <dl><div><dt>移動</dt><dd>左鍵點道路，或使用 WASD／方向鍵。角色會朝移動方向轉身。</dd></div><div><dt>旅途地圖</dt><dd>點左上角地圖可查看鳴霖、流塵谷、烈燚原及路線；青色光點標示目前場景。前往各地仍依劇情選項。</dd></div><div><dt>縮放</dt><dd>滑鼠滾輪、右側 ＋／－，或手機雙指縮放。點倍率可恢復全景。</dd></div><div><dt>轉身</dt><dd>右鍵點想面對的方向，或按 Q／R 原地轉身；手機可用 ↶／↷。</dd></div><div><dt>交談</dt><dd>鳴霖可與維達利亞、安德烈交談；流塵谷可與門梅司文托交談。點擊角色，或靠近後按 E。</dd></div><div><dt>音樂</dt><dd>右上角可播放或關閉背景音樂。</dd></div><div><dt>返回</dt><dd>按 Esc 關閉對話、地圖與說明。</dd></div></dl>
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
