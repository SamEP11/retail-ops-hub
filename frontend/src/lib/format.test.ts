import { describe, expect, it } from "vitest";

import { formatMoney } from "./format";

describe("formatMoney", () => {
  it("formatea pesos colombianos sin decimales", () => {
    // Intl usa un espacio duro entre "$" y el número
    expect(formatMoney("129900.00").replace(/\s/g, " ")).toBe("$ 129.900");
  });

  it.each([null, undefined, "", "abc"])("muestra guion si no hay precio (%s)", (v) => {
    expect(formatMoney(v as string)).toBe("—");
  });
});
