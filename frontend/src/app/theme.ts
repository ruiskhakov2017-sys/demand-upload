import { createTheme } from "@mui/material";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1f6feb"
    },
    secondary: {
      main: "#0f766e"
    },
    warning: {
      main: "#b7791f"
    },
    error: {
      main: "#c2410c"
    },
    background: {
      default: "#f6f8fb",
      paper: "#ffffff"
    }
  },
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
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)"
        }
      }
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true
      }
    }
  }
});

