# Hunyuan3D 校內 GPU 部署與交接

進度：`██████░░░░ 60%`（容器與私有 API 已完成；待校機 build、首個 GLB 與 Babylon 載入）

## 這一階段的範圍

本階段提供一個可重現的 Hunyuan3D shape-only 服務，用單張 PNG／JPEG／WebP 產生 GLB。它不會把風景圖直接變成完整可玩的 3D 關卡；第一個用途是生成祭壇、遺跡、枯木、符石等可獨立擺放的 mesh，之後再由 Babylon.js 組裝場景。

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
- 先輸出無貼圖 GLB，再由既有場景圖或後續 Blender／材質流程處理外觀。

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
git switch feature/hunyuan3d-gpu-gateway
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
  "guidance_scale": 5.0
}
```

成功時直接回傳 `model/gltf-binary`。輸入限制為 12 MiB、24 MP、PNG／JPEG／WebP；模型尚未完成載入時回 503，已有工作執行時回 429。

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

## 完成定義與下一步

這個階段要到以下條件全部成立才可標成 100%：

1. 校機 image build 完成，container health 為 `ready`。
2. 用專案參考圖實際產出一個可由檢視器開啟的 GLB。
3. 記錄生成時間、VRAM 峰值、GLB 大小與失敗日誌。
4. FastAPI 新增可持久化的 3D asset job，不讓瀏覽器直接呼叫 GPU。
5. Babylon.js 加入 GLB loader、尺寸／旋轉／位置 metadata、載入失敗 fallback。
6. 瀏覽器實際檢查 mesh 不遮住 UI、相機不穿模，production build 與回歸測試通過。

目前阻礙：2026-11-11 最後一次連線時，TCP 22 可建立，但 SSH 在 server banner 前逾時；本機路由顯示走一般 `en0` gateway，而不是先前成功時的 VPN `utun`。這是 VPN／校網路由問題，不是 public key 或 Docker 設定錯誤。恢復 VPN 路由後從本節部署命令接續。
