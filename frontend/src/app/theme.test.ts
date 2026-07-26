import { describe, expect, it } from "vitest";

import { createAppTheme, isThemeName, themeChoices } from "./theme";

describe("interface themes", () => {
  it("provides the six supported themes in the expected order", () => {
    expect(themeChoices.map((choice) => choice.name)).toEqual([
      "light",
      "dark",
      "warm",
      "ocean",
      "forest",
      "lavender"
    ]);
    expect(new Set(themeChoices.map((choice) => choice.labelKey)).size).toBe(6);
  });

  it.each(themeChoices)("$name has a complete stable MUI palette", ({ name, preview }) => {
    const theme = createAppTheme(name);

    expect(theme.palette.mode).toBe(name === "dark" ? "dark" : "light");
    expect(theme.palette.background.default).toBe(preview[0]);
    expect(theme.palette.background.paper).toBe(preview[1]);
    expect(theme.palette.primary.main).toBe(preview[2]);
    expect(theme.shape.borderRadius).toBe(8);
  });

  it("rejects unknown persisted theme names", () => {
    expect(isThemeName("forest")).toBe(true);
    expect(isThemeName("unknown")).toBe(false);
    expect(isThemeName(null)).toBe(false);
  });
});
