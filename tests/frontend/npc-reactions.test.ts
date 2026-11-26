import assert from "node:assert/strict";
import test from "node:test";

import { resolveNpcReaction } from "../../frontend/lib/npc-reactions.ts";

test("maps model emotions to bounded presentation cues", () => {
  assert.equal(resolveNpcReaction("focused"), "attentive");
  assert.equal(resolveNpcReaction("thoughtful"), "thoughtful");
  assert.equal(resolveNpcReaction("wary"), "guarded");
  assert.equal(resolveNpcReaction("firm"), "firm");
  assert.equal(resolveNpcReaction("shocked"), "surprised");
  assert.equal(resolveNpcReaction("驚恐"), "fearful");
});

test("unknown model output cannot select an arbitrary animation", () => {
  assert.equal(resolveNpcReaction("teleport-off-map"), "idle");
  assert.equal(resolveNpcReaction(null), "idle");
});
