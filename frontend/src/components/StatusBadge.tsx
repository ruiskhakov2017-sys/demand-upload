import { Chip } from "@mui/material";
import { t } from "../i18n";

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
  const status = value || "UNKNOWN";
  const key = `status.${status}`;
  const translated = t(key);
  return (
    <Chip
      size="small"
      label={translated === key ? status : translated}
      color={colorMap[status] || "default"}
      variant="outlined"
    />
  );
}
