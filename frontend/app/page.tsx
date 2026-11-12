"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import MinglinGame, { approachTarget, isNpcId, interactWithTarget, movePlayer, turnPlayer, zoomMap, MIN_MAP_ZOOM, MAX_MAP_ZOOM, MAP_ZOOM_STEP, type NpcId, type InteractionTarget } from "../components/MinglinGame";
import WorldMap from "../components/WorldMap";
import InvestigationJournal from "../components/InvestigationJournal";
import { getSceneMusic } from "../lib/scene-music";
import { useSceneMusic } from "../lib/use-scene-music";
import {
  ApiRequestError,
  DEFAULT_SCENE_VISUAL_PROFILE,
  GAME_SESSION_STORAGE_KEY,
  requestJson,
  type Capabilities,
  type GameStateSummary,
  type GameTurnResponse,
  type PlayerChoice,
  type PlayerScene,
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
  targetId?: InteractionTarget;
  sceneId?: string;
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
const CONVERSATION_FORMAT_VERSION = 2;
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

const previewDassoProfile: CharacterProfile = {
  npc_id: "dasso",
  name: "達索",
  romanized_name: "Dasso",
  title: "首席長老・火焰長老會",
  scene_name: "烈燚原",
  portrait_url: "/images/dasso.jpg",
  description: "掌管火焰長老會的首席長老。",
  greeting: "旅人，烈燚原的火焰不會替任何人回答問題。你想知道什麼？",
};

const previewSethProfile: CharacterProfile = {
  npc_id: "seth",
  name: "塞特",
  romanized_name: "Seth",
  title: "木乃伊旅人・邊境逃亡者",
  scene_name: "邊境廢墟",
  portrait_url: "/images/seth.jpg",
  description: "披著抗熱斗篷、以繃帶掩面，在邊境尋找出路的木乃伊。",
  greeting: "別叫我的名字……我已經記得太多了。你能帶我離開這裡嗎？",
};

const previewSyraProfile: CharacterProfile = {
  npc_id: "syra",
  name: "希拉",
  romanized_name: "Syra",
  title: "人族記錄員・邊境逃亡者",
  scene_name: "邊境廢墟",
  portrait_url: "/images/syra.jpg",
  description: "緊抱個人記錄盒、穿著破損圖書館制服的年輕人族。",
  greeting: "這盒子裡記著我這一世的事。請別讓他們把它拿走。",
};

const previewScene: PlayerScene = {
  scene_id: "minglin",
  region_name: "鳴霖",
  display_name: "平衡議會",
  subtitle: "古林中的議會庭",
  description: "維達利亞接見旅人的林間議會庭。",
  background_url: "/game/forest-council.png",
  horizon_url: "/game/forest-eye-backdrop.png",
  tilemap_url: "/game/minglin.tmj",
  visual_profile: DEFAULT_SCENE_VISUAL_PROFILE,
  canon_status: "confirmed",
};

export default function Home() {
  const [profiles, setProfiles] = useState<Record<NpcId, CharacterProfile>>({
    vidalia: previewProfile, andre: previewAndreProfile, menmesvento: previewMenmesventoProfile,
    dasso: previewDassoProfile, seth: previewSethProfile, syra: previewSyraProfile,
  });
  const [activeNpcId, setActiveNpcId] = useState<NpcId>("vidalia");
  const [sessionId, setSessionId] = useState("");
  const [dialogueOpen, setDialogueOpen] = useState(false);
  const [nearTarget, setNearTarget] = useState<InteractionTarget | null>(null);
  const [activeLandmark, setActiveLandmark] = useState(false);
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
  const [journalOpen, setJournalOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [trackedChoice, setTrackedChoice] = useState<string | null>(null);
  const [restartConfirm, setRestartConfirm] = useState(false);
  const [gameState, setGameState] = useState<GameStateSummary | null>(null);
  const scene = gameState?.current_scene ?? previewScene;
  const turnNumber = gameState?.turn_count ?? 0;
  const stateVersion = gameState?.state_version ?? 1;
  const navigation = gameState?.navigation;
  const findings = gameState?.story_progress.findings ?? [];
  const sceneImageUrl = scene.background_url;
  const [generationMode, setGenerationMode] = useState<Capabilities["generation_mode"]>("rule_based");
  const questLabel = gameState?.story_progress.chapter_title ?? "鳴霖異象";
  const [playerChoices, setPlayerChoices] = useState<PlayerChoice[]>([]);
  const [npcChoiceSet, setNpcChoiceSet] = useState<{npcId: NpcId; choices: PlayerChoice[]} | null>(null);
  const [mapZoom, setMapZoom] = useState(MIN_MAP_ZOOM);
  const endRef = useRef<HTMLDivElement>(null);
  const pendingActionRef = useRef<PendingAction | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const pendingApproach = useRef<string | null>(null);
  const sceneMusic = getSceneMusic(scene.scene_id);
  const music = useSceneMusic(sceneMusic.src, speaking ? 0.07 : dialogueOpen ? 0.11 : 0.2);
  const primaryNpc = gameState?.world_scene.npc_id ?? gameState?.world_scene.npc_interactions?.[0]?.npc_id;
  const primaryTarget: InteractionTarget = isNpcId(primaryNpc) ? primaryNpc : "landmark";
  const displayNpcId = dialogueOpen ? activeNpcId : nearTarget && nearTarget !== "landmark" ? nearTarget : activeNpcId;
  const profile = profiles[displayNpcId];
  const visibleMessages = messages.filter(message => activeLandmark
    ? message.targetId === "landmark" && message.sceneId === scene.scene_id
    : message.targetId !== "landmark" && (message.npcId ?? "vidalia") === displayNpcId);
  const sceneChoices = gameState?.world_scene.npc_id === activeNpcId
    ? playerChoices : playerChoices.filter(choice => choice.action_mode === "movement" || choice.target_npc_id === activeNpcId);
  const npcChoices = npcChoiceSet?.npcId === activeNpcId ? npcChoiceSet.choices : [];
  const visibleChoices = activeLandmark ? playerChoices
    : activeNpcId === "vidalia" && scene.scene_id === "minglin" ? sceneChoices
      : [...(activeNpcId === "andre" ? [] : sceneChoices), ...npcChoices].slice(0, 4);
  const reportChoice = playerChoices.find(choice => choice.choice_id === "review_demo_findings");

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (scene.scene_id === "liuchen_valley") {
      setActiveNpcId("menmesvento");
      setLastNpcSpeech(previewMenmesventoProfile.greeting);
    } else if (scene.scene_id === "lieyi_plains") {
      setActiveNpcId("dasso");
      setLastNpcSpeech(previewDassoProfile.greeting);
    } else if (scene.scene_id === "border_ruins") {
      setActiveNpcId("seth");
      setLastNpcSpeech(previewSethProfile.greeting);
    } else if (scene.scene_id === "minglin" || scene.scene_id === "minglin_life_spring") {
      setActiveNpcId("vidalia");
    }
    setNearTarget(null);
    setActiveLandmark(false);
    setDialogueOpen(false);
    pendingApproach.current = null;
    setTrackedChoice(null);
  }, [scene.scene_id]);

  useEffect(() => {
    if (!ready || !sessionId) return;
    let current = true;
    if (!dialogueOpen || activeLandmark || activeNpcId === "vidalia" && scene.scene_id === "minglin") return;
    setNpcChoiceSet(null);
    void requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices?npc_id=${activeNpcId}`)
      .then(choices => { if (current) setNpcChoiceSet({npcId: activeNpcId, choices}); })
      .catch(() => { /* Free dialogue remains available if shortcuts fail. */ });
    return () => { current = false; };
  }, [ready, dialogueOpen, activeLandmark, activeNpcId, scene.scene_id, sessionId, stateVersion]);

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
    if (dialogueOpen) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, dialogueOpen]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHelpOpen(false);
        setWorldMapOpen(false);
        setRestartConfirm(false);
        setDialogueOpen(false);
        setJournalOpen(false);
      }
      if (event.target instanceof HTMLElement && event.target.closest("input,textarea,[contenteditable=true]")) return;
      if (event.repeat) return;
      if (event.code === "KeyM") { setWorldMapOpen(value => !value); setDialogueOpen(false); setJournalOpen(false); }
      if (event.code === "KeyJ") { setJournalOpen(value => !value); setDialogueOpen(false); setWorldMapOpen(false); }
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
      const [character, andre, menmesvento, dasso, seth, syra, state, capabilities] = await Promise.all([
        requestJson<CharacterProfile>("/api/characters/vidalia"),
        requestJson<CharacterProfile>("/api/characters/andre"),
        requestJson<CharacterProfile>("/api/characters/menmesvento"),
        requestJson<CharacterProfile>("/api/characters/dasso"),
        requestJson<CharacterProfile>("/api/characters/seth"),
        requestJson<CharacterProfile>("/api/characters/syra"),
        requestJson<GameStateSummary>("/api/game/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: id }),
        }),
        requestJson<Capabilities>("/api/capabilities"),
      ]);
      setProfiles({ vidalia: character, andre, menmesvento, dasso, seth, syra });
      setGenerationMode(capabilities.generation_mode);
      setPlayerChoices(await requestJson<PlayerChoice[]>(`/api/game/${id}/choices`));
      setGameState(state);
      const fallback: ChatMessage[] = [{ id: window.crypto.randomUUID(), speaker: character.name, text: character.greeting, kind: "npc" }];
      let restored = fallback;
      try {
        const cached = JSON.parse(window.localStorage.getItem(conversationKey(id)) ?? "null");
        if (cached?.turn_number === state.turn_count && cached?.updated_at === state.updated_at &&
          Array.isArray(cached.messages) && cached.messages.length > 0 &&
          cached.messages.every((message: ChatMessage) => typeof message.id === "string" &&
            typeof message.speaker === "string" && typeof message.text === "string" &&
            (message.kind === "npc" || message.kind === "player"))) {
          restored = cached.format_version === CONVERSATION_FORMAT_VERSION ? cached.messages : migrateRecordedDialogue(cached.messages);
          if (cached.format_version !== CONVERSATION_FORMAT_VERSION) {
            window.localStorage.setItem(conversationKey(id), JSON.stringify({ ...cached, format_version: CONVERSATION_FORMAT_VERSION, messages: restored }));
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

  const openDialogue = useCallback((targetId: InteractionTarget) => {
    const landmark = targetId === "landmark";
    setActiveLandmark(landmark);
    if (!landmark) {
      setActiveNpcId(targetId);
      setLastNpcSpeech(messages.filter(message => message.kind === "npc" && (message.npcId ?? "vidalia") === targetId).at(-1)?.text ?? profiles[targetId].greeting);
    }
    if (pendingApproach.current) {
      setTrackedChoice(pendingApproach.current);
      pendingApproach.current = null;
      setNotice("已抵達，請選擇行動繼續。");
    }
    setHelpOpen(false);
    setWorldMapOpen(false);
    setJournalOpen(false);
    setDialogueOpen(true);
  }, [messages, profiles]);

  function requestChoice(choice: PlayerChoice) {
    setWorldMapOpen(false);
    setJournalOpen(false);
    if (nearTarget === primaryTarget) {
      openDialogue(primaryTarget);
      selectChoice(choice);
    } else {
      pendingApproach.current = choice.choice_id;
      setNotice("正走向人物或地標，抵達後確認行動。");
      approachTarget(primaryTarget);
    }
  }

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
    const messageNpcId: NpcId = isNpcId(targetNpcId) ? targetNpcId : activeNpcId;
    const messageTarget: InteractionTarget = isNpcId(targetNpcId) ? targetNpcId : activeLandmark ? "landmark" : primaryTarget;
    const playerLine: ChatMessage = { id: window.crypto.randomUUID(), speaker:"你", text, kind:"player", npcId:messageNpcId, targetId:messageTarget, sceneId:scene.scene_id };
    setMessages(current => [...current, playerLine]);
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
      setGameState(turn.state);
      setTrackedChoice(null);
      const count = turn.state.story_progress.findings?.length ?? 0;
      setNotice(count > findings.length ? `新的調查已記錄。按 J 查看 ${count} 項紀錄。` : `故事進度：${turn.state.story_progress.chapter_title}`);
      try {
        const choices = await requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`);
        setPlayerChoices(choices);
      } catch { /* The committed turn remains valid if the optional quest refresh fails. */ }
      const nextMessages: ChatMessage[] = [...messages, playerLine, ...turn.story.dialogue.map((line) => ({
        id: window.crypto.randomUUID(), speaker: line.speaker_name, text: line.text, kind: "npc" as const, npcId: messageNpcId, targetId:messageTarget, sceneId:scene.scene_id,
      }))];
      setMessages(nextMessages);
      setLastNpcSpeech(turn.story.dialogue.filter((line) => line.speaker_name !== "系統").map((line) => line.text).join("\n"));
      try {
        window.localStorage.setItem(conversationKey(sessionId), JSON.stringify({ format_version: CONVERSATION_FORMAT_VERSION, turn_number: turn.turn_number, updated_at: turn.state.updated_at, messages: nextMessages }));
      } catch { /* The current conversation still works when browser storage is unavailable. */ }
    } catch (cause) {
      if (cause instanceof ApiRequestError && ["STATE_VERSION_CONFLICT", "STORY_CHOICE_UNAVAILABLE", "STORY_CHOICE_MISMATCH", "NPC_UNAVAILABLE"].includes(cause.code ?? "")) {
        pendingActionRef.current = null;
        try {
          const latest = await requestJson<GameStateSummary>(`/api/game/${sessionId}/state`);
          setGameState(latest);
          setPlayerChoices(await requestJson<PlayerChoice[]>(`/api/game/${sessionId}/choices`));
          setError("進度或選項已更新，已同步目前內容；請確認後重新選擇。");
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
    setJournalOpen(false);
    setNearTarget(null);
    setActiveLandmark(false);
    pendingApproach.current = null;
    setActiveNpcId("vidalia");
    setInput("");
    setInputType("text");
    pendingActionRef.current = null;
    void initialize(id);
  }

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
        {sessionId && <MinglinGame key={`${sessionId}:${scene.scene_id}:${sceneImageUrl}`} backgroundUrl={sceneImageUrl} sceneId={scene.scene_id} tilemapUrl={scene.tilemap_url} sceneName={scene.display_name} npcNames={Object.fromEntries(Object.entries(profiles).map(([id, profile]) => [id, profile.name])) as Record<NpcId, string>} paused={dialogueOpen || helpOpen || worldMapOpen || journalOpen || restartConfirm || busy || initializing || !ready} onNearChange={setNearTarget} onInteract={openDialogue} onZoomChange={setMapZoom} />}
        <div className="scene-vignette" aria-hidden="true" />

        <header className="location-banner" aria-label="目前場景">
          <svg className="compass-mark" viewBox="0 0 72 72" fill="none" aria-hidden="true">
            <circle cx="36" cy="36" r="24" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="36" cy="36" r="16" stroke="currentColor" strokeWidth="0.8" />
            <path d="M36 3l6 27 27 6-27 6-6 27-6-27L3 36l27-6L36 3Z" stroke="currentColor" strokeWidth="1.7" />
            <path d="M36 22l4 10 10 4-10 4-4 10-4-10-10-4 10-4 4-10Z" fill="currentColor" />
          </svg>
          <div className="location-copy"><strong>{scene.display_name}</strong><span>{scene.region_name} · {scene.subtitle} · 2D 探索</span></div>
          <span className="location-ornament" aria-hidden="true">✧</span>
        </header>

        <WorldMap sceneId={scene.scene_id} sceneName={scene.region_name === scene.display_name ? scene.display_name : `${scene.region_name}・${scene.display_name}`} expanded={worldMapOpen} onExpandedChange={open => {setWorldMapOpen(open);if(open){setDialogueOpen(false);setJournalOpen(false);}}} navigation={navigation} onTravel={requestChoice} near={nearTarget===primaryTarget} busy={busy} />

        <div className="game-toolbar">
        <button className="journal-toggle" onClick={()=>{setJournalOpen(true);setDialogueOpen(false);setWorldMapOpen(false);}}>手記 {findings.length} <kbd>J</kbd></button>
        <button
          type="button"
          className={`music-toggle ${music.playing ? "is-playing" : ""}`}
          onClick={() => void music.toggle()}
          aria-label={music.error ? `${music.error}點擊重試` : music.playing ? `關閉${sceneMusic.title}背景音樂` : `播放${sceneMusic.title}背景音樂`}
          aria-pressed={music.playing}
          title={music.error || (music.playing ? `關閉${sceneMusic.title}背景音樂` : `播放${sceneMusic.title}背景音樂`)}
        >♫ {music.error ? "重試音樂" : music.playing ? "音樂開" : "播放音樂"}</button>
        </div>

        <aside className="quest-banner" aria-label="目前任務">
          <span className="quest-emblem" aria-hidden="true">◇</span>
          <span><small>第 {turnNumber} 回合 · {generationMode === "external_model" ? "AI 互動" : "規則式劇情"}</small><strong>{questLabel}</strong></span>
          <button type="button" className="help-button" onClick={() => setHelpOpen(true)} aria-label="查看操作說明" title="操作說明">?</button>
          <button type="button" className="restart-button" onClick={() => setRestartConfirm(true)} disabled={busy} aria-label="重新開始遊戲" title="重新開始">↺</button>
        </aside>

        {!dialogueOpen && nearTarget && (
          <button type="button" className="near-prompt" onClick={interactWithTarget}>
            <kbd>E</kbd> {nearTarget === "landmark" ? gameState?.world_scene.interaction_label ?? "調查地標" : `與${profiles[nearTarget].name}交談`}
          </button>
        )}

        <div className="zoom-controls" aria-label="地圖縮放">
          <button type="button" onClick={() => zoomMap({ kind: "step", amount: MAP_ZOOM_STEP })} disabled={!ready || mapZoom >= MAX_MAP_ZOOM} aria-label="放大地圖" title="放大地圖">＋</button>
          <button type="button" className="zoom-level" onClick={() => zoomMap({ kind: "reset" })} disabled={!ready || mapZoom <= MIN_MAP_ZOOM} aria-label="恢復地圖原始大小" title="恢復原始大小">{Math.round(mapZoom * 100)}%</button>
          <button type="button" onClick={() => zoomMap({ kind: "step", amount: -MAP_ZOOM_STEP })} disabled={!ready || mapZoom <= MIN_MAP_ZOOM} aria-label="縮小地圖" title="縮小地圖">−</button>
        </div>

        {!dialogueOpen && <div className="exploration-status"><p>{navigation?.objective ?? "走近維達利亞，開始調查。"}</p><small>{notice || "WASD／點地面移動 · E 互動 · M 地圖 · J 手記 · 滾輪縮放"}</small></div>}

        <div className="touch-controls" aria-label="移動控制">
          <button type="button" className="touch-turn-left" onClick={() => turnPlayer(-1)} aria-label="向左轉身">↶</button>
          <button type="button" className="touch-up" onClick={() => movePlayer({ dx: 0, dy: -1 })} aria-label="向上移動">▲</button>
          <button type="button" className="touch-turn-right" onClick={() => turnPlayer(1)} aria-label="向右轉身">↷</button>
          <button type="button" className="touch-left" onClick={() => movePlayer({ dx: -1, dy: 0 })} aria-label="向左移動">◀</button>
          <button type="button" className="touch-down" onClick={() => movePlayer({ dx: 0, dy: 1 })} aria-label="向下移動">▼</button>
          <button type="button" className="touch-right" onClick={() => movePlayer({ dx: 1, dy: 0 })} aria-label="向右移動">▶</button>
        </div>

        {dialogueOpen && <section className={`dialogue-panel is-open ${activeLandmark ? "is-landmark" : ""}`} aria-label={activeLandmark ? scene.display_name : `與${profile.name}對話`}>
          {!activeLandmark && <div className={`dialogue-portrait npc-${displayNpcId}`}>
            <Image src={profile.portrait_url} alt={`${profile.name}肖像`} fill sizes="(max-width: 640px) 90px, 175px" />
          </div>}
          <div className="dialogue-main">
            <div className="dialogue-heading">
              <div><h1>{activeLandmark ? scene.display_name : profile.name}</h1>{!activeLandmark && <span className="dialogue-title">{profile.title}</span>}<span className="turn-indicator">第 {String(turnNumber).padStart(2, "0")} 回合</span><span className={`generation-badge mode-${generationMode}`}>{generationMode === "external_model" ? "AI 互動" : "規則式劇情"}</span></div>
              <button type="button" className="close-dialogue" onClick={() => setDialogueOpen(false)} aria-label="關閉對話">✕</button>
            </div>

              <>
                <div className="dialogue-history" aria-live="polite">
                  {visibleMessages.length === 0 && <p className="line-npc">{activeLandmark ? scene.description : profile.greeting}</p>}
                  {visibleMessages.map((message) => <p key={message.id} className={`line-${message.kind}`}><span>{message.speaker}：</span>{message.text}</p>)}
                  {busy && ready && <p className="thinking">{activeLandmark ? "正在整理調查結果……" : `${profile.name}正在思索……`}</p>}
                  <div ref={endRef} />
                </div>
                <p className="dialogue-next">{navigation?.objective}</p>
                {visibleChoices.length > 0 && (
                  <div className="dialogue-choices" aria-label="可選行動">
                    {visibleChoices.map((choice) => (
                      <button key={choice.choice_id} className={trackedChoice===choice.choice_id ? "is-tracked" : ""} type="button" disabled={!ready || busy} onClick={() => selectChoice(choice)}>
                        {choice.label}
                      </button>
                    ))}
                  </div>
                )}
                {error && <p className="dialogue-error" role="alert">{error}</p>}
                {!activeLandmark && <form className="dialogue-form" onSubmit={submit}>
                  <label htmlFor="dialogue-input" className="sr-only">對{profile.name}說話</label>
                  <input id="dialogue-input" value={input} onChange={(event) => { setInput(event.target.value); setInputType("text"); }} placeholder={ready ? (listening ? "正在聆聽……" : "說出你的想法……") : "等待後端連線……"} disabled={!ready || busy || listening} maxLength={2000} />
                  <button type="button" className={`voice-button ${listening ? "is-listening" : ""}`} onClick={toggleListening} disabled={!ready || busy || !voiceSupported} aria-label={listening ? "停止語音辨識" : "使用麥克風輸入"} title={voiceSupported ? "語音轉文字" : "瀏覽器不支援語音辨識"}>{listening ? "■" : "🎙"}</button>
                  <button type="button" className={`voice-button ${speaking ? "is-speaking" : ""}`} onClick={speakLastResponse} disabled={!ttsSupported || !lastNpcSpeech} aria-label={speaking ? "停止播放 NPC 回覆" : "播放 NPC 最近回覆"} title={speaking ? "停止播放" : "播放 NPC 最近回覆"}>{speaking ? "■" : "🔊"}</button>
                  <button type="submit" disabled={!ready || busy || !input.trim()}>送出 ↗</button>
                </form>}
              </>
          </div>
        </section>}

        {journalOpen && <InvestigationJournal inventory={gameState?.player.items ?? []} findings={findings} objective={navigation?.objective ?? "走近地標開始調查。"} onClose={()=>setJournalOpen(false)} near={nearTarget===primaryTarget} onReport={reportChoice ? ()=>requestChoice(reportChoice) : undefined} />}

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
              <dl><div><dt>移動</dt><dd>左鍵點道路，或使用 WASD／方向鍵。角色會朝移動方向轉身。</dd></div><div><dt>旅途地圖</dt><dd>點左上角地圖可查看鳴霖、流塵谷、烈燚原及路線；青色光點標示目前場景。前往各地仍依劇情選項。</dd></div><div><dt>縮放</dt><dd>滑鼠滾輪、右側 ＋／－，或手機雙指縮放。點倍率可恢復全景。</dd></div><div><dt>轉身</dt><dd>右鍵點想面對的方向，或按 Q／R 原地轉身；手機可用 ↶／↷。</dd></div><div><dt>交談</dt><dd>鳴霖議會可與維達利亞、安德烈交談；命脈之泉可與維達利亞交談；流塵谷可與門梅司文托交談；烈燚原可與達索交談；邊境廢墟可與塞特、希拉交談。點擊角色，或靠近後按 E。</dd></div><div><dt>音樂</dt><dd>右上角可播放或關閉背景音樂。</dd></div><div><dt>返回</dt><dd>按 Esc 關閉對話、地圖與說明。</dd></div></dl>
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
