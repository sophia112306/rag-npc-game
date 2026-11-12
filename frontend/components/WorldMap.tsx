"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import type { PlayerChoice, PlayerMapScene, PlayerNavigation } from "../lib/game-api";

const mapImage = "/game/world-route-map-v1.png";
const mapWidth = 1672;
const mapHeight = 941;

type Props = {
  sceneId: string;
  sceneName: string;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  navigation?: PlayerNavigation | null;
  onTravel?: (choice: PlayerChoice) => void;
  near?: boolean;
  busy?: boolean;
  exploration?: boolean;
};

function placeStyle(place: PlayerMapScene) {
  return {left: `${place.map_x / mapWidth * 100}%`, top: `${place.map_y / mapHeight * 100}%`};
}
function placeStatus(place: PlayerMapScene) {
  return place.current ? "目前位置" : place.travel_choice ? "可前往" : place.unlocked ? "已知地點" : "尚未解鎖";
}

function CurrentPlace({ place }: { place?: PlayerMapScene }) {
  return place ? <span className="world-map-current" style={placeStyle(place)} aria-hidden><span /></span> : null;
}

function Routes({ navigation }: { navigation?: PlayerNavigation | null }) {
  const current = navigation?.scenes.find(scene => scene.current);
  if (!current) return null;
  return (
    <svg className="world-map-routes" viewBox={`0 0 ${mapWidth} ${mapHeight}`} aria-hidden>
      {navigation?.scenes.filter(scene => scene.travel_choice).map(scene => (
        <g key={scene.scene_id}>
          <path d={`M${current.map_x} ${current.map_y} Q${(current.map_x+scene.map_x)/2+65} ${(current.map_y+scene.map_y)/2-50} ${scene.map_x} ${scene.map_y}`} />
          <circle cx={scene.map_x} cy={scene.map_y} r="17" />
        </g>
      ))}
    </svg>
  );
}

/** Both clients use the same map art and server-issued locations/actions. */
export default function WorldMap({ sceneId, sceneName, expanded, onExpandedChange, navigation, onTravel, near=false, busy=false, exploration=false }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLDivElement>(null);
  const openButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const wasExpanded = useRef(false);
  const [selectedId, setSelectedId] = useState(sceneId);
  const current = navigation?.scenes.find(scene => scene.scene_id === sceneId);
  const selected = navigation?.scenes.find(scene => scene.scene_id === selectedId) ?? current;

  useEffect(() => {
    if (expanded) {
      closeButtonRef.current?.focus();
      setSelectedId(sceneId);
      wasExpanded.current = true;
    } else if (wasExpanded.current) {
      openButtonRef.current?.focus();
      wasExpanded.current = false;
    }
  }, [expanded, sceneId]);

  useEffect(() => {
    if (!expanded || !viewportRef.current || !imageRef.current || !current) return;
    const viewport = viewportRef.current, image = imageRef.current;
    viewport.scrollLeft = current.map_x / mapWidth * image.clientWidth - viewport.clientWidth / 2;
    viewport.scrollTop = current.map_y / mapHeight * image.clientHeight - viewport.clientHeight / 2;
  }, [expanded, current?.scene_id]);

  return (
    <>
      <aside className={`world-map-preview ${exploration ? "exploration-map" : ""}`} aria-label="旅途小地圖">
        <button ref={openButtonRef} type="button" className="world-map-open" onClick={() => onExpandedChange(true)} aria-haspopup="dialog" aria-label={`開啟旅途地圖，目前位於${sceneName}`}>
          <span className="world-map-preview-heading">◇　旅途地圖 <span aria-hidden>⤢</span></span>
          <span className="world-map-preview-image">
            <Image src={mapImage} alt="" width={mapWidth} height={mapHeight} sizes="(max-width: 760px) 150px, 260px" />
            <Routes navigation={navigation} />
            <CurrentPlace place={current} />
          </span>
          <span className="world-map-preview-footer">{sceneName}<span>{exploration ? "M 展開" : "查看全圖 ›"}</span></span>
        </button>
      </aside>

      {expanded && (
        <div className="game-overlay world-map-overlay" role="presentation" onMouseDown={event => { if(event.target===event.currentTarget) onExpandedChange(false); }}>
          <section ref={dialogRef} className={`world-map-dialog ${navigation ? "has-navigation" : ""}`} role="dialog" aria-modal="true" aria-label="旅途地圖"
            onKeyDown={event => {
              if (event.key === "Escape") onExpandedChange(false);
              if (event.key !== "Tab") return;
              const controls = dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled),[tabindex='0']");
              const first = controls?.[0], last = controls?.[controls.length - 1];
              if (event.shiftKey && document.activeElement === first) { event.preventDefault();last?.focus(); }
              if (!event.shiftKey && document.activeElement === last) { event.preventDefault();first?.focus(); }
            }}>
            <header className="world-map-dialog-header">
              <div><span>◇　旅途地圖</span><small>目前：{sceneName}</small></div>
              <button ref={closeButtonRef} type="button" onClick={() => onExpandedChange(false)} aria-label="關閉旅途地圖">✕</button>
            </header>
            <div className="world-map-layout">
              <div className="world-map-scroll" ref={viewportRef} tabIndex={0} aria-label="地圖，可使用方向鍵或滑動查看">
                <div className="world-map-full-image" ref={imageRef}>
                  <Image src={mapImage} alt="平衡議會、命脈之泉、符石林、流塵谷與烈燚原的俯視旅途地圖" width={mapWidth} height={mapHeight} sizes="(max-width: 700px) 700px, 75vw" />
                  <Routes navigation={navigation} />
                  {navigation?.scenes.map(place => (
                    <button key={place.scene_id} className={`world-map-pin ${place.travel_choice ? "is-reachable" : ""} ${!place.unlocked ? "is-locked" : ""}`} style={placeStyle(place)} onClick={() => setSelectedId(place.scene_id)} aria-label={`${place.display_name}，${placeStatus(place)}`} aria-pressed={selected?.scene_id===place.scene_id}>
                      {place.current ? "✦" : place.unlocked ? "◇" : "⌑"}
                    </button>
                  ))}
                  <CurrentPlace place={current} />
                </div>
              </div>
              {selected && (
                <aside className="world-map-details" aria-label="選取地點">
                  <img src={selected.background_url} alt={`${selected.display_name}場景預覽`} />
                  <div>
                    <small>{placeStatus(selected)}</small>
                    <h3>{selected.display_name}</h3>
                    <p>{selected.hint}</p>
                    {selected.travel_choice && onTravel && (
                      <button disabled={busy} onClick={() => onTravel(selected.travel_choice!)}>
                        {near ? `前往${selected.display_name} →` : "追蹤路線，走向出發點 →"}
                      </button>
                    )}
                    {selected.travel_choice && onTravel && !near && <p className="world-map-detail-hint">先走近人物／地標，抵達後確認出發。</p>}
                    <p className="world-map-detail-hint">旅行後切換對應場景；調查結果保留在手記中。</p>
                  </div>
                </aside>
              )}
            </div>
            {navigation && <nav className="world-map-places" aria-label="選擇地點">{navigation.scenes.map(place => <button key={place.scene_id} aria-pressed={selected?.scene_id===place.scene_id} onClick={() => setSelectedId(place.scene_id)}>{place.display_name}<small>{placeStatus(place)}</small></button>)}</nav>}
            <p className="world-map-caption">{navigation?.objective ?? "青色光點是目前位置，依故事選項探索各地。"}<span>青色：目前位置　金色：可走路線　灰色：未解鎖</span></p>
          </section>
        </div>
      )}
    </>
  );
}
