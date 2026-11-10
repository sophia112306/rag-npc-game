export type PlayerScene = {
  scene_id: string;
  region_name: string;
  display_name: string;
  subtitle: string;
  description: string;
  background_url: string;
  horizon_url: string;
  canon_status: "confirmed" | "provisional";
};

export type GameStateSummary = {
  turn_count: number;
  state_version: number;
  updated_at: string;
  current_scene_id: string;
  current_scene: PlayerScene;
  story_progress: {
    arc_id: string;
    node_id: string;
    chapter_title: string;
    mode: "demo_fallback";
    public_clue_ids: string[];
  };
};

export type GameTurnResponse = {
  turn_number: number;
  state: GameStateSummary;
  story: { dialogue: { speaker_name: string; text: string }[] };
};

export type PlayerChoice = {
  choice_id: string;
  label: string;
  message: string;
  target_npc_id: string | null;
  action_mode: "dialogue" | "interaction" | "movement";
  destination_scene_id: string | null;
};

export type Capabilities = {
  generation_mode: "rule_based" | "external_model";
  dynamic_dialogue: boolean;
};

export type PlayerQuest = {
  quest_id: string;
  title: string;
  status: "offered" | "active" | "completed" | "failed" | "cancelled";
};

export class ApiRequestError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
  }
}

export const GAME_SESSION_STORAGE_KEY = "vidalia-game-session";
const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, init);
  } catch {
    throw new Error("無法連線到遊戲服務，請確認後端已啟動。");
  }
  if (!response.ok) {
    let detail: { code?: string; message?: string } | undefined;
    try {
      const payload = (await response.json()) as {
        detail?: { code?: string; message?: string };
      };
      detail = payload.detail;
    } catch {
      // Non-JSON failures use the generic status message below.
    }
    throw new ApiRequestError(
      detail?.message ?? `遊戲服務回應 ${response.status}，請稍後重試。`,
      response.status,
      detail?.code,
    );
  }
  return (await response.json()) as T;
}
