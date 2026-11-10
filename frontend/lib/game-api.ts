export type SceneVisualProfile = {
  profile_id: string;
  clear_color: string;
  fog_color: string;
  fog_density: number;
  ambient_color: string;
  ground_color: string;
  use_ground_texture: boolean;
  sky_color: string;
  sky_ground_color: string;
  sky_intensity: number;
  key_light_color: string;
  key_light_intensity: number;
  accent_light_color: string;
  accent_light_intensity: number;
  backdrop_emissive_color: string;
  surface_color: string;
  surface_light_color: string;
  surface_dark_color: string;
  organic_color: string;
  rune_color: string;
  rune_emissive_color: string;
  liquid_color: string;
  liquid_emissive_color: string;
  prop_groups: Array<"forest" | "path" | "council" | "pillars" | "spring">;
  show_ground: boolean;
  show_vidalia: boolean;
  show_relic: boolean;
};

export const DEFAULT_SCENE_VISUAL_PROFILE: SceneVisualProfile = {
  profile_id: "minglin_council",
  clear_color: "#142e38",
  fog_color: "#29525c",
  fog_density: 0.011,
  ambient_color: "#2e3b45",
  ground_color: "#b5c2b6",
  use_ground_texture: true,
  sky_color: "#d1e5e3",
  sky_ground_color: "#2e4038",
  sky_intensity: 0.72,
  key_light_color: "#c7e3e0",
  key_light_intensity: 0.85,
  accent_light_color: "#ffe0b0",
  accent_light_intensity: 0.26,
  backdrop_emissive_color: "#666b66",
  surface_color: "#92958a",
  surface_light_color: "#aaafa0",
  surface_dark_color: "#657970",
  organic_color: "#537e65",
  rune_color: "#668f88",
  rune_emissive_color: "#183d39",
  liquid_color: "#2d9297",
  liquid_emissive_color: "#1e626c",
  prop_groups: ["forest", "path", "council", "pillars", "spring"],
  show_ground: true,
  show_vidalia: true,
  show_relic: true,
};

export type PlayerScene = {
  scene_id: string;
  region_name: string;
  display_name: string;
  subtitle: string;
  description: string;
  background_url: string;
  horizon_url: string;
  visual_profile: SceneVisualProfile;
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

export type SceneImageJob = {
  job_id: string;
  session_id: string;
  scene_id: string;
  story_node_id: string;
  state_version: number;
  prompt_fingerprint: string;
  provider: string;
  status: "queued" | "processing" | "succeeded" | "fallback";
  image_url: string | null;
  attempt_count: number;
  error_code: string | null;
};

export function enqueueSceneImage(sessionId: string, expectedStateVersion: number) {
  return requestJson<SceneImageJob>(`/api/game/${sessionId}/scene-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_state_version: expectedStateVersion }),
  });
}

export function getSceneImageJob(sessionId: string, jobId: string) {
  return requestJson<SceneImageJob>(`/api/game/${sessionId}/scene-image/${jobId}`);
}

export async function resolveSceneImage(
  sessionId: string,
  expectedStateVersion: number,
  isCurrent: () => boolean,
) {
  let job = await enqueueSceneImage(sessionId, expectedStateVersion);
  for (let attempt = 0; attempt < 10 && isCurrent(); attempt += 1) {
    if (job.status === "succeeded" || job.status === "fallback") return job;
    await new Promise((resolve) => window.setTimeout(resolve, 750));
    if (!isCurrent()) return null;
    job = await getSceneImageJob(sessionId, job.job_id);
  }
  return isCurrent() ? job : null;
}

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
