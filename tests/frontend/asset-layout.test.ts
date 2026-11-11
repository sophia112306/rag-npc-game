import test from "node:test";
import assert from "node:assert/strict";
import { fitAsset } from "../../frontend/components/experiments/asset-layout.ts";

test("a wide generated model stays inside its promised placement footprint",()=>{
  const fit=fitAsset({x:20,y:.5,z:3},6.8);
  assert.ok(Math.abs(fit.width-6.8)<1e-9);
  assert.ok(fit.height<6.8&&fit.depth<6.8);
});
test("depth participates in normalization so rotated altars cannot become giant walls",()=>{
  const fit=fitAsset({x:2,y:1,z:40},3);
  assert.equal(fit.depth,3);
  assert.ok(fit.width<=3&&fit.height<=3);
});
test("flat, empty and non-finite geometry is rejected before replacing a scene",()=>{
  for(const size of [{x:1,y:0,z:1},{x:1,y:1e-4,z:1},{x:NaN,y:1,z:1},{x:1,y:Infinity,z:1}]) {
    assert.throws(()=>fitAsset(size,3));
  }
});
