type Dimensions = { x: number; y: number; z: number };

/** A model may never exceed the placement footprint promised by the backend. */
export function fitAsset(size: Dimensions, nominalSize: number) {
  const axes = [size.x, size.y, size.z];
  if (!Number.isFinite(nominalSize) || nominalSize <= 0 ||
    axes.some(value => !Number.isFinite(value) || value <= 1e-5)) {
    throw new Error("生成模型的幾何尺寸無效，保留原場景。");
  }
  const longest = Math.max(...axes), shortest = Math.min(...axes);
  if (shortest / longest < .015) throw new Error("生成模型比例過薄，保留原場景。");
  const scale = nominalSize / longest;
  return { scale, width: size.x * scale, height: size.y * scale, depth: size.z * scale };
}
