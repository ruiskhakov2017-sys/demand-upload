import { alpha, createTheme } from "@mui/material";
import { createAppTheme, ThemeName } from "./theme";

/** Portfolio presentation only; the production workspace keeps its existing theme. */
export function createPortfolioTheme(name: ThemeName) {
  const base = createAppTheme(name);
  return createTheme(base, {
    shape: { borderRadius: 8 },
    typography: {
      h4: { fontSize: "2.125rem", fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.045em" },
      h5: { fontSize: "1.5rem", fontWeight: 600, letterSpacing: "-0.035em" },
      body1: { fontSize: "0.875rem", lineHeight: 1.65 },
      body2: { fontSize: "0.8125rem", lineHeight: 1.6 },
      caption: { fontSize: "0.75rem", lineHeight: 1.6 },
    },
    components: {
      MuiPaper: { styleOverrides: { rounded: { borderRadius: 12 } } },
      MuiCard: { styleOverrides: { root: { borderRadius: 12, boxShadow: "none" } } },
      MuiButton: { styleOverrides: {
        root: { borderRadius: 8, minHeight: 38, fontWeight: 500 },
        sizeSmall: { fontSize: "0.8125rem", minHeight: 34 },
      } },
      MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 8, fontSize: "0.8125rem" } } },
      MuiTab: { styleOverrides: { root: { minHeight: 48, padding: "12px 16px", fontWeight: 500 } } },
      MuiTabs: { styleOverrides: { indicator: { height: 2 } } },
      MuiTableCell: { styleOverrides: {
        root: { borderBottomColor: alpha(base.palette.divider, 0.65) },
        head: { fontSize: "0.75rem", fontWeight: 500 },
      } },
      MuiChip: { styleOverrides: {
        root: { borderRadius: 6, fontWeight: 500 },
        outlinedSuccess: { borderColor: "transparent", backgroundColor: alpha(base.palette.success.main, 0.08) },
        outlinedWarning: { borderColor: "transparent", backgroundColor: alpha(base.palette.warning.main, 0.09) },
        outlinedError: { borderColor: "transparent", backgroundColor: alpha(base.palette.error.main, 0.08) },
      } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: 16 } } },
      MuiIconButton: { styleOverrides: { root: { fontSize: "1.25rem" } } },
      MuiTablePagination: { styleOverrides: {
        toolbar: { flexWrap: "wrap", padding: "8px 16px", rowGap: 4, [base.breakpoints.down("sm")]: { padding: "8px 12px" } },
        spacer: { [base.breakpoints.down("sm")]: { display: "none" } },
        selectLabel: { margin: 0 },
        displayedRows: { marginBlock: 0 },
        select: { paddingBlock: 6 },
        actions: { [base.breakpoints.down("sm")]: { marginLeft: "auto" } },
      } },
    },
  });
}
