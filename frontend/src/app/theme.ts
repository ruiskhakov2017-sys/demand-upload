import { alpha, createTheme, ThemeOptions } from "@mui/material";

export type ThemeName = "light" | "dark" | "warm" | "ocean" | "forest" | "lavender";

export type ThemeChoice = {
  name: ThemeName;
  labelKey: string;
  preview: [string, string, string];
};

export const themeChoices: ThemeChoice[] = [
  { name: "light", labelKey: "ui.8080010c5e", preview: ["#f4f7fb", "#ffffff", "#244bb9"] },
  { name: "dark", labelKey: "ui.bd16b23470", preview: ["#111315", "#1b1e21", "#7db4ff"] },
  { name: "warm", labelKey: "ui.40c9e14f62", preview: ["#f4ede2", "#fffaf3", "#8a4f32"] },
  { name: "ocean", labelKey: "ui.fa58852bac", preview: ["#edf4f7", "#ffffff", "#176b87"] },
  { name: "forest", labelKey: "ui.b6cdac5a60", preview: ["#eef2ed", "#fbfdfb", "#2f6b48"] },
  { name: "lavender", labelKey: "ui.f03361f0b4", preview: ["#f2f0f5", "#fdfcff", "#685b86"] }
];

const palettes: Record<ThemeName, ThemeOptions["palette"]> = {
  light: {
    mode: "light",
    primary: { main: "#244bb9" },
    secondary: { main: "#516788" },
    warning: { main: "#b7791f" },
    error: { main: "#c2410c" },
    info: { main: "#2563a8" },
    success: { main: "#2e7d52" },
    background: { default: "#f4f7fb", paper: "#ffffff" },
    text: { primary: "#152640", secondary: "#526177" },
    divider: "#d9e1ec"
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
  const focusColor = themeChoices.find((item) => item.name === name)?.preview[2] || "#244bb9";
  return createTheme({
    palette: palettes[name],
    shape: {
      borderRadius: 8
    },
    typography: {
      fontFamily:
        '"Golos Text", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      fontSize: 14,
      h4: {
        fontSize: "1.75rem",
        lineHeight: 1.2,
        fontWeight: 600,
        letterSpacing: "-0.035em"
      },
      h5: {
        fontSize: "1.35rem",
        lineHeight: 1.3,
        fontWeight: 600,
        letterSpacing: "-0.025em"
      },
      h6: {
        fontSize: "1.125rem",
        fontWeight: 600,
        letterSpacing: "-0.02em"
      },
      body1: {
        fontSize: "0.875rem",
        lineHeight: 1.6
      },
      body2: {
        fontSize: "0.8125rem",
        lineHeight: 1.55
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
            fontVariantNumeric: "tabular-nums",
            WebkitFontSmoothing: "antialiased",
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
              : "0 2px 7px rgba(21, 38, 64, 0.04)"
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
        },
        styleOverrides: {
          root: {
            borderRadius: 6,
            minHeight: 36,
            paddingInline: 14
          },
          sizeSmall: {
            minHeight: 32,
            fontSize: "0.75rem"
          },
          outlined: ({ theme }) => ({
            borderColor: theme.palette.divider,
            "&:hover": {
              borderColor: theme.palette.primary.main,
              backgroundColor: alpha(theme.palette.primary.main, 0.04)
            }
          })
        }
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            boxShadow: "none"
          }
        }
      },
      MuiDrawer: {
        styleOverrides: {
          paper: ({ theme }) => ({
            backgroundColor: theme.palette.background.paper,
            borderColor: theme.palette.divider
          })
        }
      },
      MuiListItemButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderRadius: 6,
            color: theme.palette.text.secondary,
            "& .MuiListItemIcon-root": { color: "inherit" },
            "& .MuiListItemText-primary": { fontSize: "0.8125rem" },
            "&.Mui-selected": {
              color: theme.palette.primary.main,
              backgroundColor: alpha(theme.palette.primary.main, 0.08),
              "& .MuiListItemText-primary": { fontWeight: 600 },
              "&:hover": { backgroundColor: alpha(theme.palette.primary.main, 0.12) }
            }
          })
        }
      },
      MuiListSubheader: {
        styleOverrides: {
          root: ({ theme }) => ({
            color: theme.palette.text.secondary,
            letterSpacing: "0.04em"
          })
        }
      },
      MuiTabs: {
        styleOverrides: {
          root: { minHeight: 44 },
          indicator: { height: 3, borderRadius: "3px 3px 0 0" }
        }
      },
      MuiTab: {
        styleOverrides: {
          root: {
            minHeight: 44,
            minWidth: 0,
            padding: "10px 18px",
            textTransform: "none",
            fontSize: "0.8125rem",
            fontWeight: 500
          }
        }
      },
      MuiTableCell: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderBottom: `1px solid ${theme.palette.divider}`,
            fontSize: "0.8125rem",
            lineHeight: 1.45
          }),
          head: ({ theme }) => ({
            color: theme.palette.text.secondary,
            backgroundColor: theme.palette.background.default,
            fontSize: "0.75rem",
            fontWeight: 600
          }),
          sizeSmall: {
            padding: "10px 12px",
            "&.MuiTableCell-paddingCheckbox": { padding: "0 0 0 4px" }
          }
        }
      },
      MuiTableRow: {
        styleOverrides: {
          root: ({ theme }) => ({
            "&.MuiTableRow-hover:hover": {
              backgroundColor: alpha(theme.palette.primary.main, 0.045)
            },
            "&.Mui-selected": {
              backgroundColor: alpha(theme.palette.primary.main, 0.075)
            }
          })
        }
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 5, fontWeight: 500, fontSize: "0.75rem" },
          sizeSmall: { height: 23 }
        }
      },
      MuiToggleButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderColor: theme.palette.divider,
            textTransform: "none",
            fontSize: "0.75rem",
            fontWeight: 500,
            "&.Mui-selected": {
              color: theme.palette.primary.main,
              backgroundColor: alpha(theme.palette.primary.main, 0.08)
            }
          })
        }
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: { borderRadius: 6 },
          notchedOutline: ({ theme }) => ({ borderColor: theme.palette.divider })
        }
      },
      MuiAlert: {
        styleOverrides: {
          root: { fontSize: "0.8125rem", borderRadius: 6 }
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
