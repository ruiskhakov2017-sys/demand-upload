import { describe, expect, it } from "vitest";

import { ru } from "../i18n/ru";
import { optionalMetric } from "./OperationsPages";

describe("operations data presentation", () => {
  it("keeps a real zero distinct from missing Google metrics", () => {
    expect(optionalMetric(null, 0)).toBe(ru["operations.noData"]);
    expect(optionalMetric(undefined, 2)).toBe(ru["operations.noData"]);
    expect(optionalMetric(0, 0)).not.toBe(ru["operations.noData"]);
    expect(optionalMetric(0, 2, 1_000_000)).not.toBe(ru["operations.noData"]);
  });
});
