import assert from "node:assert/strict";
import test from "node:test";

import {
  CHARACTER_VOICE_PROFILES,
  resolveCharacterVoiceId,
  selectCharacterVoice,
} from "../../frontend/lib/character-voice.ts";

test("every story character has distinct prosody even when only one browser voice exists", () => {
  const ids = ["vidalia", "andre", "menmesvento", "dasso", "seth", "syra", "alan", "veta"] as const;
  const signatures = ids.map(id => {
    const profile = CHARACTER_VOICE_PROFILES[id];
    return `${profile.rate}:${profile.pitch}:${profile.volume}`;
  });
  assert.equal(new Set(signatures).size, ids.length);
});

test("character voice selection prefers the matching named Taiwanese voice", () => {
  const voices = [
    { name: "Microsoft YunJhe Online", lang: "zh-TW" },
    { name: "Microsoft HsiaoYu Online", lang: "zh-TW" },
  ];

  assert.equal(selectCharacterVoice(voices, "vidalia")?.name, "Microsoft HsiaoYu Online");
  assert.equal(selectCharacterVoice(voices, "andre")?.name, "Microsoft YunJhe Online");
});

test("speaker identity covers non-map characters and narrator", () => {
  assert.equal(resolveCharacterVoiceId("veta", "維塔", "vidalia"), "veta");
  assert.equal(resolveCharacterVoiceId(null, "艾倫・沃克", "vidalia"), "alan");
  assert.equal(resolveCharacterVoiceId(null, "旁白", "vidalia"), "narrator");
});
