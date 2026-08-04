import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { ai } from "../i18n/aiAnalyst";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application render failed", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2 }}>
        <Stack spacing={2} sx={{ width: "min(100%, 640px)" }}>
          <Alert severity="error">
            <Typography fontWeight={800}>{ai("ai.renderErrorTitle")}</Typography>
            <Typography variant="body2">{ai("ai.renderErrorText")}</Typography>
          </Alert>
          <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
            {this.state.error.message}
          </Typography>
          <Button variant="contained" startIcon={<RefreshIcon />} onClick={() => window.location.reload()}>
            {ai("ai.reload")}
          </Button>
        </Stack>
      </Box>
    );
  }
}
