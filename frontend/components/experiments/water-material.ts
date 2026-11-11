import { Color3, DynamicTexture, FresnelParameters, Mesh, MirrorTexture, Plane, Scene, StandardMaterial } from "@babylonjs/core";

/** Shared by the council pond and spring so both belong to the same forest. */
export function createReflectiveWater(scene: Scene, surface: Mesh) {
  const material = new StandardMaterial(`${surface.name} water`, scene);
  material.diffuseColor = Color3.FromHexString("#0b302e");
  material.emissiveColor = Color3.FromHexString("#010505");
  material.alpha = .98;
  material.backFaceCulling = false;
  material.specularColor = new Color3(.2, .3, .22);
  material.specularPower = 128;
  const reflection = new MirrorTexture(`${surface.name} reflection`, 512, scene, true);
  reflection.level = .35;
  reflection.refreshRate = 2;
  material.reflectionTexture = reflection;
  const fresnel = new FresnelParameters();
  fresnel.bias = .2;
  fresnel.power = 3;
  fresnel.leftColor = Color3.White();
  fresnel.rightColor = new Color3(.16, .22, .20);
  material.reflectionFresnelParameters = fresnel;
  const ripples = new DynamicTexture(`${surface.name} soft normal ripples`, 128, scene, false);
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
  material.bumpTexture = ripples;
  surface.material = material;
  return {
    update(time: number) {
      ripples.uOffset = time * .008;
      ripples.vOffset = time * .005;
      reflection.mirrorPlane = new Plane(0, -1, 0, surface.getAbsolutePosition().y);
      reflection.renderList = scene.meshes.filter(mesh => mesh !== surface &&
        !mesh.name.includes("sky") && mesh.name !== "distant painted forest" && !mesh.name.startsWith("flame"));
    },
    dispose() {
      material.dispose(false, false);
      reflection.dispose();
      ripples.dispose();
    },
  };
}
