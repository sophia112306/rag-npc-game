"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import styles from "./StoryIntro.module.css";

const SLIDE_DURATION_MS = 5000;

const slides = [
  {
    eyebrow: "序章 · 邊境之地",
    title: "失衡以前",
    body: "森林、烈焰與風沙曾依循古老秩序共存。不同族群守著各自的領地，也守著不願對外人說明的記憶。",
    image: "/game/forest-eye-backdrop.png",
    alt: "薄霧籠罩的古老森林",
  },
  {
    eyebrow: "序章 · 異象",
    title: "沉默的命脈",
    body: "近來，命脈之泉停止回應，符石與地脈也陸續出現異象。沒有人能確定，這些徵兆是否來自同一個原因。",
    image: "/game/scenes/minglin-life-spring-v1.png",
    alt: "森林深處出現異象的命脈之泉",
  },
  {
    eyebrow: "序章 · 旅人",
    title: "你的調查，從鳴霖開始",
    body: "你會先在鳴霖林間醒來，遇見正在調查地脈的安德烈。和他交談後沿著前方道路走，維達利亞才會在議會庭現身。",
    image: "/game/forest-council.png",
    alt: "鳴霖古林中的議會庭",
  },
] as const;

type Props = {
  onComplete: () => void;
};

export default function StoryIntro({ onComplete }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const slide = slides[activeIndex];
  const isLast = activeIndex === slides.length - 1;

  const advance = useCallback(() => {
    if (isLast) {
      onComplete();
      return;
    }
    setActiveIndex((index) => index + 1);
  }, [isLast, onComplete]);

  useEffect(() => {
    const timer = window.setTimeout(advance, SLIDE_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [advance]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (["ArrowRight", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        advance();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        setActiveIndex((index) => Math.max(0, index - 1));
      } else if (event.key === "Escape") {
        event.preventDefault();
        onComplete();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [advance, onComplete]);

  function handleStageClick(event: React.MouseEvent<HTMLElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    advance();
  }

  return (
    <section
      className={styles.intro}
      role="dialog"
      aria-modal="true"
      aria-label="遊戲序章"
      onClick={handleStageClick}
    >
      <div key={slide.image} className={styles.visual} aria-hidden="true">
        <Image src={slide.image} alt="" fill priority sizes="100vw" />
      </div>
      <div className={styles.shade} aria-hidden="true" />
      <div className={styles.grain} aria-hidden="true" />

      <button type="button" className={styles.skip} onClick={onComplete}>
        略過序章
      </button>

      <div className={styles.content} aria-live="polite">
        <p className={styles.eyebrow}>{slide.eyebrow}</p>
        <h1>{slide.title}</h1>
        <p className={styles.body}>{slide.body}</p>

        {isLast && (
          <div className={styles.guide} aria-label="遊玩方式">
            <span><kbd>E</kbd> 交談調查</span>
            <span><kbd>M</kbd> 查看路線</span>
            <span><kbd>J</kbd> 回顧線索</span>
          </div>
        )}

        <div className={styles.controls}>
          <nav className={styles.dots} aria-label="序章頁面">
            {slides.map((item, index) => (
              <button
                key={item.title}
                type="button"
                className={index === activeIndex ? styles.activeDot : ""}
                onClick={() => setActiveIndex(index)}
                aria-label={`前往第 ${index + 1} 幕：${item.title}`}
                aria-current={index === activeIndex ? "step" : undefined}
              />
            ))}
          </nav>
          <button type="button" className={styles.next} onClick={advance}>
            {isLast ? "醒在鳴霖" : "下一幕"}<span aria-hidden="true"> →</span>
          </button>
        </div>
      </div>

      <div className={styles.timeline} aria-hidden="true">
        <span key={activeIndex} />
      </div>
      <p className={styles.hint}>點擊畫面前進 · 約 15 秒</p>
    </section>
  );
}
