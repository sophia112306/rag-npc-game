"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";

const mapImage = "/game/world-route-map-v1.png";
const mapWidth = 1672;
const mapHeight = 941;

const places: Record<string, { x: number; y: number }> = {
  minglin: { x: 644, y: 433 },
  minglin_life_spring: { x: 276, y: 188 },
  minglin_rune_grove: { x: 287, y: 663 },
  liuchen_valley: { x: 1360, y: 307 },
  lieyi_plains: { x: 1418, y: 584 },
};

type Props = {
  sceneId: string;
  sceneName: string;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
};

function CurrentPlace({ sceneId }: { sceneId: string }) {
  const place = places[sceneId];
  if (!place) return null;
  return (
    <span
      className="world-map-current"
      style={{ left: `${place.x / mapWidth * 100}%`, top: `${place.y / mapHeight * 100}%` }}
      aria-hidden="true"
    ><span /></span>
  );
}

export default function WorldMap({ sceneId, sceneName, expanded, onExpandedChange }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLDivElement>(null);
  const openButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const wasExpanded = useRef(false);

  useEffect(() => {
    if (expanded) {
      closeButtonRef.current?.focus();
      wasExpanded.current = true;
    } else if (wasExpanded.current) {
      openButtonRef.current?.focus();
      wasExpanded.current = false;
    }
  }, [expanded]);

  useEffect(() => {
    if (!expanded || !viewportRef.current || !imageRef.current) return;
    const place = places[sceneId];
    if (!place) return;
    const viewport = viewportRef.current;
    const image = imageRef.current;
    viewport.scrollLeft = place.x / mapWidth * image.clientWidth - viewport.clientWidth / 2;
    viewport.scrollTop = place.y / mapHeight * image.clientHeight - viewport.clientHeight / 2;
  }, [expanded, sceneId]);

  return (
    <>
      <aside className="world-map-preview" aria-label="旅途地圖">
        <button ref={openButtonRef} type="button" className="world-map-open" onClick={() => onExpandedChange(true)} aria-haspopup="dialog" aria-label={`開啟旅途地圖，目前位於${sceneName}`}>
          <span className="world-map-preview-heading">◇　旅途地圖 <span aria-hidden="true">⤢</span></span>
          <span className="world-map-preview-image">
            <Image src={mapImage} alt="" width={mapWidth} height={mapHeight} sizes="(max-width: 640px) 210px, 260px" />
            <CurrentPlace sceneId={sceneId} />
          </span>
          <span className="world-map-preview-footer">目前：{sceneName}<span>查看全圖 ›</span></span>
        </button>
      </aside>

      {expanded && (
        <div className="game-overlay world-map-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onExpandedChange(false); }}>
          <section className="world-map-dialog" role="dialog" aria-modal="true" aria-label="旅途地圖">
            <header className="world-map-dialog-header">
              <div><span>◇　旅途地圖</span><small>目前：{sceneName}</small></div>
              <button ref={closeButtonRef} type="button" onClick={() => onExpandedChange(false)} aria-label="關閉旅途地圖">✕</button>
            </header>
            <div className="world-map-scroll" ref={viewportRef} tabIndex={0} aria-label="地圖，可使用方向鍵或滑動查看">
              <div className="world-map-full-image" ref={imageRef}>
                <Image src={mapImage} alt="鳴霖、平衡議會、命脈之泉、符石林、流塵谷與烈燚原的俯視旅途地圖" width={mapWidth} height={mapHeight} sizes="(max-width: 700px) 900px, 95vw" />
                <CurrentPlace sceneId={sceneId} />
              </div>
            </div>
            <p className="world-map-caption">青色光點是目前位置；金色圓環是旅程起點。地圖展示路線，前往各地請依故事選項探索。<span>窄螢幕可左右滑動地圖</span></p>
          </section>
        </div>
      )}
    </>
  );
}
