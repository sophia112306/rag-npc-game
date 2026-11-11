/** Music for each playable scene, plus the standalone Veta preview. */
export const SCENE_MUSIC = {
  minglin: { src: "/audio/iremos-forest-theme.ogg", title: "鳴霖・平衡議會" },
  minglin_life_spring: { src: "/audio/life-spring.ogg", title: "鳴霖・命脈之泉" },
  minglin_rune_grove: { src: "/audio/rune-grove.ogg", title: "鳴霖・符石林" },
  liuchen_valley: { src: "/audio/liuchen-valley.ogg", title: "流塵谷" },
  lieyi_plains: { src: "/audio/lieyi-plains.ogg", title: "烈燚原" },
  veta_preview: { src: "/audio/veta-dream.ogg", title: "維塔・沉眠之所" },
} as const;

export function getSceneMusic(sceneId: string) {
  return Object.hasOwn(SCENE_MUSIC, sceneId)
    ? SCENE_MUSIC[sceneId as keyof typeof SCENE_MUSIC]
    : SCENE_MUSIC.minglin;
}
