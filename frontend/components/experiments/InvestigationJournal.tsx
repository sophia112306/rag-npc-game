import type { StoryFinding } from "../../lib/game-api";
import styles from "./TrialExperience.module.css";

type Props = {
  findings: StoryFinding[];
  objective: string;
  onClose: () => void;
  onReport?: () => void;
  near: boolean;
};

export default function InvestigationJournal({findings,objective,onClose,onReport,near}:Props) {
  return <div className={styles.modal} onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}>
    <section className={`${styles.journal} ${styles.investigationJournal}`} role="dialog" aria-modal="true" aria-label="調查紀錄"
      onKeyDown={event=>{
        if(event.key!=="Tab")return;
        const buttons=event.currentTarget.querySelectorAll<HTMLButtonElement>("button");
        const first=buttons[0],last=buttons[buttons.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
        if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
      }}>
      <button className={styles.close} onClick={onClose} aria-label="關閉調查紀錄" autoFocus>✕</button>
      <small>旅人的調查手記 · {findings.length} 項紀錄</small>
      <h2>你走過的路，留下不同的線索</h2>
      <p>{objective}</p>
      {findings.length ? <div className={styles.findingsGrid}>{findings.map(finding=><article key={finding.clue_id} data-signal={finding.visual_signal}>
        <small>{finding.scene_name} · {finding.kind==="conversation"?"交談記錄":"現場調查"}</small>
        <h3>{finding.title}</h3>
        <p>{finding.summary}</p>
      </article>)}</div> : <p className={styles.emptyFindings}>手記還是空白的。向維達利亞詢問調查方向，再到泉眼或符石林走近地標按 E。</p>}
      {onReport && <button className={styles.reportButton} onClick={onReport}>{near?"向維達利亞回報這些紀錄":"走向維達利亞，準備回報"} →</button>}
      <p className={styles.hint}>交談記錄與現場調查分開標示。NPC 只會承接親自參與或你實際回報的內容。</p>
    </section>
  </div>;
}
