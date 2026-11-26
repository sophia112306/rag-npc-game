import type { AlanTone } from "./game-api";

let context: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined" || !("AudioContext" in window)) return null;
  context ??= new AudioContext();
  return context;
}

/** Play a tiny communication cue without adding a binary audio asset. */
export function playAlanCue(tone: AlanTone): void {
  const audio = getContext();
  if (!audio || tone === "silent") return;

  try {
    if (audio.state === "suspended") void audio.resume();
    const now = audio.currentTime;
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = tone === "interference" ? "sawtooth" : "sine";
    const frequency = tone === "override" ? 220 : tone === "urgent" ? 660 : tone === "interference" ? 180 : 520;
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(frequency * (tone === "interference" ? 0.72 : 1.12), now + 0.14);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(tone === "override" ? 0.06 : 0.035, now + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + (tone === "override" ? 0.32 : 0.16));
    oscillator.connect(gain).connect(audio.destination);
    oscillator.start(now);
    oscillator.stop(now + (tone === "override" ? 0.34 : 0.18));
  } catch {
    // Audio is optional: browser autoplay policies must never block a turn.
  }
}
