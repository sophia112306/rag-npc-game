# Hunyuan3D 校內 GPU 部署與交接

GPU gateway 階段：`██████████ 100%`（校機 build、私有 API、持久化 cache 與真實 GLB 均已驗收）

完整 A4 原型串接：`██████████ 100%`（持久化 job、私有 API、投影貼圖、Babylon loader 與 Chrome 真實載入完成；正式角色與精修資產仍待提供）

2026-11-11 更新：遊戲後端設定 `HUNYUAN3D_URL=http://127.0.0.1:8081`，經 `/api/game/{session_id}/scene-assets` 提交持久化工作，再由 Session 範圍的 `/model` 下載 GLB。三種環境物件的即時生成與 Babylon `3/3` 載入已驗收。來源與完整提示見 [3D_ASSET_PROMPTS.md](3D_ASSET_PROMPTS.md)，遊戲操作見 [DEMO_HANDOFF.md](DEMO_HANDOFF.md)。

## 這一階段的範圍

本階段提供可重現的 Hunyuan3D shape 服務，用單張 PNG／JPEG／WebP 產生獨立 mesh，後處理加入參考圖投影材質與平滑法線。目前已用樹木、符石與祭壇接入 Babylon 組裝場景；整張風景圖片不能直接變成完整可玩的 3D 關卡。

已在校機確認的環境：

- NVIDIA GeForce RTX 5060 Ti，16 GB VRAM，compute capability 12.0。
- rootless Docker 29.8.1、Docker Compose v5.5.1。
- NVIDIA CDI 裝置 `nvidia.com/gpu=all` 可在 rootless container 內看到 GPU。
- 主機不執行 `apt`、`pip` 或 `npm install`；所有依賴只在 Docker build 內安裝。

## 為什麼先做 shape-only

Hunyuan3D 官方文件標示 shape generation 約需 6 GB VRAM，shape＋texture 約需 16 GB。校機的 VRAM 剛好是 16 GB，若同時載入材質模型，還要加上輸入影像、mesh、CUDA workspace 與 API 程序，Demo 時很容易 OOM。因此第一版固定：

- Hunyuan3D-2mini shape model。
- 不載入 Hunyuan3D Paint。
- 同時間只允許一個 generation。
- Shape 生成後加上參考圖投影貼圖；不額外載入 Paint 模型。側面／背面品質仍有限，正式資產可再用 Blender 精修。

## 安全邊界

Compose 只把 API 發布到校機的 `127.0.0.1:8081`。請勿改成 `0.0.0.0:8081`，也不要在防火牆開公開連接埠。本機透過 SSH tunnel 使用：

```bash
ssh -N -L 8081:127.0.0.1:8081 nccu-gpu
```

建立 tunnel 後，本機健康檢查網址才是：

```bash
curl http://127.0.0.1:8081/health
```

生成端點沒有瀏覽器 CORS，也沒有放在公網使用的身分驗證。下一階段應由 FastAPI 後端代理請求、保存 job 與產出；前端不應直接連校機。

## GPU 主機部署

SSH 連線恢復後，在校機執行：

```bash
git clone https://github.com/sophia112306/rag-npc-game.git
cd rag-npc-game
git switch main
docker compose -f infra/hunyuan3d/compose.yaml build
docker compose -f infra/hunyuan3d/compose.yaml up -d
docker compose -f infra/hunyuan3d/compose.yaml logs -f api
```

首次啟動會下載模型權重；`GET /live` 會先回應，`GET /health` 的 `status` 會依序由 `loading` 變成 `ready`。Compose 給模型下載與初始化 20 分鐘的 healthcheck start period。

Hunyuan 模型、Hugging Face cache 與 rembg 的 U2Net 權重都寫入 `hunyuan3d-models` named volume；重建 container 不會重複下載。不要只設定 `HF_HOME`：Hunyuan3D-2 的 shape loader 另讀取 `HY3DGEN_MODELS`，rembg 則讀取 `U2NET_HOME`。

查看狀態：

```bash
docker compose -f infra/hunyuan3d/compose.yaml ps
docker compose -f infra/hunyuan3d/compose.yaml logs --tail=200 api
docker stats --no-stream
```

校機目前 `loginctl show-user "$USER" -p Linger` 回報 `Linger=no`。主機重開機或所有使用者 session 結束後，不要假設 rootless Docker 一定會自動常駐；重新連線時若 health 無回應，執行：

