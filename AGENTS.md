# Project execution policy

These rules apply to every change in this repository.

## School GPU development

- GPU/model/Gateway work must run through `ssh nccu-gpu` and then inside Docker.
- Do not start vLLM, the NPC Gateway, training, or GPU evaluation in a host virtual environment.
- Use `infra/npc_gateway/compose.yaml` for the NPC runtime. Keep ports bound to `127.0.0.1`; this project is not authorized for public deployment.
- Run backend tests inside the project Docker container before committing model or story integration changes.
- Keep generated logs, caches, virtual environments, and `training/outputs/` out of Git.

## Git workflow

- Integrate on `main`; do not create an extra branch unless the user explicitly asks for one.
- Preserve unrelated teammate changes. Inspect and save a recoverable patch or stash before moving a dirty checkout.
- A completed stage may be committed and pushed only after its relevant tests pass.
- Do not claim an NPC LoRA is ready merely because its weight file exists. Verify the running `/health` route and real generated replies.

## Story authority

- The backend owns items, scene transitions, choices, and endings. Model dialogue cannot establish those facts.
- Model guidance may use only player-visible objectives and currently legal action labels computed by the backend.
- Fixed scene and item assets remain authoritative. Stop and ask the user before generating a missing scene or prop.
