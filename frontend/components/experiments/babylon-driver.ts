import {
  AssetContainer,
  Color3,
  Color4,
  DirectionalLight,
  DynamicTexture,
  Engine,
  HemisphericLight,
  LoadAssetContainerAsync,
  Mesh,
  MeshBuilder,
  ParticleSystem,
  PointLight,
  Scene,
  ShaderMaterial,
  ShadowGenerator,
  StandardMaterial,
  Texture,
  TransformNode,
  UniversalCamera,
  Vector3,
  VertexData,
} from "@babylonjs/core";
import { registerBuiltInLoaders } from "@babylonjs/loaders/dynamic";
import type { AssetKind, WorldScene } from "../../lib/game-api";
import {
  EYE_HEIGHT,
  terrainHeight,
  type PlayerPose,
  type TrialDriver,
} from "./world";

registerBuiltInLoaders();

export function createBabylonDriver(canvas: HTMLCanvasElement): TrialDriver {
  const engine = new Engine(canvas, true, {
    stencil: false,
    powerPreference: "high-performance",
  });
  engine.setHardwareScalingLevel(
    1 / Math.min(window.devicePixelRatio || 1, 1.25),
  );
  const scene = new Scene(engine);
  scene.fogMode = Scene.FOGMODE_EXP2;
  const camera = new UniversalCamera(
    "player eyes",
    new Vector3(0, EYE_HEIGHT, 8),
    scene,
  );
  camera.fov = (72 * Math.PI) / 180;
  camera.minZ = 0.08;
  camera.maxZ = 210;
  camera.inputs.clear();
  scene.activeCamera = camera;
  const fill = new HemisphericLight("sky ambient", new Vector3(0, 1, 0), scene);
  const sun = new DirectionalLight(
    "sunlight",
    new Vector3(-0.45, -0.8, 0.3),
    scene,
  );
  sun.position = new Vector3(25, 40, -20);
  const shadows = new ShadowGenerator(1024, sun);
  shadows.usePercentageCloserFiltering = true;
  shadows.filteringQuality = ShadowGenerator.QUALITY_LOW;
  sun.shadowMinZ = 1;
  sun.shadowMaxZ = 95;
  const accent = new PointLight("landmark light", new Vector3(0, 3, -6), scene);
  accent.range = 16;
  let world: WorldScene | null = null;
  let terrain: Mesh | null = null;
  let landmark: TransformNode | null = null;
  let particles: ParticleSystem | null = null;
  let waterSurface: Mesh | null = null;
  let waterShader: ShaderMaterial | null = null;
  let fireShader: ShaderMaterial | null = null;
  let lavaShader: ShaderMaterial | null = null;
  let flameRoot: TransformNode | null = null;
  let disposed = false;
  let sceneGeneration = 0;
  const modelGroups = new Map<AssetKind, TransformNode>();
  const modelVersions = new Map<AssetKind, number>();
  const modelUrls = new Map<AssetKind, string>();
  const containers = new Map<string, Promise<AssetContainer>>();
  const createdMaterials: StandardMaterial[] = [];
  const portraits = new Map<string, Texture>();
  const floorTexture = new Texture("/game/forest-floor.png", scene);
  floorTexture.uScale = floorTexture.vScale = 22;
  const stoneTexture = new Texture("/game/forest-stone.png", scene);
  stoneTexture.uScale = stoneTexture.vScale = 18;
  const sandTexture = new Texture("/game/materials/sand-v1.png", scene);
  const basaltTexture = new Texture("/game/materials/basalt-v1.png", scene);
  for (const texture of [sandTexture, basaltTexture])
    texture.uScale = texture.vScale = 24;

  const sky = MeshBuilder.CreateSphere(
    "continuous sky dome",
    { diameter: 360, segments: 32, sideOrientation: Mesh.BACKSIDE },
    scene,
  );
  sky.isPickable = false;
  sky.infiniteDistance = true;
  const skyMaterial = new ShaderMaterial(
    "atmosphere",
    scene,
    {
      vertexSource: `precision highp float; attribute vec3 position; uniform mat4 worldViewProjection; varying vec3 p; void main(){p=position;gl_Position=worldViewProjection*vec4(position,1.);}`,
      fragmentSource: `precision highp float; varying vec3 p; uniform vec3 zenith; uniform vec3 horizon; uniform float clock; uniform float night; void main(){vec3 d=normalize(p);float h=pow(max(d.y,0.),.45);vec3 c=mix(horizon,zenith,h);float s=pow(max(dot(d,normalize(vec3(-.4,.4,-.7))),0.),160.);c+=vec3(1.,.8,.46)*s*(1.-night*.8);float cloud=sin(d.x*17.+clock*.025)*sin(d.z*22.+d.y*13.)*.5+.5; c=mix(c,c+vec3(.08),smoothstep(.65,.95,cloud)*(1.-h)*.3);float stars=step(.997,fract(sin(dot(floor(d.xz*750.),vec2(12.9898,78.233)))*43758.5453)); c+=vec3(stars*night*h*.6); gl_FragColor=vec4(c,1.);}`,
    },
    {
      attributes: ["position"],
      uniforms: ["worldViewProjection", "zenith", "horizon", "clock", "night"],
    },
  );
  sky.material = skyMaterial;
  skyMaterial.backFaceCulling = false;
  skyMaterial.disableDepthWrite = true;

  function mat(name: string, color: string, emissive?: string) {
    const m = new StandardMaterial(name, scene);
    m.diffuseColor = Color3.FromHexString(color);
    m.specularColor = new Color3(0.025, 0.025, 0.025);
    if (emissive) m.emissiveColor = Color3.FromHexString(emissive);
    createdMaterials.push(m);
    return m;
  }
  function disposeGroup(group: TransformNode) {
    for (const mesh of group.getChildMeshes()) shadows.removeShadowCaster(mesh);
    group.dispose(false);
  }
  const particleTexture = new DynamicTexture("soft particle", 32, scene, false);
  const ctx = particleTexture.getContext();
  const glow = ctx.createRadialGradient(16, 16, 0, 16, 16, 15);
  glow.addColorStop(0, "rgba(255,255,255,1)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 32, 32);
  particleTexture.update();

  function buildTerrain(current: WorldScene) {
    terrain?.dispose();
    const desert = current.scene_id === "liuchen_valley";
    const lava = current.scene_id === "lieyi_plains";
    terrain = MeshBuilder.CreateGround(
      "continuous walkable terrain",
      { width: 180, height: 180, subdivisions: 150, updatable: true },
      scene,
    );
    const positions = terrain.getVerticesData("position")!;
    const indices = terrain.getIndices()!;
    const colours: number[] = [];
    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i],
        z = positions[i + 2];
      positions[i + 1] = terrainHeight(x, z, current);
      const path = Math.exp(-Math.pow(x / (2.3 + Math.sin(z * 0.08) * 0.4), 2));
      const variation =
        0.88 + Math.sin(x * 1.9 + z * 2.7) * Math.sin(z * 1.1) * 0.07;
      const base = desert
        ? new Color3(0.76, 0.59, 0.36)
        : lava
          ? new Color3(0.24, 0.19, 0.19)
          : new Color3(0.35, 0.47, 0.25);
      const trail = desert
        ? new Color3(0.85, 0.68, 0.44)
        : lava
          ? new Color3(0.37, 0.28, 0.25)
          : new Color3(0.67, 0.59, 0.4);
      const c = Color3.Lerp(base, trail, path * 0.8).scale(variation);
      colours.push(c.r, c.g, c.b, 1);
    }
    const normals: number[] = [];
    VertexData.ComputeNormals(positions, indices, normals);
    terrain.updateVerticesData("position", positions);
    terrain.updateVerticesData("normal", normals);
    terrain.setVerticesData("color", colours);
    const groundMaterial = mat("terrain surface", "#ffffff");
    groundMaterial.diffuseTexture = desert
      ? sandTexture
      : lava
        ? basaltTexture
        : floorTexture;
    terrain.material = groundMaterial;
    terrain.receiveShadows = true;
  }

  function buildLandmark(current: WorldScene) {
    fireShader?.dispose();
    fireShader = null;
    lavaShader?.dispose();
    lavaShader = null;
    flameRoot = null;
    waterShader?.dispose();
    waterShader = null;
    waterSurface = null;
    if (landmark) disposeGroup(landmark);
    particles?.dispose(false);
    particles = null;
    landmark = new TransformNode("interaction landmark", scene);
    const x = current.interaction_x,
      z = current.interaction_z,
      y = terrainHeight(x, z, current);
    landmark.position.set(x, y, z);
    const stone = mat("landmark stone", current.fire ? "#372622" : "#7f8977");
    stone.diffuseTexture = stoneTexture;
    const dais = MeshBuilder.CreateCylinder(
      "landmark paving",
      { diameter: 8, height: 0.12, tessellation: 64 },
      scene,
    );
    dais.parent = landmark;
    dais.position.y = 0.015;
    dais.material = stone;
    dais.receiveShadows = true;
    const ringMaterial = mat(
      "etched glowing circle",
      current.fire ? "#dc6d1f" : "#77b3a0",
      current.fire ? "#6b2609" : "#19493b",
    );
    const ring = MeshBuilder.CreateTorus(
      "landmark etched ring",
      { diameter: 6.8, thickness: 0.025, tessellation: 64 },
      scene,
    );
    ring.parent = landmark;
    ring.position.y = 0.09;
    ring.material = ringMaterial;
    if (current.npc_id) {
      const portrait = MeshBuilder.CreatePlane(
        "npc",
        { width: 1.26, height: 2.55 },
        scene,
      );
      portrait.parent = landmark;
      portrait.position.y = 1.35;
      portrait.billboardMode = Mesh.BILLBOARDMODE_Y;
      const portraitMat = mat("npc artwork", "#ffffff");
      if (!portraits.has(current.npc_id))
        portraits.set(
          current.npc_id,
          new Texture(`/game/${current.npc_id}-cutout.png`, scene),
        );
      portraitMat.diffuseTexture = portraits.get(current.npc_id)!;
      portraitMat.diffuseTexture.hasAlpha = true;
      portraitMat.useAlphaFromDiffuseTexture = true;
      portraitMat.backFaceCulling = false;
      portraitMat.emissiveColor = new Color3(0.12, 0.12, 0.1);
      portrait.material = portraitMat;
      shadows.addShadowCaster(portrait);
    } else if (current.water) {
      const water = MeshBuilder.CreateDisc(
        "spring surface",
        { radius: 2.15, tessellation: 80 },
        scene,
      );
      water.parent = landmark;
      water.rotation.x = Math.PI / 2;
      water.position.y = 0.13;
      waterShader = new ShaderMaterial(
        "rippling spring",
        scene,
        {
          vertexSource: `precision highp float; attribute vec3 position;attribute vec2 uv;uniform mat4 worldViewProjection;varying vec2 v;void main(){v=uv;gl_Position=worldViewProjection*vec4(position,1.);}`,
          fragmentSource: `precision highp float;varying vec2 v;uniform float clock;void main(){vec2 p=v-.5;float r=length(p);float wave=sin(r*90.-clock*2.+sin(p.x*21.+clock)*.4)*.5+.5;float caustic=pow(wave,10.)*.18;vec3 c=mix(vec3(.025,.18,.21),vec3(.08,.43,.44),1.-r);c+=vec3(.25,.5,.42)*caustic;gl_FragColor=vec4(c,1.);}`,
        },
        {
          attributes: ["position", "uv"],
          uniforms: ["worldViewProjection", "clock"],
        },
      );
      waterShader.backFaceCulling = false;
      water.material = waterShader;
      waterSurface = water;
    }
    accent.position.set(x, y + 2, z);
    accent.diffuse = Color3.FromHexString(current.fire ? "#ff8028" : "#86e2cc");
    accent.intensity = current.fire ? 2.5 : 0.65;
    if (current.fire) {
      fireShader = new ShaderMaterial(
        "living sacred fire",
        scene,
        {
          vertexSource: `precision highp float;attribute vec3 position;attribute vec2 uv;uniform mat4 worldViewProjection;varying vec2 v;void main(){v=uv;gl_Position=worldViewProjection*vec4(position,1.);}`,
          fragmentSource: `precision highp float;varying vec2 v;uniform float clock;float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}void main(){float y=v.y;float n=noise(vec2(v.x*7.,y*9.-clock*2.4))*.65+noise(vec2(v.x*17.,y*19.-clock*4.))*.35;float x=(v.x-.5)*2.+sin(y*11.-clock*2.)*.1*y;float width=(1.-y)*.72+n*.22;float edge=1.-smoothstep(width-.22,width,abs(x));float a=edge*smoothstep(0.,.07,y)*(1.-smoothstep(.62+n*.25,1.,y));if(a<.02)discard;float core=clamp(1.-abs(x)*1.5-y*.65,0.,1.);vec3 c=mix(vec3(.72,.10,.008),vec3(1.,.72,.16),core);gl_FragColor=vec4(c,a*.7);}`,
        },
        {
          attributes: ["position", "uv"],
          uniforms: ["worldViewProjection", "clock"],
          needAlphaBlending: true,
        },
      );
      fireShader.backFaceCulling = false;
      fireShader.disableDepthWrite = true;
      fireShader.alphaMode = Engine.ALPHA_ADD;
      flameRoot = new TransformNode("fire volume", scene);
      flameRoot.parent = landmark;
      for (let i = 0; i < 3; i++) {
        const flame = MeshBuilder.CreatePlane(
          `flame sheet ${i}`,
          { width: 3.2, height: 5.8 },
          scene,
        );
        flame.parent = flameRoot;
        flame.position.y = 2.9;
        flame.rotation.y = (i * Math.PI) / 3;
        flame.material = fireShader;
      }
      lavaShader = new ShaderMaterial(
        "flowing molten rock",
        scene,
        {
          vertexSource: `precision highp float;attribute vec3 position;attribute vec2 uv;uniform mat4 worldViewProjection;varying vec2 v;varying float depth;void main(){v=uv;gl_Position=worldViewProjection*vec4(position,1.);depth=gl_Position.w;}`,
          fragmentSource: `precision highp float;varying vec2 v;varying float depth;uniform float clock;uniform vec3 fog;void main(){float n=sin(v.x*140.-clock*.8+sin(v.y*17.))*sin(v.y*24.+clock*.5);float crust=smoothstep(-.3,.8,n);vec3 c=mix(vec3(.85,.16,.015),vec3(.16,.035,.018),crust);gl_FragColor=vec4(mix(c,fog,clamp(depth*.009,0.,.75)),1.);}`,
        },
        {
          attributes: ["position", "uv"],
          uniforms: ["worldViewProjection", "clock", "fog"],
        },
      );
      lavaShader.backFaceCulling = false;
      lavaShader.setColor3("fog", scene.fogColor);
      for (const side of [-1, 1]) {
        const edges = [[], []] as Vector3[][];
        for (let i = 0; i <= 70; i++) {
          const pz = 22 - i * 1.05;
          const center = side * (9 + Math.sin(pz * 0.16) * 2.5);
          for (let edge = 0; edge < 2; edge++) {
            const px = center + (edge - 0.5) * 1.25;
            edges[edge].push(
              new Vector3(
                px - x,
                terrainHeight(px, pz, current) - y + 0.055,
                pz - z,
              ),
            );
          }
        }
        const channel = MeshBuilder.CreateRibbon(
          `lava stream ${side}`,
          { pathArray: edges, sideOrientation: Mesh.DOUBLESIDE },
          scene,
        );
        channel.parent = landmark;
        channel.material = lavaShader;
      }
    }
    if (current.fire || current.config.weather !== "clear") {
      const rain = current.config.weather === "rain" && !current.fire;
      particles = new ParticleSystem(
        "weather and fire",
        rain ? 900 : 450,
        scene,
      );
      particles.particleTexture = particleTexture;
      particles.emitter = new Vector3(
        current.fire ? x : 0,
        current.fire ? y + 0.5 : 5,
        current.fire ? z : 0,
      );
      particles.minEmitBox = new Vector3(
        current.fire ? -1.2 : -35,
        0,
        current.fire ? -1.2 : -35,
      );
      particles.maxEmitBox = new Vector3(
        current.fire ? 1.2 : 35,
        current.fire ? 0.3 : 9,
        current.fire ? 1.2 : 35,
      );
      particles.color1 = new Color4(
        current.fire ? 1 : 0.72,
        current.fire ? 0.4 : 0.82,
        current.fire ? 0.06 : 0.83,
        current.fire ? 0.9 : 0.3,
      );
      particles.color2 = new Color4(
        1,
        current.fire ? 0.7 : 0.87,
        current.fire ? 0.15 : 0.75,
        0.15,
      );
      particles.colorDead = new Color4(0.1, 0.1, 0.1, 0);
      particles.minSize = rain ? 0.025 : current.fire ? 0.02 : 0.2;
      particles.maxSize = current.fire ? 0.06 : rain ? 0.08 : 0.8;
      particles.minLifeTime = current.fire ? 0.6 : rain ? 1 : 4;
      particles.maxLifeTime = current.fire ? 2 : rain ? 2 : 9;
      particles.emitRate = current.fire ? 24 : rain ? 200 : 45;
      particles.direction1 = new Vector3(
        -0.3,
        rain ? -12 : current.fire ? 2 : -0.08,
        -0.2,
      );
      particles.direction2 = new Vector3(
        0.5,
        rain ? -10 : current.fire ? 5 : 0.04,
        0.3,
      );
      particles.gravity = new Vector3(
        0,
        current.fire ? 0.25 : rain ? -5 : 0,
        0,
      );
      particles.start();
    }
  }

  async function setAsset(kind: AssetKind, url: string) {
    if (!world || disposed) return;
    const token = (modelVersions.get(kind) || 0) + 1;
    modelVersions.set(kind, token);
    const generation = sceneGeneration;
    const current = world;
    if (!containers.has(url))
      containers.set(
        url,
        LoadAssetContainerAsync(url, scene, { pluginExtension: ".glb" }).catch(
          (error) => {
            containers.delete(url);
            throw error;
          },
        ),
      );
    const container = await containers.get(url)!;
    if (
      disposed ||
      generation !== sceneGeneration ||
      token !== modelVersions.get(kind)
    )
      return;
    const group = new TransformNode(`generated ${kind} props`, scene);
    for (const object of current.objects.filter((o) => o.kind === kind)) {
      const pivot = new TransformNode(object.object_id, scene);
      pivot.parent = group;
      const instance = container.instantiateModelsToScene(
        (name) => `${object.object_id}:${name}`,
        false,
        { doNotInstantiate: false },
      );
      for (const root of instance.rootNodes) root.parent = pivot;
      const bounds = pivot.getHierarchyBoundingVectors(true);
      const size = bounds.max.subtract(bounds.min);
      const scale =
        object.scale / Math.max(size.y, kind === "altar" ? size.x : 0, 0.001);
      const vertical =
        kind === "altar" && current.water && object.x === 0 && object.z === -6
          ? 0.42
          : 1;
      const center = bounds.min.add(size.scale(0.5));
      if (
        kind === "altar" &&
        object.x === current.interaction_x &&
        object.z === current.interaction_z
      ) {
        const top = size.y * scale * vertical;
        if (waterSurface) waterSurface.position.y = top * 0.99;
        if (current.fire && flameRoot) flameRoot.position.y = top + 0.05;
        if (current.fire && particles)
          particles.emitter = new Vector3(
            object.x,
            terrainHeight(object.x, object.z, current) + top + 0.15,
            object.z,
          );
      }
      const normalizer = new TransformNode(
        `${object.object_id}:normalizer`,
        scene,
      );
      normalizer.parent = pivot;
      for (const root of instance.rootNodes) root.parent = normalizer;
      normalizer.position.set(-center.x, -bounds.min.y, -center.z);
      pivot.scaling.set(scale, scale * vertical, scale);
      pivot.rotation.y = object.yaw;
      pivot.position.set(
        object.x,
        terrainHeight(object.x, object.z, current) - 0.03,
        object.z,
      );
      for (const mesh of pivot.getChildMeshes()) {
        mesh.receiveShadows = true;
        mesh.isPickable = false;
        shadows.addShadowCaster(mesh);
      }
    }
    const previousGroup = modelGroups.get(kind);
    if (previousGroup) disposeGroup(previousGroup);
    modelGroups.set(kind, group);
    modelUrls.set(kind, url);
    if (containers.size > 9) {
      for (const [key, promise] of containers) {
        if (![...modelUrls.values()].includes(key)) {
          containers.delete(key);
          void promise.then((c) => c.dispose()).catch(() => {});
          if (containers.size <= 6) break;
        }
      }
    }
  }

  return {
    pickGround(clientX, clientY) {
      if (!world) return null;
      const bounds = canvas.getBoundingClientRect();
      const hit = scene.pick(
        clientX - bounds.left,
        clientY - bounds.top,
        (mesh) =>
          mesh === terrain ||
          mesh.name === "npc" ||
          mesh.name === "landmark paving",
        false,
        camera,
      );
      if (!hit?.hit || !hit.pickedPoint) return null;
      if (
        hit.pickedMesh?.name === "npc" ||
        hit.pickedMesh?.name === "landmark paving"
      )
        return {
          x: world.interaction_x,
          z: world.interaction_z,
          interaction: true,
        };
      return { x: hit.pickedPoint.x, z: hit.pickedPoint.z };
    },
    async setWorld(next) {
      if (disposed) return;
      world = next;
      sceneGeneration++;
      for (const group of modelGroups.values()) disposeGroup(group);
      modelGroups.clear();
      for (const material of createdMaterials) material.dispose(false, false);
      createdMaterials.length = 0;
      const night = next.config.time_of_day === "night";
      const dusk = next.config.time_of_day === "dusk";
      const desert = next.scene_id === "liuchen_valley";
      const fire = next.scene_id === "lieyi_plains";
      const horizon = Color3.FromHexString(
        night
          ? "#142c3e"
          : desert
            ? "#bba37c"
            : fire
              ? "#bd7350"
              : dusk
                ? "#c7b5a0"
                : "#b6cbb9",
      );
      const zenith = Color3.FromHexString(
        night ? "#050d22" : fire ? "#4d353e" : dusk ? "#4b6279" : "#6c9cb9",
      );
      scene.clearColor = new Color4(horizon.r, horizon.g, horizon.b, 1);
      scene.fogColor = horizon;
      scene.fogDensity =
        next.config.weather === "mist"
          ? 0.023
          : next.config.weather === "dust"
            ? 0.019
            : next.config.weather === "rain"
              ? 0.012
              : 0.005;
      skyMaterial.setColor3("zenith", zenith);
      skyMaterial.setColor3("horizon", horizon);
      skyMaterial.setFloat("night", night ? 1 : 0);
      fill.diffuse = Color3.FromHexString(night ? "#7095c2" : "#d4e5d6");
      fill.groundColor = Color3.FromHexString(desert ? "#76553b" : "#344229");
      fill.intensity = night ? 0.5 : 0.85;
      sun.diffuse = Color3.FromHexString(dusk || fire ? "#ffd19b" : "#fff4db");
      sun.intensity = night ? 0.16 : dusk ? 0.9 : 1.15;
      buildTerrain(next);
      buildLandmark(next);
      await Promise.all(
        (["tree", "runestone", "altar"] as AssetKind[]).map((kind) =>
          setAsset(kind, `/game/models/${kind}-v1.glb`),
        ),
      );
    },
    setAsset,
    setView(pose: PlayerPose, eyeBob: number) {
      if (!world) return;
      const y = terrainHeight(pose.x, pose.z, world) + EYE_HEIGHT + eyeBob;
      camera.position.set(pose.x, y, pose.z);
      camera.setTarget(
        new Vector3(
          pose.x + Math.sin(pose.yaw) * Math.cos(pose.pitch),
          y + Math.sin(pose.pitch),
          pose.z - Math.cos(pose.yaw) * Math.cos(pose.pitch),
        ),
      );
    },
    move(x, z, dx, dz) {
      const blocked = (px: number, pz: number) =>
        !world ||
        Math.abs(px) > 64 ||
        Math.abs(pz) > 64 ||
        (!!world.npc_id &&
          Math.hypot(px - world.interaction_x, pz - world.interaction_z) <
            0.8) ||
        Math.abs(terrainHeight(px, pz, world) - terrainHeight(x, z, world)) >
          0.45 ||
        world.objects.some(
          (o) =>
            Math.hypot(px - o.x, pz - o.z) <
            (o.kind === "tree"
              ? 0.7
              : o.kind === "altar"
                ? o.scale * 0.43
                : 1.05),
        );
      const nx = Math.max(-64, Math.min(64, x + dx)),
        nz = Math.max(-64, Math.min(64, z + dz));
      return { x: blocked(nx, z) ? x : nx, z: blocked(x, nz) ? z : nz };
    },
    render() {
      skyMaterial.setFloat("clock", performance.now() / 1000);
      waterShader?.setFloat("clock", performance.now() / 1000);
      fireShader?.setFloat("clock", performance.now() / 1000);
      lavaShader?.setFloat("clock", performance.now() / 1000);
      scene.render();
    },
    resize() {
      engine.resize();
    },
    dispose() {
      disposed = true;
      sceneGeneration++;
      particles?.dispose();
      for (const pending of containers.values())
        void pending.then((c) => c.dispose()).catch(() => {});
      scene.dispose();
      engine.dispose();
    },
  };
}
