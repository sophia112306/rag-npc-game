export type CharacterVoiceId =
  | "vidalia"
  | "andre"
  | "menmesvento"
  | "dasso"
  | "seth"
  | "syra"
  | "alan"
  | "veta"
  | "narrator";

export type CharacterVoiceProfile = {
  lang: string;
  rate: number;
  pitch: number;
  volume: number;
  fallbackSlot: number;
  preferredVoiceNames: readonly string[];
};

export type BrowserVoice = {
  name: string;
  lang: string;
  default?: boolean;
};

export const CHARACTER_VOICE_PROFILES: Record<CharacterVoiceId, CharacterVoiceProfile> = {
  vidalia: {
    lang: "zh-TW", rate: 0.9, pitch: 1.08, volume: 0.95, fallbackSlot: 0,
    preferredVoiceNames: ["HsiaoYu", "HsiaoChen", "Mei-Jia", "Meijia"],
  },
  andre: {
    lang: "zh-TW", rate: 0.96, pitch: 0.84, volume: 1, fallbackSlot: 1,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Sin-ji", "Sinji"],
  },
  menmesvento: {
    lang: "zh-TW", rate: 0.76, pitch: 0.58, volume: 0.92, fallbackSlot: 1,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Ting-Ting", "Tingting"],
  },
  dasso: {
    lang: "zh-TW", rate: 0.82, pitch: 0.64, volume: 1, fallbackSlot: 2,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Sin-ji", "Ting-Ting"],
  },
  seth: {
    lang: "zh-TW", rate: 0.88, pitch: 0.74, volume: 0.82, fallbackSlot: 3,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Sin-ji", "Ting-Ting"],
  },
  syra: {
    lang: "zh-TW", rate: 1.02, pitch: 1.14, volume: 0.94, fallbackSlot: 2,
    preferredVoiceNames: ["HsiaoChen", "HsiaoYu", "Mei-Jia", "Meijia"],
  },
  alan: {
    lang: "zh-TW", rate: 0.9, pitch: 0.72, volume: 0.48, fallbackSlot: 3,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Google 國語", "Ting-Ting"],
  },
  veta: {
    lang: "zh-TW", rate: 0.68, pitch: 0.48, volume: 1, fallbackSlot: 1,
    preferredVoiceNames: ["YunJhe", "Yunjhe", "Ting-Ting", "Sin-ji"],
  },
  narrator: {
    lang: "zh-TW", rate: 0.94, pitch: 1, volume: 0.9, fallbackSlot: 0,
    preferredVoiceNames: ["HsiaoChen", "Mei-Jia", "Meijia", "Ting-Ting"],
  },
};

const SPEAKER_NAME_TO_ID: Record<string, CharacterVoiceId> = {
  維達利亞: "vidalia",
  安德烈: "andre",
  門梅司文托: "menmesvento",
  達索: "dasso",
  塞特: "seth",
  希拉: "syra",
  艾倫: "alan",
  "艾倫・沃克": "alan",
  維塔: "veta",
  旁白: "narrator",
};

export function isCharacterVoiceId(value: string | null | undefined): value is CharacterVoiceId {
  return Boolean(value && value in CHARACTER_VOICE_PROFILES);
}

export function resolveCharacterVoiceId(
  speakerId: string | null | undefined,
  speakerName: string | null | undefined,
  fallback: CharacterVoiceId = "narrator",
): CharacterVoiceId {
  if (isCharacterVoiceId(speakerId)) return speakerId;
  return speakerName && SPEAKER_NAME_TO_ID[speakerName] ? SPEAKER_NAME_TO_ID[speakerName] : fallback;
}

export function selectCharacterVoice<T extends BrowserVoice>(
  voices: readonly T[],
  characterId: CharacterVoiceId,
): T | undefined {
  const profile = CHARACTER_VOICE_PROFILES[characterId];
  const preferred = profile.preferredVoiceNames
    .map(name => name.toLocaleLowerCase())
    .map(name => voices.find(voice => voice.name.toLocaleLowerCase().includes(name)))
    .find((voice): voice is T => Boolean(voice));
  if (preferred) return preferred;

  const normalizedLanguage = profile.lang.toLocaleLowerCase();
  const exactLanguage = voices.filter(voice => voice.lang.toLocaleLowerCase() === normalizedLanguage);
  const chineseVoices = voices.filter(voice => {
    const lang = voice.lang.toLocaleLowerCase();
    return lang.startsWith("zh") || lang.startsWith("cmn") || lang.startsWith("yue");
  });
  const candidates = exactLanguage.length > 0 ? exactLanguage : chineseVoices;
  if (candidates.length === 0) return voices.find(voice => voice.default) ?? voices[0];
  return candidates[profile.fallbackSlot % candidates.length];
}
