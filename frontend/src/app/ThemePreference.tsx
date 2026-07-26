import { CssBaseline, ThemeProvider } from "@mui/material";
import { createContext, ReactNode, useContext, useMemo, useState } from "react";

import { createAppTheme, isThemeName, ThemeName } from "./theme";

const STORAGE_KEY = "dgu.theme";

type ThemePreferenceValue = {
  themeName: ThemeName;
  setThemeName: (name: ThemeName) => void;
};

const ThemePreferenceContext = createContext<ThemePreferenceValue | null>(null);

export function ThemePreferenceProvider({ children }: { children: ReactNode }) {
  const [themeName, setThemeNameState] = useState<ThemeName>(readInitialTheme);
  const theme = useMemo(() => createAppTheme(themeName), [themeName]);
  const value = useMemo<ThemePreferenceValue>(
    () => ({
      themeName,
      setThemeName: (name) => {
        localStorage.setItem(STORAGE_KEY, name);
        document.documentElement.dataset.theme = name;
        setThemeNameState(name);
      }
    }),
    [themeName]
  );
  return (
    <ThemePreferenceContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemePreferenceContext.Provider>
  );
}

export function useThemePreference() {
  const value = useContext(ThemePreferenceContext);
  if (!value) throw new Error("ThemePreferenceProvider is missing");
  return value;
}

function readInitialTheme(): ThemeName {
  const stored = localStorage.getItem(STORAGE_KEY);
  const themeName = isThemeName(stored) ? stored : "light";
  document.documentElement.dataset.theme = themeName;
  return themeName;
}
