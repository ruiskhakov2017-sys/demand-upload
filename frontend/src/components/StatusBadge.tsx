import { Chip } from "@mui/material";

const colorMap: Record<string, "default" | "primary" | "success" | "warning" | "error" | "info"> = {
  CONNECTED: "success",
  VERIFIED: "success",
  DRAFT: "default",
  NEEDS_CREDENTIALS: "warning",
  ERROR: "error",
  TEST: "info",
  PRODUCTION: "warning",
  QUEUED: "default",
  RUNNING: "primary",
  SUCCEEDED: "success",
  FAILED: "error"
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  const label = value || "UNKNOWN";
  return <Chip size="small" label={label} color={colorMap[label] || "default"} variant="outlined" />;
}
