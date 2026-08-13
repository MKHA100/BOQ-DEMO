export type ScaleUnit = "mm" | "cm" | "m" | "ft_in";

export function toMillimetres(value: number, unit: ScaleUnit, feet = 0, inches = 0): number {
  if (unit === "ft_in") return feet * 304.8 + inches * 25.4;
  if (unit === "cm") return value * 10;
  if (unit === "m") return value * 1000;
  return value;
}

export function displayMillimetres(value: number, unit: ScaleUnit): number {
  if (unit === "ft_in") return value / 25.4;
  if (unit === "cm") return value / 10;
  if (unit === "m") return value / 1000;
  return value;
}

export function millimetresToFeetAndInches(value: number): { feet: number; inches: number } {
  const totalInches = Math.max(0, value) / 25.4;
  let feet = Math.floor(totalInches / 12);
  let inches = Math.round((totalInches - feet * 12) * 1000) / 1000;
  if (inches >= 12) {
    feet += 1;
    inches = 0;
  }
  return { feet, inches };
}
