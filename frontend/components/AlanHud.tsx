import { useEffect, useState, type FormEvent } from "react";
import { requestJson, type AlanHud as AlanHudState, type AlanModelResponse, type AlanTone } from "../lib/game-api";
import styles from "./AlanHud.module.css";

type AlanHudProps = {
  hud: AlanHudState | null | undefined;
  onReplay?: () => void;
  onSpeakReply?: (text: string) => void;
  sessionId?: string;
  stateVersion?: number;
};

const toneClassNames: Record<AlanTone, string> = {
  calm: styles.calm,
  urgent: styles.urgent,
  interference: styles.interference,
  override: styles.override,
  silent: styles.silent,
};

export default function AlanHud({ hud, onReplay, onSpeakReply, sessionId, stateVersion }: AlanHudProps) {
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { setReply(""); setError(""); }, [sessionId, stateVersion]);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!sessionId || !stateVersion || !text || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await requestJson<AlanModelResponse>(`/api/game/${encodeURIComponent(sessionId)}/alan/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, expected_state_version: stateVersion }),
      });
      setReply(result.reply);
      setQuestion("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "通訊暫時中斷。");
    } finally {
      setBusy(false);
    }
  }

  if (!hud?.visible) return null;

  return (
    <aside className={`${styles.hud} ${toneClassNames[hud.tone]} ${hud.persistent ? styles.persistent : ""}`} aria-label="玩家專屬視網膜 HUD" aria-live="polite">
      <div className={styles.header}>
        <span className={styles.signal} aria-hidden="true"><i /> <i /> <i /></span>
        <span>{hud.label}</span>
        <span className={styles.headerStatus}>{hud.tone === "override" ? "OVERRIDE" : hud.tone === "interference" ? "INTERFERENCE" : "ONLINE"}</span>
      </div>
      <div className={styles.meter} aria-label={`因果解析度 ${hud.display_value}%`}>
        <span style={{ width: `${hud.display_value}%` }} />
      </div>
      <div className={styles.valueRow}><span>因果解析度</span><strong>{hud.display_value}%</strong></div>
      <p>{hud.message}</p>
      {reply && <div className={styles.reply}><span>通訊回覆</span><p>{reply}</p>{onSpeakReply && <button type="button" onClick={() => onSpeakReply(reply)}>播放回覆</button>}</div>}
      {error && <p className={styles.error} role="status">{error}</p>}
      {sessionId && <form className={styles.ask} onSubmit={ask}>
        <label htmlFor="alan-question">詢問連線</label>
        <div><input id="alan-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={500} placeholder="現在應該做什麼？" disabled={busy} /><button type="submit" disabled={busy || !question.trim()}>{busy ? "連線中…" : "傳送"}</button></div>
      </form>}
      {hud.countdown_turns !== null && <div className={styles.countdown}>倒數 <strong>{hud.countdown_turns}</strong> 回合</div>}
      {onReplay && <button type="button" className={styles.replay} onClick={onReplay}>⌁ 播放通訊</button>}
    </aside>
  );
}
