export const seededRandom = (seed: number): number => {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
};

export const range = (length: number): number[] =>
  Array.from({length}, (_, index) => index);
