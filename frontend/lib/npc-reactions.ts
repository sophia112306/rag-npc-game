export const NPC_REACTION_CUES = [
  "idle",
  "attentive",
  "thoughtful",
  "guarded",
  "firm",
  "surprised",
  "fearful",
] as const;

export type NpcReactionCue = typeof NPC_REACTION_CUES[number];

const REACTION_BY_EMOTION: Record<string, NpcReactionCue> = {
  calm: "idle",
  neutral: "idle",
  attentive: "attentive",
  focused: "attentive",
  helpful: "attentive",
  observant: "attentive",
  purposeful: "attentive",
  welcoming: "attentive",
  careful: "thoughtful",
  measured: "thoughtful",
  mysterious: "thoughtful",
  reserved: "thoughtful",
  solemn: "thoughtful",
  thoughtful: "thoughtful",
  cautious: "guarded",
  guarded: "guarded",
  serious: "guarded",
  wary: "guarded",
  determined: "firm",
  firm: "firm",
  steady: "firm",
  alarmed: "surprised",
  shocked: "surprised",
  startled: "surprised",
  surprised: "surprised",
  afraid: "fearful",
  fearful: "fearful",
  panicked: "fearful",
  terrified: "fearful",
  專注: "attentive",
  沉思: "thoughtful",
  戒備: "guarded",
  堅定: "firm",
  震驚: "surprised",
  驚訝: "surprised",
  害怕: "fearful",
  驚恐: "fearful",
};

export const NPC_REACTION_LABELS: Record<NpcReactionCue, string> = {
  idle: "平靜",
  attentive: "專注",
  thoughtful: "沉思",
  guarded: "戒備",
  firm: "堅定",
  surprised: "震驚",
  fearful: "驚恐",
};

export function resolveNpcReaction(emotion: string | null | undefined): NpcReactionCue {
  const normalized = String(emotion ?? "").trim().toLocaleLowerCase().replace(/[\s_-]+/g, " ");
  return REACTION_BY_EMOTION[normalized] ?? "idle";
}
