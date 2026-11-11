import test from "node:test";
import assert from "node:assert/strict";
import { createFirstPerson } from "../../frontend/components/experiments/first-person.ts";

class Surface {
  listeners=new Map<string,Set<(event:any)=>void>>();
  tag="canvas";
  focus(){}
  closest(selector:string){return selector.split(",").includes(this.tag)?this:null;}
  setPointerCapture(){}
  addEventListener(type:string,listener:any){if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type)!.add(listener);}
  removeEventListener(type:string,listener:any){this.listeners.get(type)?.delete(listener);}
  emit(type:string,values:Record<string,unknown>={}){for(const listener of this.listeners.get(type)??[])listener({preventDefault(){},button:0,clientX:0,clientY:0,...values});}
}

function setup(){
  const windowSurface=new Surface(),canvas=new Surface();
  Object.assign(globalThis,{window:windowSurface,document:{pointerLockElement:null},HTMLElement:Surface});
  let picked:{x:number;z:number;interaction?:boolean}|null={x:0,z:4};let interactions=0;
  const driver={pickGround:()=>picked,move:(x:number,z:number,dx:number,dz:number)=>({x:x+dx,z:z+dz}),setView(){},setWorld:async()=>{},setAsset:async()=>{},render(){},resize(){},dispose(){}};
  const controls=createFirstPerson(canvas as unknown as HTMLCanvasElement,driver,()=>interactions++,()=>{});
  return{canvas,windowSurface,controls,setPicked:(point:typeof picked)=>{picked=point;},interactions:()=>interactions};
}

test("WASD still moves after a toolbar button has focus",()=>{
  const {controls,windowSurface}=setup();const button=new Surface();button.tag="button";
  windowSurface.emit("keydown",{key:"w",code:"KeyW",target:button});controls.tick(.2);
  assert.ok(controls.pose.z<8);controls.dispose();
});
test("physical W works while Chinese IME reports Process",()=>{
  const {controls,windowSurface,canvas}=setup();
  windowSurface.emit("keydown",{key:"Process",code:"KeyW",isComposing:true,target:canvas});controls.tick(.2);
  assert.ok(controls.pose.z<8);windowSurface.emit("keyup",{key:"Process",code:"KeyW"});const stopped=controls.pose.z;controls.tick(.2);assert.equal(controls.pose.z,stopped);controls.dispose();
});
test("typing a movement letter in dialogue does not move the player",()=>{
  const {controls,windowSurface}=setup();const input=new Surface();input.tag="input";
  windowSurface.emit("keydown",{key:"w",code:"KeyW",target:input});controls.tick(.2);assert.equal(controls.pose.z,8);controls.dispose();
});
test("clicking ground moves to the chosen point without a fixed rail",()=>{
  const {controls,canvas}=setup();canvas.emit("pointerdown");canvas.emit("pointerup");
  for(let i=0;i<40;i++)controls.tick(.05);
  assert.ok(Math.abs(controls.pose.z-4)<.2);controls.dispose();
});
test("dragging only turns the camera and does not start click movement",()=>{
  const {controls,canvas}=setup();canvas.emit("pointerdown");canvas.emit("pointermove",{clientX:100,clientY:20});canvas.emit("pointerup");controls.tick(.2);
  assert.notEqual(controls.pose.yaw,0);assert.equal(controls.pose.z,8);controls.dispose();
});
test("touch directions stop when paused and work after returning",()=>{
  const {controls}=setup();controls.setMove("forward",true);controls.tick(.2);const moved=controls.pose.z;
  controls.pause(true);controls.tick(.2);assert.equal(controls.pose.z,moved);controls.pause(false);controls.setMove("right",true);controls.tick(.2);assert.ok(controls.pose.x>0);controls.dispose();
});

test("map route tracking shares walking and stops near the landmark before interacting",()=>{
  const {controls,interactions}=setup();
  const target={x:0,z:-8,interaction:true};
  controls.pause(true);controls.pause(false);controls.walkTo(target);
  for(let i=0;i<120;i++)controls.tick(.05);
  assert.equal(interactions(),1);
  assert.ok(controls.pose.z>-8+2.5 && controls.pose.z<-8+3.6);
  assert.deepEqual(target,{x:0,z:-8,interaction:true});
  controls.dispose();
});
