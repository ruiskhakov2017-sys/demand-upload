import { createTheme, ThemeOptions } from "@mui/material";

export type ThemeName = "light" | "dark" | "warm" | "ocean" | "forest" | "lavender";

export type ThemeChoice = {
  name: ThemeName;
  label: string;
  preview: [string, string, string];
};

export const themeChoices: ThemeChoice[] = [
  { name: "light", label: "Светлая", preview: ["#f6f8fb", "#ffffff", "#1f6feb"] },
  { name: "dark", label: "Тёмная", preview: ["#111315", "#1b1e21", "#7db4ff"] },
  { name: "warm", label: "Тёплая", preview: ["#f4ede2", "#fffaf3", "#8a4f32"] },
  { name: "ocean", label: "Океан", preview: ["#edf4f7", "#ffffff", "#176b87"] },
  { name: "forest", label: "Лес", preview: ["#eef2ed", "#fbfdfb", "#2f6b48"] },
  { name: "lavender", label: "Лаванда", preview: ["#f2f0f5", "#fdfcff", "#685b86"] }
];

const palettes: Record<ThemeName, ThemeOptions["palette"]> = {
  light: {
    mode: "light",
    primary: { main: "#1f6feb" },
    secondary: { main: "#0f766e" },
    warning: { main: "#b7791f" },
    error: { main: "#c2410c" },
    info: { main: "#2563a8" },
    success: { main: "#2e7d52" },
    background: { default: "#f6f8fb", paper: "#ffffff" },
    text: { primary: "#172033", secondary: "#5f6b7a" },
    divider: "#dfe4ea"
  },
  dark: {
    mode: "dark",
    primary: { main: "#7db4ff" },
    secondary: { main: "#66c9b7" },
    warning: { main: "#f5bf65" },
    error: { main: "#ff847c" },
    info: { main: "#82c7e8" },
    success: { main: "#79c99e" },
    background: { default: "#111315", paper: "#1b1e21" },
    text: { primary: "#f1f4f6", secondary: "#b2bbc3" },
    divider: "#343a40"
  },
  warm: {
    mode: "light",
    primary: { main: "#8a4f32" },
    secondary: { main: "#66724b" },
    warning: { main: "#b96a17" },
    error: { main: "#a43f3f" },
    info: { main: "#65717a" },
    success: { main: "#5f7047" },
    background: { default: "#f4ede2", paper: "#fffaf3" },
    text: { primary: "#342b27", secondary: "#6b5f57" },
    divider: "#d9cbbb"
  },
  ocean: {
    mode: "light",
    primary: { main: "#176b87" },
    secondary: { main: "#3f7d6f" },
    warning: { main: "#b67520" },
    error: { main: "#b44d56" },
    info: { main: "#326e9a" },
    success: { main: "#3d7c67" },
    background: { default: "#edf4f7", paper: "#ffffff" },
    text: { primary: "#18333e", secondary: "#586d75" },
    divider: "#ccdde3"
  },
  forest: {
    mode: "light",
    primary: { main: "#2f6b48" },
    secondary: { main: "#4f6472" },
    warning: { main: "#a56f19" },
    error: { main: "#a7464e" },
    info: { main: "#3f7085" },
    success: { main: "#357552" },
    background: { default: "#eef2ed", paper: "#fbfdfb" },
    text: { primary: "#203029", secondary: "#5d6b63" },
    divider: "#d1ddd3"
  },
  lavender: {
    mode: "light",
    primary: { main: "#685b86" },
    secondary: { main: "#577475" },
    warning: { main: "#a66f23" },
    error: { main: "#a94f68" },
    info: { main: "#5b7394" },
    success: { main: "#55765f" },
    background: { default: "#f2f0f5", paper: "#fdfcff" },
    text: { primary: "#302d39", secondary: "#686272" },
    divider: "#dcd6e2"
  }
};

export function isThemeName(value: string | null): value is ThemeName {
  return themeChoices.some((item) => item.name === value);
}

export function createAppTheme(name: ThemeName) {
  const focusColor = themeChoices.find((item) => item.name === name)?.preview[2] || "#1f6feb";
  return createTheme({
    palette: palettes[name],
    shape: {
      borderRadius: 8
    },
    typography: {
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      h4: {
        fontWeight: 700,
        letterSpacing: 0
      },
      h6: {
        fontWeight: 700,
        letterSpacing: 0
      },
      button: {
        textTransform: "none",
        fontWeight: 600,
        letterSpacing: 0
      }
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          html: {
            backgroundColor: palettes[name]?.background?.default
          },
          body: {
            backgroundColor: palettes[name]?.background?.default,
            transition: "background-color 120ms ease, color 120ms ease"
          },
          "*:focus-visible": {
            outline: `3px solid ${focusColor}66`,
            outlineOffset: 2
          }
        }
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            backgroundImage: "none",
            boxShadow: name === "dark"
              ? "0 1px 2px rgba(0, 0, 0, 0.35)"
              : "0 1px 2px rgba(15, 23, 42, 0.08)"
          }
        }
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none"
          }
        }
      },
      MuiButton: {
        defaultProps: {
          disableElevation: true
        }
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: "none"
          }
        }
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            "&.MuiTableRow-hover:hover": {
              backgroundColor: name === "dark" ? "rgba(125, 180, 255, 0.08)" : "rgba(31, 111, 235, 0.045)"
            }
          }
        }
      },
      MuiInputBase: {
        styleOverrides: {
          root: {
            "&.Mui-disabled": {
              opacity: 0.72
            }
          }
        }
      }
    }
  });
}

export const theme = createAppTheme("light");
