import { describe, expect, it } from "vitest";
import { parseAmount, peso, toCentavos, toDecimalString } from "./money";

describe("money", () => {
  it("converts API strings to centavos and back without float error", () => {
    expect(toCentavos("1250.50")).toBe(125050);
    expect(toCentavos("0.1")).toBe(10);
    expect(toCentavos("-3.05")).toBe(-305);
    expect(toDecimalString(125050)).toBe("1250.50");
    expect(toDecimalString(5)).toBe("0.05");
    expect(toDecimalString(-305)).toBe("-3.05");
    // 0.1 + 0.2 style traps never happen: sums are integer centavos.
    expect(toDecimalString(toCentavos("0.10") + toCentavos("0.20"))).toBe("0.30");
  });

  it("rejects junk", () => {
    expect(() => toCentavos("12.345")).toThrow();
    expect(() => toCentavos("abc")).toThrow();
  });

  it.each([
    ["150", 15000],
    ["1,250.5", 125050],
    ["₱99", 9900],
    ["2k", 200000],
    ["1.5k", 150000],
    ["25K", 2500000],
    ["0", null],
    ["12.345", null],
    ["kape", null],
    ["", null],
  ])("parses what people type: %s", (text, expected) => {
    expect(parseAmount(text)).toBe(expected);
  });

  it("formats pesos", () => {
    expect(peso("1250.5")).toBe("₱1,250.50");
    expect(peso(123456, { round: true })).toBe("₱1,235");
  });
});