```bash
systemctl --user start docker
cd ~/rag-npc-game
docker compose -f infra/hunyuan3d/compose.yaml up -d
```

若團隊需要無人登入也能在重開機後啟動，請由校機管理員依政策評估是否為這個帳號啟用 linger；不要自行改系統層設定。

停止服務但保留模型與輸出 volume：

```bash
docker compose -f infra/hunyuan3d/compose.yaml down
```

不要加 `--volumes`，否則會刪除已下載的模型 cache 與生成結果。

## 生成 API

`POST /generate` 接受：

```json
{
  "image": "<base64>",
  "seed": 1234,
  "octree_resolution": 256,
  "num_inference_steps": 5,
  "guidance_scale": 5.0,
  "max_faces": 40000
}
```

成功時直接回傳 `model/gltf-binary`。輸入限制為 12 MiB、24 MP、PNG／JPEG／WebP；輸出會依官方 FloaterRemover、DegenerateFaceRemover 與 FaceReducer 清理，`max_faces` 限制為 5,000～100,000。模型尚未完成載入時回 503，已有工作執行時回 429。

macOS 測試指令：

```bash
IMAGE_B64="$(base64 -i ./reference.png)"
curl --fail-with-body \
  -X POST http://127.0.0.1:8081/generate \
  -H 'Content-Type: application/json' \
  --data-binary "$(jq -n --arg image "$IMAGE_B64" '{image: $image}')" \
  --output ./generated.glb
file ./generated.glb
```

不要把大段 base64、SSH 密碼、private key 或任何 token 貼到聊天、commit 或 GitHub。

## 固定版本與相容性

- CUDA image：`nvidia/cuda:12.8.1-devel-ubuntu22.04`
- PyTorch：`2.7.1`、torchvision `0.22.1`、cu128 wheel。
- Hunyuan3D-2 upstream commit：`f8db63096c8282cb27354314d896feba5ba6ff8a`。
- Compose image tag：`rag-npc-hunyuan3d:2.0-mini-cu128`。

使用 Hunyuan3D 須遵守 Tencent Hunyuan Non-Commercial License；目前用途限課程、研究與非商業 Demo，若要公開或商業部署需重新審查授權。

## 2026-11-11 實機驗收

| 驗收項目 | 結果 |
| --- | --- |
| 校機 container | `ready`，RTX 5060 Ti，PyTorch 2.7.1+cu128，0 restart，未 OOM |
| 常駐 VRAM | 3,994 MiB |
| 128 raw generation | 4.73 秒，3,598,012 bytes，201,292 faces，watertight |
| 256 raw generation | 18.62 秒，15,713,432 bytes，875,034 faces，峰值 4,571 MiB |
| 正式 API＋後處理 | 6.75 秒，687,488 bytes，17,222 vertices／40,000 faces，watertight |
| 正式 API GLB SHA-256 | `0da27f0a5b4b2fe8217a27e8347d0070011f29cd1c10fe69fe49fb359b2b7fe4` |
| cache 重啟 | 強制重建 container 後 42 秒回到 `ready`，未重新下載 7.2 GB 模型 |
| SSH tunnel | 本機 `127.0.0.1:8081/health` 回傳 `ready` |

驗收輸入使用既有 `frontend/public/game/vidalia-cutout.png`。原始 128／256 GLB 只保存於校機 named volume 與本機 `/tmp/rag-npc-hunyuan3d-validation`，沒有提交 Git：視覺預覽顯示人形輪廓成立，但無材質且晶體感明顯，不符合正式維達利亞品質。正式 API 已加入官方後處理與面數限制，仍應把輸出視為待材質化的原始資產。

## 下一步

GPU gateway 的完成條件已達成：

1. 校機 image build 完成，container health 為 `ready`。
2. 用專案參考圖實際產出一個可由檢視器開啟的 GLB。
3. 記錄生成時間、VRAM 峰值、GLB 大小與失敗日誌。

後續精修仍需：

1. 已完成 FastAPI 持久化 3D asset job；正式多人部署再拆分外部 worker 與租約。
2. 由團隊提供獨立物件參考圖；不要使用整張風景圖或把角色單張正面結果直接當正式模型。
3. Babylon.js 已加入 GLB loader、尺寸／旋轉／位置、貼圖與載入 fallback；後續應提供正式資產的精確碰撞形狀。
4. 瀏覽器實際檢查 mesh 面數、材質、遮擋、相機穿模，production build 與回歸測試通過。
