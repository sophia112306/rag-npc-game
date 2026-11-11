"use client";

import { useEffect, useRef, useState } from "react";

export function useSceneMusic(src: string, volume: number) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const wantedRef = useRef(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume;
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !wantedRef.current) return;
    let current = true;
    setError("");
    audio.load();
    audio.volume = volume;
    void audio.play().catch(() => {
      if (!current) return;
      wantedRef.current = false;
      setPlaying(false);
      setError("音樂無法播放，請點擊重試。");
    });
    return () => { current = false; };
    // A scene change should change the track; volume changes are handled above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (wantedRef.current) {
      wantedRef.current = false;
      audio.pause();
      setPlaying(false);
      setError("");
      return;
    }
    wantedRef.current = true;
    setError("");
    try {
      if (audio.error) audio.load();
      audio.volume = volume;
      await audio.play();
    } catch {
      if (!wantedRef.current) return;
      wantedRef.current = false;
      setPlaying(false);
      setError("音樂無法播放，請點擊重試。");
    }
  }

  return {
    audioRef,
    playing,
    error,
    toggle,
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onError: () => {
      wantedRef.current = false;
      setPlaying(false);
      setError("音樂載入失敗，請點擊重試。");
    },
  };
}
