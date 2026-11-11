import { Color3, Color4, DynamicTexture, FresnelParameters, Material, Mesh, MeshBuilder, MirrorTexture, ParticleSystem, Plane, Scene, ShaderMaterial, StandardMaterial, Texture, TransformNode, Vector3 } from "@babylonjs/core";
import type { WorldScene } from "../../lib/game-api";
import { COUNCIL_LAKE, insideCouncilLake } from "./sanctuary-layout";

/** Original painted leaves are reused over real tree trunks, not solid polygon crowns. */
export function createForestFoliage(scene: Scene) {
  const texture = new Texture("/game/forest-canopy.png", scene);
  texture.hasAlpha = true;
  const material = new StandardMaterial("original painted forest leaves", scene);
  material.diffuseTexture = texture;
  material.useAlphaFromDiffuseTexture = true;
  material.transparencyMode = Material.MATERIAL_ALPHATEST;
  material.alphaCutOff = .32;
  material.backFaceCulling = false;
  material.diffuseColor = new Color3(.92, .98, .78);
  material.emissiveColor = new Color3(.14, .18, .09);
  material.specularColor = Color3.Black();
  const barkTexture = new DynamicTexture("original forest bark grain", {
    width: 128,
    height: 512
  }, scene, true);
  const ctx = barkTexture.getContext();
  ctx.fillStyle = "#595240";
  ctx.fillRect(0, 0, 128, 512);
  for (let i = 0; i < 90; i++) {
    ctx.strokeStyle = ["#403d30", "#756b50", "#625d42", "#4a5039"][i % 4];
    ctx.lineWidth = .5 + i % 3;
    ctx.beginPath();
    for (let y = 0; y <= 512; y += 8) {
      const x = i * 1.43 % 128 + Math.sin(y * .012 + i) * 2.5;
      if (y === 0) ctx.moveTo(x, y);else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  barkTexture.update();
  barkTexture.uScale = 2;
  barkTexture.vScale = 2;
  const bark = new StandardMaterial("original forest bark", scene);
  bark.diffuseTexture = barkTexture;
  bark.diffuseColor = new Color3(.95, .93, .86);
  bark.emissiveColor = new Color3(.03, .03, .02);
  bark.specularColor = Color3.Black();
  return {
    material,
    bark,
    dispose() {
      material.dispose();
      texture.dispose();
      bark.dispose();
      barkTexture.dispose();
    }
  };
}
export function addForestTree(scene: Scene, parent: TransformNode, material: StandardMaterial, bark: StandardMaterial, x: number, y: number, z: number, height: number, yaw: number, index: number) {
  const crown = new TransformNode(`painted crown ${index}`, scene);
  crown.parent = parent;
  crown.position.set(x, y, z);
  // Restore the original continuous trunk, with slight bends and branching.
  // GPU roots remain below it; low quality generated crowns are not exposed.
  const lean = Math.sin(index * 2.3) * .3;
  const path = [new Vector3(0, -.06, 0), new Vector3(lean, .18 * height, .08), new Vector3(lean * .7, .36 * height, -.08), new Vector3(lean + .12, .56 * height, .05)];
  const trunk = MeshBuilder.CreateTube(`original forest trunk ${index}`, {
    path,
    tessellation: 16,
    radiusFunction: i => height * (.033 - i * .006),
    cap: Mesh.CAP_ALL
  }, scene);
  trunk.parent = crown;
  trunk.material = bark;
  trunk.isPickable = false;
  trunk.receiveShadows = true;
  const wood = [trunk];
  for (let i = 0; i < 3; i++) {
    const angle = yaw + i * 2.1;
    const branch = MeshBuilder.CreateTube(`forest branch ${index}-${i}`, {
      path: [new Vector3(lean, .30 * height, 0), new Vector3(Math.sin(angle) * height * .09, .42 * height, Math.cos(angle) * height * .09), new Vector3(Math.sin(angle) * height * .17, .51 * height, Math.cos(angle) * height * .17)],
      tessellation: 10,
      radiusFunction: j => height * (.014 - j * .005),
      cap: Mesh.CAP_ALL
    }, scene);
    branch.parent = crown;
    branch.material = bark;
    branch.isPickable = false;
    branch.receiveShadows = true;
    wood.push(branch);
  }
  // Different overlapping lobes create depth without repeating a whole tree silhouette.
  for (let i = 0; i < 3; i++) {
    const leaf = MeshBuilder.CreatePlane(`canopy lobe ${index}-${i}`, {
      width: height * (.72 + i * .035),
      height: height * .49
    }, scene);
    leaf.parent = crown;
    leaf.position.set(Math.sin(index * 1.7 + i) * height * .06, height * (.51 + i * .035), Math.cos(index + i) * height * .05);
    leaf.rotation.y = yaw + i * Math.PI / 3;
    leaf.rotation.z = Math.sin(index + i) * .11;
    leaf.material = material;
    leaf.isPickable = false;
  }
  return wood;
}

/** Authored focal composition restored from the original council, kept separate from generated props. */
export function createForestSanctuary(scene: Scene, parent: TransformNode, world: WorldScene) {
  const materials: StandardMaterial[] = [];
  const textures: Texture[] = [];
  const stoneTexture = new Texture("/game/forest-stone.png", scene);
  textures.push(stoneTexture);
  const material = (name: string, colour: string, emissive?: string) => {
    const m = new StandardMaterial(name, scene);
    m.diffuseColor = Color3.FromHexString(colour);
    m.specularColor = new Color3(.05, .08, .07);
    if (emissive) m.emissiveColor = Color3.FromHexString(emissive);
    materials.push(m);
    return m;
  };
  const stone = material("weathered council stone", "#889d91");
  stone.diffuseTexture = stoneTexture;
  const lightStone = material("sunlit worn stone", "#b7c1a8");
  lightStone.diffuseTexture = stoneTexture;
  const darkStone = material("shaded mossy stone", "#637c6c");
  darkStone.diffuseTexture = stoneTexture;
  const rune = material("subtle turquoise engravings", "#3d7060", "#04110b");
  const gold = material("worn brass engravings", "#786b45", "#080601");
  const root = new TransformNode("original council sanctuary", scene);
  root.parent = parent;
  const at = (mesh: Mesh, x: number, y: number, z: number, m: StandardMaterial, walkable = false) => {
    mesh.parent = root;
    mesh.position.set(x - world.interaction_x, y, z - world.interaction_z);
    mesh.material = m;
    mesh.receiveShadows = true;
    mesh.isPickable = walkable;
    mesh.metadata = walkable ? {
      walkable: true
    } : null;
    return mesh;
  };
  const cx = world.interaction_x,
    cz = world.interaction_z;
  const base = at(MeshBuilder.CreateCylinder("council lower step", {
    diameterTop: 9.3,
    diameterBottom: 9.6,
    height: .13,
    tessellation: 96
  }, scene), cx, .055, cz, darkStone, true);
  const dais = at(MeshBuilder.CreateCylinder("council engraved dais", {
    diameterTop: 8.8,
    diameterBottom: 9.1,
    height: .19,
    tessellation: 96
  }, scene), cx, .205, cz, stone, true);
  base.metadata = {
    walkable: true,
    interaction: true
  };
  dais.metadata = {
    walkable: true,
    interaction: true
  };
  for (const [i, radius] of [2.1, 3.2, 4.15].entries()) at(MeshBuilder.CreateTorus(`council etched ring ${i}`, {
    diameter: radius * 2,
    thickness: .032,
    tessellation: 128
  }, scene), cx, .307, cz, i === 1 ? rune : gold);
  for (let i = 0; i < 24; i++) {
    const angle = i / 24 * Math.PI * 2;
    const mark = at(MeshBuilder.CreateBox(`radial carved mark ${i}`, {
      width: .36,
      height: .008,
      depth: .045
    }, scene), cx + Math.sin(angle) * 3.67, .307, cz + Math.cos(angle) * 3.67, i % 3 ? gold : rune);
    mark.rotation.y = angle;
  }
  for (let i = 0; i < 18; i++) {
    const z = 8 - i * .69;
    if (z < cz + 4.65) break;
    const x = Math.sin(i * 1.7) * .16;
    const slab = at(MeshBuilder.CreateBox(`original path slab ${i}`, {
      width: 2.35 + i % 3 * .10,
      height: .085,
      depth: .61
    }, scene), x, .035, z, i % 3 ? lightStone : stone, true);
    slab.rotation.y = Math.sin(i * 1.41) * .065;
  }
  const columns = [[-4.7, cz + .8, 2.85], [4.6, cz + .5, 3.15], [-5.1, cz + 4.1, 1.65], [5.3, cz + 3.7, 2.05]];
  for (const [i, [x, z, h]] of columns.entries()) {
    at(MeshBuilder.CreateCylinder(`council pillar foot ${i}`, {
      diameterTop: .87,
      diameterBottom: 1.02,
      height: .21,
      tessellation: 12
    }, scene), x, .105, z, darkStone);
    const shaft = at(MeshBuilder.CreateCylinder(`council pillar ${i}`, {
      diameterTop: .49,
      diameterBottom: .66,
      height: h,
      tessellation: 16
    }, scene), x, h / 2 + .2, z, i % 2 ? stone : darkStone);
    shaft.rotation.z = (i % 2 ? 1 : -1) * .025;
    at(MeshBuilder.CreateCylinder(`council pillar cap ${i}`, {
      diameterTop: .88,
      diameterBottom: .71,
      height: .18,
      tessellation: 12
    }, scene), x, h + .23, z, lightStone);
    at(MeshBuilder.CreateTorus(`pillar engraving ${i}`, {
      diameter: .53,
      thickness: .025,
      tessellation: 32
    }, scene), x, h + .1, z, rune);
  }
  const lake = MeshBuilder.CreateDisc("original forest lake", {
    radius: 1,
    tessellation: 100,
    sideOrientation: Mesh.DOUBLESIDE
  }, scene);
  lake.parent = root;
  lake.position.set(COUNCIL_LAKE.x - cx, .035, COUNCIL_LAKE.z - cz);
  lake.rotation.x = Math.PI / 2;
  lake.scaling.set(COUNCIL_LAKE.rx, COUNCIL_LAKE.rz, 1);
  lake.isPickable = false;
  const water = material("reflecting teal forest water", "#0b302e", "#010505");
  water.alpha = .98;
  water.specularColor = new Color3(.2, .3, .22);
  water.specularPower = 128;
  const reflection = new MirrorTexture("council lake reflection", 512, scene, true);
  reflection.mirrorPlane = new Plane(0, -1, 0, .035);
  reflection.level = .35;
  reflection.refreshRate = 2;
  water.reflectionTexture = reflection;
  const fresnel = new FresnelParameters();
  fresnel.bias = .2;
  fresnel.power = 3;
  fresnel.leftColor = Color3.White();
  fresnel.rightColor = new Color3(.16, .22, .20);
  water.reflectionFresnelParameters = fresnel;
  const ripples = new DynamicTexture("soft water normal ripples", 128, scene, false);
  const ctx = ripples.getContext();
  const image = new ImageData(128, 128);
  for (let j = 0; j < 128; j++) for (let i = 0; i < 128; i++) {
    const n = (j * 128 + i) * 4;
    image.data[n] = 128 + Math.sin(i * .22 + j * .13) * 12;
    image.data[n + 1] = 128 + Math.cos(j * .21 - i * .09) * 10;
    image.data[n + 2] = 250;
    image.data[n + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  ripples.update();
  ripples.uScale = 3;
  ripples.vScale = 4;
  ripples.level = .14;
  water.bumpTexture = ripples;
  textures.push(ripples);
  lake.material = water;
  for (let i = 0; i < 28; i++) {
    const a = i / 28 * Math.PI * 2;
    const size = .22 + i % 4 * .055;
    const rock = at(MeshBuilder.CreateIcoSphere(`lake bank stone ${i}`, {
      radius: size,
      subdivisions: 2
    }, scene), COUNCIL_LAKE.x + Math.cos(a) * (COUNCIL_LAKE.rx + .04), .02, COUNCIL_LAKE.z + Math.sin(a) * (COUNCIL_LAKE.rz + .02), i % 3 ? darkStone : stone);
    rock.scaling.set(1.3, .6, 1);
    rock.rotation.y = a;
  }

  // A curved, mist-blended distant forest preserves the original artwork's palette.
  const backdrop = MeshBuilder.CreateCylinder("distant painted forest", {
    diameter: 220,
    height: 69,
    tessellation: 96,
    cap: Mesh.NO_CAP,
    sideOrientation: Mesh.BACKSIDE
  }, scene);
  backdrop.parent = root;
  // Stay beyond the entire walkable area, including its diagonal corners.
  backdrop.position.set(-cx, 24, -cz);
  backdrop.isPickable = false;
  const forestTexture = new Texture("/game/forest-eye-backdrop.png", scene);
  textures.push(forestTexture);
  const backdropMaterial = new ShaderMaterial("mist blended forest artwork", scene, {
    vertexSource: `precision highp float;attribute vec3 position;attribute vec2 uv;uniform mat4 worldViewProjection;varying vec2 v;void main(){v=uv;gl_Position=worldViewProjection*vec4(position,1.);}`,
    fragmentSource: `precision highp float;varying vec2 v;uniform sampler2D forest;uniform vec3 mist;uniform float daylight;void main(){float u=1.-abs(fract(v.x*2.)*2.-1.);vec3 c=texture2D(forest,vec2(u,v.y)).rgb;float edge=smoothstep(.01,.30,v.y)*(1.-smoothstep(.67,1.,v.y));c=mix(c,mist,.32)*daylight;gl_FragColor=vec4(c,edge*.94);}`
  }, {
    attributes: ["position", "uv"],
    uniforms: ["worldViewProjection", "mist", "daylight"],
    samplers: ["forest"],
    needAlphaBlending: true
  });
  backdropMaterial.setTexture("forest", forestTexture);
  backdropMaterial.setColor3("mist", scene.fogColor);
  backdropMaterial.setFloat("daylight", world.config.time_of_day === "night" ? .19 : world.config.time_of_day === "dusk" ? .7 : 1);
  backdropMaterial.backFaceCulling = false;
  backdropMaterial.disableDepthWrite = true;
  backdrop.material = backdropMaterial;
  backdrop.alphaIndex = -100;
  const motesTexture = new DynamicTexture("forest pollen light", 32, scene, false);
  const mctx = motesTexture.getContext();
  const gradient = mctx.createRadialGradient(16, 16, 0, 16, 16, 15);
  gradient.addColorStop(0, "#ffffff");
  gradient.addColorStop(1, "#ffffff00");
  mctx.fillStyle = gradient;
  mctx.fillRect(0, 0, 32, 32);
  motesTexture.update();
  const motes = new ParticleSystem("forest sunlit motes", 80, scene);
  motes.particleTexture = motesTexture;
  motes.emitter = new Vector3(0, 1, -7);
  motes.minEmitBox = new Vector3(-10, 0, -10);
  motes.maxEmitBox = new Vector3(9, 5, 9);
  motes.color1 = new Color4(.9, .83, .49, .28);
  motes.color2 = new Color4(.5, .9, .78, .12);
  motes.colorDead = new Color4(0, 0, 0, 0);
  motes.minSize = .018;
  motes.maxSize = .045;
  motes.minLifeTime = 4;
  motes.maxLifeTime = 8;
  motes.emitRate = 6;
  motes.direction1 = new Vector3(-.1, .03, -.05);
  motes.direction2 = new Vector3(.1, .1, .1);
  motes.start();
  return {
    height(x: number, z: number) {
      const r = Math.hypot(x - cx, z - cz);
      return r < 4.4 ? .30 : r < 4.8 ? .12 : Math.abs(x) < 1.3 && z > cz + 4.5 && z < 8.6 ? .08 : -Infinity;
    },
    blocked(x: number, z: number) {
      return insideCouncilLake(x, z, .2) || columns.some(([px, pz]) => Math.hypot(x - px, z - pz) < .62);
    },
    update(time: number) {
      ripples.uOffset = time * .008;
      ripples.vOffset = time * .005;
      reflection.renderList = scene.meshes.filter(mesh => mesh !== lake && mesh !== backdrop && !mesh.name.includes("sky") && !mesh.name.startsWith("flame"));
    },
    dispose() {
      motes.dispose();
      reflection.dispose();
      backdropMaterial.dispose();
      for (const m of materials) m.dispose(false, false);
      for (const t of textures) t.dispose();
    }
  };
}
