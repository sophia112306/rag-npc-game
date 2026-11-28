import { useState } from "react";
import type { PlayerChoice, PlayerItem, StoryFinding } from "../lib/game-api";
import styles from "./InvestigationJournal.module.css";

type Props = {
  findings: StoryFinding[];
  objective: string;
  onClose: () => void;
  onReport?: () => void;
  near: boolean;
  inventory?: PlayerItem[];
  itemUseChoices?: Record<string, PlayerChoice>;
  onUseItem?: (choice: PlayerChoice) => void;
};

export default function InvestigationJournal({findings,objective,onClose,onReport,near,inventory=[],itemUseChoices={},onUseItem}:Props) {
  const [openedItemId, setOpenedItemId] = useState<string | null>(null);
  const openedItem = inventory.find(item => item.item_id === openedItemId);
  return <div className={styles.modal} onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}>
    <section className={styles.journal} role="dialog" aria-modal="true" aria-label="調查紀錄"
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
      <section className={styles.inventory} aria-label="隨身道具">
        <h3>隨身道具 · {inventory.length} 件</h3>
        {inventory.length ? <ul>{inventory.map(item=><li key={item.item_id}>
          {item.image_url && <img src={item.image_url} alt="" width={72} height={72} />}
          <div><strong>{item.name}</strong><p>{item.description}</p>
            {["vidalia_observation_page", "remembrance_slab"].includes(item.item_id) && <button type="button" className={styles.useButton} onClick={()=>setOpenedItemId(openedItemId===item.item_id?null:item.item_id)} aria-expanded={openedItemId===item.item_id}>檢視{item.item_id === "remembrance_slab" ? "石板" : "殘頁"}</button>}
            {itemUseChoices[item.item_id] && onUseItem && <button type="button" className={styles.useButton} onClick={()=>onUseItem(itemUseChoices[item.item_id])}>{itemUseChoices[item.item_id].label}</button>}
          </div>
        </li>)}</ul>
          : <p>目前沒有道具。調查線索請查看下方紀錄。</p>}
        {openedItem && <div className={styles.itemDetail} aria-label={`${openedItem.name}內容`}>
          {openedItem.image_url && <img src={openedItem.image_url} alt={openedItem.name} />}
          <div><strong>{openedItem.name}</strong><p>{openedItem.description}</p><small>{openedItem.item_id === "remembrance_slab" ? "石板尚未記下經查證的姓名。" : "你可在與維達利亞交談時，提起這張殘頁。"}</small></div>
        </div>}
      </section>
      {findings.length ? <div className={styles.findingsGrid}>{findings.map(finding=><article key={finding.clue_id} data-signal={finding.visual_signal}>
        {finding.image_url && <img className={styles.findingImage} src={finding.image_url} alt="" />}
        <small>{finding.scene_name} · {finding.kind==="conversation"?"交談記錄":"現場調查"}</small>
        <h3>{finding.title}</h3>
        <p>{finding.summary}</p>
      </article>)}</div> : <p className={styles.emptyFindings}>手記還是空白的。向維達利亞詢問調查方向，再到泉眼或符石林走近地標按 E。</p>}
      {onReport && <button className={styles.reportButton} onClick={onReport}>{near?"向維達利亞回報這些紀錄":"走向維達利亞，準備回報"} →</button>}
      <p className={styles.hint}>交談記錄與現場調查分開標示。NPC 只會承接親自參與或你實際回報的內容。</p>
    </section>
  </div>;
}
