"""Session-scoped asset jobs and self-contained GLB downloads."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.orchestration.game_orchestrator import SessionNotFoundError
from backend.schemas.world_scene import EnqueueSceneAssetsRequest, SceneAssetJobView

router = APIRouter(prefix="/api/game", tags=["scene-assets"])


@router.post(
    "/{session_id}/scene-assets",
    response_model=list[SceneAssetJobView],
    status_code=202,
)
async def enqueue(session_id: str, body: EnqueueSceneAssetsRequest, request: Request):
    try:
        state = await request.app.state.game_orchestrator.get_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)}
        ) from exc
    if state.state_version != body.expected_state_version:
        raise HTTPException(
            409,
            detail={
                "code": "STATE_VERSION_CONFLICT",
                "message": "場景版本已更新，請同步後重試。",
            },
        )
    return await request.app.state.scene_asset_coordinator.enqueue(state)


@router.get("/{session_id}/scene-assets/{job_id}", response_model=SceneAssetJobView)
async def get_job(session_id: str, job_id: str, request: Request):
    row = await request.app.state.scene_asset_coordinator.get(session_id, job_id)
    if row is None:
        raise HTTPException(404, detail="Asset job not found")
    return row


@router.get("/{session_id}/scene-assets/{job_id}/model")
async def get_model(session_id: str, job_id: str, request: Request):
    coordinator = request.app.state.scene_asset_coordinator
    row = await coordinator.get(session_id, job_id)
    if row is None or row.status != "succeeded":
        raise HTTPException(404, detail="Model not ready")
    path = coordinator.output_dir / f"{row.job_id}.glb"
    if not path.is_file():
        raise HTTPException(404, detail="Model missing")
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        headers={"Cache-Control": "private, max-age=86400"},
    )
