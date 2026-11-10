import {
  Color3,
  Color4,
  DirectionalLight,
  Engine,
  HemisphericLight,
  Layer,
  Mesh,
  MeshBuilder,
  PointLight,
  Scene,
  StandardMaterial,
  Texture,
  UniversalCamera,
  Vector3,
  VertexData,
  TransformNode,
} from "@babylonjs/core";
import type { SceneVisualProfile } from "../../lib/game-api";
import { EYE_HEIGHT, NPC, pillars, RELIC, trees, type Pick, type TrialDriver } from "./world";

export function createBabylonDriver(canvas: HTMLCanvasElement): TrialDriver {
  const engine = new Engine(canvas, true, { powerPreference: "high-performance", stencil: false });
  engine.setHardwareScalingLevel(1 / Math.min(window.devicePixelRatio || 1, 1.5));
  const scene = new Scene(engine);
  scene.clearColor = new Color4(0.08, 0.18, 0.22, 1);
  scene.fogMode = Scene.FOGMODE_EXP2;
  scene.fogColor = new Color3(0.16, 0.32, 0.36);
  scene.fogDensity = 0.011;
  scene.ambientColor = new Color3(0.18, 0.23, 0.27);

  const camera = new UniversalCamera("eye", new Vector3(0, EYE_HEIGHT, 8), scene);
  camera.fov = 68 * Math.PI / 180;
  camera.minZ = 0.08;
  camera.maxZ = 100;
  camera.setTarget(new Vector3(0, EYE_HEIGHT, 7));
  scene.activeCamera = camera;

  const sky = new HemisphericLight("sky fill", new Vector3(0, 1, 0), scene);
  sky.intensity = 0.72;
  sky.diffuse = new Color3(0.82, 0.9, 0.89);
  sky.groundColor = new Color3(0.18, 0.25, 0.22);
  const moon = new DirectionalLight("cool daylight", new Vector3(0.35, -1, -0.5), scene);
  moon.intensity = 0.85;
  moon.diffuse = new Color3(0.78, 0.89, 0.88);
  const goldLight = new DirectionalLight("filtered sunlight", new Vector3(-0.7, -1, 0.35), scene);
  goldLight.intensity = 0.26;
  goldLight.diffuse = new Color3(1, 0.88, 0.69);

  function material(name: string, color: string, emissive?: string) {
    const value = new StandardMaterial(name, scene);
    value.diffuseColor = Color3.FromHexString(color);
    value.specularColor = new Color3(0.08, 0.12, 0.12);
    if (emissive) value.emissiveColor = Color3.FromHexString(emissive);
    return value;
  }
  const stoneTexture = new Texture("/game/forest-stone.png", scene);
  const stone = material("textured carved stone", "#92958a");
  const stoneLight = material("textured weathered stone", "#aaafa0");
  const stoneDark = material("textured mossy stone", "#657970");
  for (const surface of [stone, stoneLight, stoneDark]) surface.diffuseTexture = stoneTexture;
  const moss = material("deep moss", "#537e65");
  const gold = material("aged runes", "#978767", "#0b1614");
  const rune = material("luminous runes", "#668f88", "#183d39");
  const bark = material("wet bark", "#4b4336");
  const canopyTexture = new Texture("/game/forest-canopy.png", scene);
  canopyTexture.hasAlpha = true;
  const canopyMaterial = material("painted leaf canopy", "#d2d6ba");
  canopyMaterial.diffuseTexture = canopyTexture;
  canopyMaterial.useAlphaFromDiffuseTexture = true;
  canopyMaterial.backFaceCulling = false;

  function at(mesh: Mesh, x: number, y: number, z: number, surface: StandardMaterial, pickable = false) {
    mesh.position.set(x, y, z);
    mesh.material = surface;
    mesh.isPickable = pickable;
    return mesh;
  }

  const groundTexture = new Texture("/game/forest-floor.png", scene);
  groundTexture.uScale = 4.5;
  groundTexture.vScale = 4.5;
  const groundMat = material("textured forest floor", "#b5c2b6");
  groundMat.diffuseTexture = groundTexture;
  const ground = at(MeshBuilder.CreateGround("walkable forest", { width: 80, height: 80, subdivisions: 1 }, scene), 0, 0, 0, groundMat, true);

  const backgroundTexture = new Texture("/game/forest-eye-backdrop.png", scene);
  const backdropLayer = new Layer("painted scene backdrop", null, scene, true);
  let activeBackgroundTexture = backgroundTexture;
  let activeBackgroundUrl = "/game/forest-eye-backdrop.png";
  let backdropRequest = 0;
  let backdropLoad: { request: number; url: string; promise: Promise<void> } | null = null;
  let disposed = false;
  backdropLayer.texture = activeBackgroundTexture;

  // Shallow broken paving leads directly to the council ring.
  for (let i = 0; i < 19; i++) {
    const z = 8 - i * 0.72;
    const x = Math.sin(i * 2.1) * 0.29;
    const slab = at(MeshBuilder.CreateBox(`path slab ${i}`, { width: 2.45 + i % 3 * 0.18, height: 0.09, depth: 0.61 }, scene), x, 0.045, z, i % 3 ? stoneLight : stone);
    slab.rotation.y = Math.sin(i * 1.41) * 0.09;
    if (i % 3 === 0) {
      at(MeshBuilder.CreateBox(`moss between slabs ${i}`, { width: 0.38, height: 0.025, depth: 0.28 }, scene), x + 1.04, 0.104, z, moss);
    }
  }

  // Small worn stones continue the walk from Vidalia's stopping point toward the relic.
  for (const [i, [x, z, angle]] of [
    [0.46, -5.08, -0.13], [0.76, -4.91, -0.27], [1.08, -4.69, -0.4],
    [1.39, -4.39, -0.53], [1.67, -4.04, -0.67], [1.91, -3.69, -0.75],
  ].entries()) {
    const slab = at(MeshBuilder.CreateBox(`relic branch stone ${i}`, {
      width: 0.92, height: 0.055, depth: 0.48,
    }, scene), x, Math.hypot(x, z + 8) < 4.4 ? 0.292 : 0.035, z, i % 2 ? stoneLight : stone);
    slab.rotation.y = angle;
  }

  at(MeshBuilder.CreateCylinder("council dais", { diameterTop: 8.8, diameterBottom: 9.2, height: 0.32, tessellation: 64 }, scene), 0, 0.09, -8, stone);
  for (const [i, radius] of [2.1, 3.2, 4.15].entries()) {
    at(MeshBuilder.CreateTorus(`etched ring ${i}`, { diameter: radius * 2, thickness: 0.065, tessellation: 96 }, scene), 0, 0.265, -8, i === 1 ? rune : gold);
  }
  for (let i = 0; i < 24; i++) {
    const a = i / 24 * Math.PI * 2;
    const mark = at(MeshBuilder.CreateBox(`radial inscription ${i}`, { width: 0.43, height: 0.026, depth: 0.075 }, scene), Math.sin(a) * 3.65, 0.27, -8 + Math.cos(a) * 3.65, i % 3 ? gold : rune);
    mark.rotation.y = a;
  }
  for (const [i, [x, z, size]] of [
    [-3.55, -3.82, 0.23], [-3.27, -4.13, 0.14], [3.62, -4.4, 0.19],
  ].entries()) {
    const rock = at(MeshBuilder.CreateIcoSphere(`council edge rock ${i}`, {
      radius: size, subdivisions: 0,
    }, scene), x, size * 0.48, z, i === 1 ? stoneDark : stoneLight);
    rock.scaling.y = 0.67;
    rock.rotation.y = i * 1.4;
  }

  for (const [i, [x, z, h]] of pillars.entries()) {
    at(MeshBuilder.CreateCylinder(`pillar foot ${i}`, { diameterTop: 0.95, diameterBottom: 1.1, height: 0.26, tessellation: 8 }, scene), x, 0.13, z, stoneLight);
    at(MeshBuilder.CreateCylinder(`pillar ${i}`, { diameterTop: 0.59, diameterBottom: 0.78, height: h, tessellation: 8 }, scene), x, h / 2 + 0.23, z, i % 2 ? stoneDark : stone);
    at(MeshBuilder.CreateCylinder(`pillar cap ${i}`, { diameterTop: 0.97, diameterBottom: 0.8, height: 0.25, tessellation: 8 }, scene), x, h + 0.27, z, stoneLight);
    at(MeshBuilder.CreateCylinder(`pillar rune ${i}`, { diameter: 0.62, height: 0.045, tessellation: 8 }, scene), x, h + 0.42, z, rune);
  }

  for (const [i, [x, z, scale]] of trees.entries()) {
    const trunk = at(MeshBuilder.CreateCylinder(`tree trunk ${i}`, { diameterTop: 0.6 * scale, diameterBottom: 1.24 * scale, height: 5.3 * scale, tessellation: 9 }, scene), x, 2.65 * scale, z, bark);
    trunk.rotation.z = (i % 2 ? -1 : 1) * 0.065;
    for (let j = 0; j < 3; j++) {
      const canopy = at(MeshBuilder.CreatePlane(`leaf canopy ${i}-${j}`, { width: 6.9 * scale, height: 5.2 * scale }, scene),
        x, 5.15 * scale, z, canopyMaterial);
      canopy.rotation.y = j * Math.PI / 3 + i * 0.17;
    }
    for (let j = 0; j < 2; j++) {
      const lowerLeaves = at(MeshBuilder.CreatePlane(`lower leaves ${i}-${j}`, { width: 4.7 * scale, height: 3.5 * scale }, scene),
        x, 3.9 * scale, z, canopyMaterial);
      lowerLeaves.rotation.y = j * Math.PI / 2 + i * 0.17;
    }
  }

  const water = material("spring water", "#2d9297", "#1e626c");
  water.alpha = 0.86;
  at(MeshBuilder.CreateCylinder("forest spring", { diameter: 5.6, height: 0.07, tessellation: 48 }, scene), -6.1, 0.045, -8.7, water);
  for (let i = 0; i < 16; i++) {
    const a = i * Math.PI * 2 / 16;
    const rock = at(MeshBuilder.CreateIcoSphere(`spring rock ${i}`, { radius: 0.34 + i % 3 * 0.08, subdivisions: 0 }, scene), -6.1 + Math.cos(a) * 2.8, 0.23, -8.7 + Math.sin(a) * 2.8, i % 3 ? stone : stoneLight);
    rock.rotation.y = i;
  }

  // Keep Vidalia's illustrated facial features and gown instead of constructing
  // an unrelated person from primitive shapes. The curved surface adds a small
  // amount of volume while a proper textured GLB is being prepared.
  const npcRoot = new TransformNode("Vidalia animated root", scene);
  npcRoot.position.set(NPC.x, 0, NPC.z);
  const npcTexture = new Texture("/game/vidalia-cutout.png", scene);
  npcTexture.hasAlpha = true;
  const npcMaterial = material("Vidalia original artwork", "#ffffff");
  npcMaterial.diffuseTexture = npcTexture;
  npcMaterial.useAlphaFromDiffuseTexture = true;
  npcMaterial.backFaceCulling = false;
  npcMaterial.emissiveColor = new Color3(0.38, 0.37, 0.33);
  npcMaterial.specularColor = Color3.Black();
  const npcMeshes = new Set<Mesh>();
  // A gently convex portrait surface avoids the edge-on collapse of a flat
  // plane while keeping every detail from the supplied character painting.
  const portraitWidth = 1.4;
  const portraitHeight = 3.42;
  const columns = 28;
  const rows = 68;
  const positions: number[] = [];
  const indices: number[] = [];
  const uvs: number[] = [];
  for (let row = 0; row <= rows; row++) {
    const v = row / rows;
    for (let column = 0; column <= columns; column++) {
      const u = column / columns;
      const x = (u - 0.5) * portraitWidth;
      const bodyCurve = Math.sin(v * Math.PI) * 0.12;
      const z = (1 - (2 * u - 1) ** 2) * (0.075 + bodyCurve);
      positions.push(x, (v - 0.5) * portraitHeight, z);
      uvs.push(u, v);
      if (row < rows && column < columns) {
        const a = row * (columns + 1) + column;
        indices.push(a, a + 1, a + columns + 1, a + 1, a + columns + 2, a + columns + 1);
      }
    }
  }
  const normals: number[] = [];
  VertexData.ComputeNormals(positions, indices, normals);
  const portraitData = new VertexData();
  portraitData.positions = positions;
  portraitData.indices = indices;
  portraitData.uvs = uvs;
  portraitData.normals = normals;
  const npcAvatar = new Mesh("Vidalia curved reference portrait", scene);
  portraitData.applyToMesh(npcAvatar);
  npcAvatar.parent = npcRoot;
  npcAvatar.position.y = 1.98;
  npcAvatar.billboardMode = Mesh.BILLBOARDMODE_Y;
  npcAvatar.material = npcMaterial;
  npcAvatar.isPickable = true;
  npcMeshes.add(npcAvatar);
  let npcTalking = false;

  const portraitLight = new PointLight("warm light on Vidalia", new Vector3(NPC.x - 1.5, 3.1, NPC.z + 2.2), scene);
  portraitLight.diffuse = new Color3(1, 0.79, 0.56);
  portraitLight.intensity = 0.58;
  portraitLight.range = 5.5;

  const pedestal = at(MeshBuilder.CreateCylinder("relic pedestal", { diameterTop: 0.9, diameterBottom: 1.2, height: 1.05, tessellation: 8 }, scene), RELIC.x, 0.52, RELIC.z, stoneDark, true);
  pedestal.rotation.y = 0.25;
  const relicMaterial = material("teal relic crystal", "#75b4a7", "#1c6962");
  const relic = at(MeshBuilder.CreatePolyhedron("floating relic", { type: 1, size: 0.43 }, scene), RELIC.x, 1.43, RELIC.z, relicMaterial, true);
  relic.rotation.z = 0.24;
  const relicLight = new PointLight("relic glow", new Vector3(RELIC.x, 1.4, RELIC.z), scene);
  relicLight.diffuse = new Color3(0.24, 0.72, 0.63);
  relicLight.intensity = 0.8;
  relicLight.range = 4;

  function propGroup(
    meshName: string,
  ): SceneVisualProfile["prop_groups"][number] | null {
    if (/^(tree trunk|leaf canopy|lower leaves)/.test(meshName)) return "forest";
    if (/^(path slab|moss between slabs|relic branch stone)/.test(meshName)) return "path";
    if (/^(council dais|etched ring|radial inscription|council edge rock)/.test(meshName)) return "council";
    if (/^pillar/.test(meshName)) return "pillars";
    if (/^(forest spring|spring rock)/.test(meshName)) return "spring";
    return null;
  }

  function setSceneProfile(profile: SceneVisualProfile) {
    const clear = Color3.FromHexString(profile.clear_color);
    scene.clearColor = new Color4(clear.r, clear.g, clear.b, 1);
    scene.fogColor = Color3.FromHexString(profile.fog_color);
    scene.fogDensity = profile.fog_density;
    scene.ambientColor = Color3.FromHexString(profile.ambient_color);

    groundMat.diffuseColor = Color3.FromHexString(profile.ground_color);
    groundMat.diffuseTexture = profile.use_ground_texture ? groundTexture : null;
    sky.diffuse = Color3.FromHexString(profile.sky_color);
    sky.groundColor = Color3.FromHexString(profile.sky_ground_color);
    sky.intensity = profile.sky_intensity;
    moon.diffuse = Color3.FromHexString(profile.key_light_color);
    moon.intensity = profile.key_light_intensity;
    goldLight.diffuse = Color3.FromHexString(profile.accent_light_color);
    goldLight.intensity = profile.accent_light_intensity;

    stone.diffuseColor = Color3.FromHexString(profile.surface_color);
    stoneLight.diffuseColor = Color3.FromHexString(profile.surface_light_color);
    stoneDark.diffuseColor = Color3.FromHexString(profile.surface_dark_color);
    moss.diffuseColor = Color3.FromHexString(profile.organic_color);
    bark.diffuseColor = Color3.FromHexString(profile.organic_color);
    rune.diffuseColor = Color3.FromHexString(profile.rune_color);
    rune.emissiveColor = Color3.FromHexString(profile.rune_emissive_color);
    water.diffuseColor = Color3.FromHexString(profile.liquid_color);
    water.emissiveColor = Color3.FromHexString(profile.liquid_emissive_color);

    const visibleGroups = new Set(profile.prop_groups);
    for (const mesh of scene.meshes) {
      const group = propGroup(mesh.name);
      if (group) mesh.setEnabled(visibleGroups.has(group));
    }
    ground.setEnabled(profile.show_ground);
    npcTalking = false;
    npcRoot.setEnabled(profile.show_vidalia);
    portraitLight.setEnabled(profile.show_vidalia);
    pedestal.setEnabled(profile.show_relic);
    relic.setEnabled(profile.show_relic);
    relicLight.setEnabled(profile.show_relic);
  }

  const started = performance.now();
  return {
    setSceneProfile,
    setBackdrop(url) {
      if (activeBackgroundUrl === url) {
        if (backdropLoad && backdropLoad.url !== url) {
          backdropRequest += 1;
          backdropLoad = null;
        }
        return Promise.resolve();
      }
      if (backdropLoad?.url === url) return backdropLoad.promise;

      const request = ++backdropRequest;
      let nextTexture: Texture;
      const promise = new Promise<void>((resolve, reject) => {
        nextTexture = new Texture(url, scene, false, true, Texture.TRILINEAR_SAMPLINGMODE, () => {
          if (disposed || request !== backdropRequest) {
            nextTexture.dispose();
            resolve();
            return;
          }
          const previousTexture = activeBackgroundTexture;
          activeBackgroundTexture = nextTexture;
          activeBackgroundUrl = url;
          backdropLayer.texture = nextTexture;
          backdropLoad = null;
          previousTexture.dispose();
          resolve();
        }, (message, exception) => {
          nextTexture.dispose();
          if (disposed || request !== backdropRequest) {
            resolve();
            return;
          }
          backdropLoad = null;
          reject(exception instanceof Error ? exception : new Error(message || `Unable to load backdrop: ${url}`));
        });
      });
      backdropLoad = { request, url, promise };
      return promise;
    },
    setTalking(talking) {
      npcTalking = talking;
    },
    setView(x, z, yaw, pitch, eyeBob = 0) {
      camera.position.set(x, EYE_HEIGHT + eyeBob, z);
      camera.setTarget(new Vector3(x + Math.sin(yaw) * Math.cos(pitch), EYE_HEIGHT + eyeBob + Math.sin(pitch), z - Math.cos(yaw) * Math.cos(pitch)));
    },
    pick(clientX, clientY): Pick {
      const bounds = canvas.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return null;
      const hit = scene.pick(clientX - bounds.left, clientY - bounds.top, (mesh) => mesh === ground || npcMeshes.has(mesh as Mesh) || mesh === relic || mesh === pedestal, false, camera);
      if (!hit?.hit || !hit.pickedMesh) return null;
      if (npcMeshes.has(hit.pickedMesh as Mesh)) return { kind: "npc" };
      if (hit.pickedMesh === relic || hit.pickedMesh === pedestal) return { kind: "relic" };
      if (hit.pickedMesh === ground && hit.pickedPoint) return { kind: "ground", x: hit.pickedPoint.x, z: hit.pickedPoint.z };
      return null;
    },
    render() {
      const time = (performance.now() - started) / 1000;
      npcRoot.position.y = (npcTalking ? 0.055 : 0.018) * Math.sin(time * (npcTalking ? 3.1 : 1.3));
      npcRoot.rotation.z = (npcTalking ? 0.008 : 0.003) * Math.sin(time * (npcTalking ? 1.8 : 0.8));
      relic.rotation.y = time * 0.75;
      relic.position.y = 1.43 + Math.sin(time * 1.7) * 0.08;
      scene.render();
    },
    resize() {
      engine.resize();
    },
    dispose() {
      disposed = true;
      backdropRequest += 1;
      backdropLoad = null;
      scene.dispose();
      engine.dispose();
    },
  };
}
