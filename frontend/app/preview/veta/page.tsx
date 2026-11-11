"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { getSceneMusic } from "../../../lib/scene-music";
import { useSceneMusic } from "../../../lib/use-scene-music";
import styles from "./VetaPreview.module.css";

type View = "wide" | "head" | "heart";

const views: { id: View; label: string; observation: string }[] = [
  { id: "wide", label: "全景", observation: "洞穴深處，蜷縮的巨龍仍在沉睡。" },
  { id: "head", label: "龍首", observation: "苔痕攀上古老的鱗片；牠的眼仍然閉著。" },
  { id: "heart", label: "心光", observation: "胸前的琥珀色微光，隨著呼吸緩緩明滅。" },
];

export default function VetaPreview() {
  const [view, setView] = useState<View>("wide");
  const track = getSceneMusic("veta_preview");
  const music = useSceneMusic(track.src, 0.2);
  const observation = views.find((item) => item.id === view)?.observation ?? views[0].observation;

  return (
    <main className={styles.page} aria-label="維塔角色畫面">
      <audio ref={music.audioRef} src={track.src} loop preload="none" onPlay={music.onPlay} onPause={music.onPause} onError={music.onError} />
      <div className={`${styles.artwork} ${styles[view]}`}>
        <Image
          src="/game/veta-sleeping-dragon.png"
          alt="沉睡在古老洞穴中的維塔，龍身覆著岩層與苔蘚，胸前透出溫暖微光"
          fill
          sizes="100vw"
          className={styles.sceneImage}
        />
        <span className={styles.heartGlow} aria-hidden="true" />
      </div>
      <div className={styles.vignette} aria-hidden="true" />

      <header className={styles.location}>
        <span className={styles.rune} aria-hidden="true">✧</span>
        <div>
          <span className={styles.eyebrow}>沉眠之所</span>
          <h1>維塔</h1>
        </div>
      </header>

      <Link className={styles.back} href="/" aria-label="返回遊戲">返回遊戲 <span aria-hidden="true">↗</span></Link>
      <button
        type="button"
        className={styles.musicButton}
        onClick={() => void music.toggle()}
        aria-pressed={music.playing}
        aria-label={music.error ? `${music.error}點擊重試` : music.playing ? `關閉${track.title}背景音樂` : `播放${track.title}背景音樂`}
        title={music.error || track.title}
      >♫ {music.error ? "重試音樂" : music.playing ? "音樂開" : "播放音樂"}</button>

      <section className={styles.caption} aria-label="觀察維塔">
        <div className={styles.portrait} aria-hidden="true">
          <Image src="/game/veta-sleeping-dragon.png" alt="" fill sizes="(max-width: 640px) 84px, 154px" />
        </div>
        <div className={styles.captionBody}>
          <div className={styles.speaker}><strong>維塔</strong><span>沉睡中</span></div>
          <p aria-live="polite">{observation}</p>
          <div className={styles.views} role="group" aria-label="觀察視角">
            {views.map((item) => (
              <button key={item.id} type="button" aria-pressed={view === item.id} onClick={() => setView(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
