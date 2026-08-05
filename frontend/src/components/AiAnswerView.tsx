import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  LinearProgress,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";

import type { AiMessage, AiStructuredAnswer } from "../api/client";
import { formatDate, formatNumber } from "../i18n";
import { ai } from "../i18n/aiAnalyst";

type AnswerProps = {
  message: AiMessage;
  onNavigate?: (path: string) => void;
};

const severityMap = {
  INFO: "info",
  SUCCESS: "success",
  WARNING: "warning",
  ERROR: "error"
} as const;

export function AiMessageView({ message, onNavigate }: AnswerProps) {
  if (message.role === "USER") {
    return (
      <Paper
        elevation={0}
        sx={{ ml: { xs: 2, sm: 8 }, p: 1.5, bgcolor: "action.selected", border: 1, borderColor: "divider" }}
      >
        <Typography sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{message.content}</Typography>
        <Typography variant="caption" color="text.secondary">{formatDate(message.created_at)}</Typography>
      </Paper>
    );
  }

  const answer = message.structured_content as Partial<AiStructuredAnswer>;
  const hasStructured = Boolean(answer.answer || answer.findings?.length || answer.tables?.length || answer.sources?.length);
  return (
    <Stack spacing={2} component="article" aria-label={ai("ai.answer")}>
      <Box>
        <Typography variant="overline" color="primary.main" fontWeight={800}>{ai("ai.answer")}</Typography>
        <Typography sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", lineHeight: 1.7 }}>
          {answer.answer || message.content}
        </Typography>
      </Box>

      {hasStructured && <AnswerWarnings answer={answer} />}
      {!!answer.currency_groups?.length && <CurrencyGroups groups={answer.currency_groups} />}

      {!!answer.findings?.length && (
        <Box>
          <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>{ai("ai.findings")}</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" }, gap: 1 }}>
            {answer.findings.map((finding, index) => (
              <Alert key={`${finding.title}-${index}`} severity={severityMap[finding.severity]} variant="outlined">
                <Typography fontWeight={800}>{finding.title}</Typography>
                <Typography variant="body2">{finding.detail}</Typography>
                <Typography variant="caption" display="block" sx={{ mt: 0.75 }}>
                  {ai("ai.confidence")}: {Math.round(finding.confidence * 100)}%
                </Typography>
              </Alert>
            ))}
          </Box>
        </Box>
      )}

      {!!answer.tables?.length && answer.tables.map((table, tableIndex) => (
        <Box key={`${table.title}-${tableIndex}`}>
          <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>{table.title}</Typography>
          <TableContainer sx={{ border: 1, borderColor: "divider", maxWidth: "100%" }}>
            <Table size="small" aria-label={table.title}>
              <TableHead>
                <TableRow>{table.columns.map((column) => <TableCell key={column.key}>{column.label}</TableCell>)}</TableRow>
              </TableHead>
              <TableBody>
                {table.rows.map((row, rowIndex) => (
                  <TableRow key={`${row.object_id || "row"}-${rowIndex}`} hover>
                    {table.columns.map((column) => {
                      const cell = row.cells.find((item) => item.key === column.key);
                      return <TableCell key={column.key}>{cell?.value ?? "—"}</TableCell>;
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      ))}

      {!!answer.charts?.length && (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" }, gap: 2 }}>
          {answer.charts.map((chart, index) => <SafeChart key={`${chart.title}-${index}`} chart={chart} />)}
        </Box>
      )}

      {!!answer.evidence?.length && (
        <Accordion disableGutters elevation={0} sx={{ border: 1, borderColor: "divider", "&:before": { display: "none" } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography fontWeight={700}>{ai("ai.evidence")} · {answer.evidence.length}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack divider={<Divider flexItem />}>
              {answer.evidence.map((item, index) => (
                <Box key={`${item.label || "evidence"}-${index}`} sx={{ py: 1 }}>
                  <Typography variant="body2" fontWeight={700}>{String(item.label || "")}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
                    {String(item.value ?? "")}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {!!answer.sources?.length && (
        <Box>
          <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>{ai("ai.sources")}</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" }, gap: 1 }}>
            {answer.sources.map((source, index) => (
              <Paper key={`${source.provider || "source"}-${index}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <StorageOutlinedIcon fontSize="small" color="action" />
                  <Typography variant="body2" fontWeight={800}>{String(source.provider || "Axyro")}</Typography>
                  <Chip size="small" label={String(source.freshness || "UNKNOWN")} />
                </Stack>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.75 }}>
                  {String(source.semantic_metric || "DATA")} · {String(source.attribution || "—")}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatDate(source.observed_at as string | null)}
                </Typography>
              </Paper>
            ))}
          </Box>
        </Box>
      )}

      {answer.exact_backend_condition && (
        <Alert severity="info" variant="outlined">
          <Typography variant="caption" fontWeight={800}>{ai("ai.condition")}</Typography>
          <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>{answer.exact_backend_condition}</Typography>
        </Alert>
      )}

      {!!answer.object_links?.length && (
        <Stack direction="row" gap={1} flexWrap="wrap">
          {answer.object_links.map((link) => (
            <Button
              key={`${link.path}-${link.object_id}`}
              size="small"
              variant="outlined"
              endIcon={<OpenInNewIcon />}
              onClick={() => navigate(link.path, onNavigate)}
            >
              {link.label}
            </Button>
          ))}
        </Stack>
      )}

      {!!message.tool_timeline?.length && (
        <Accordion disableGutters elevation={0} sx={{ border: 1, borderColor: "divider", "&:before": { display: "none" } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography fontWeight={700}>{ai("ai.toolTimeline")} · {message.tool_timeline.length}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="caption" color="text.secondary">{ai("ai.noInternalReasoning")}</Typography>
            <Stack spacing={1} sx={{ mt: 1 }}>
              {message.tool_timeline.map((tool) => (
                <Stack key={tool.id} direction="row" gap={1} alignItems="center" flexWrap="wrap">
                  <Chip size="small" label={tool.risk_class} color={tool.status === "SUCCEEDED" ? "success" : "default"} />
                  <Typography variant="body2" fontFamily="monospace">{tool.tool_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {tool.duration_ms === null ? "—" : `${tool.duration_ms} ms`}
                  </Typography>
                  {tool.job_id && (
                    <Button size="small" variant="text" onClick={() => navigate(tool.job_path || "/jobs", onNavigate)}>
                      {tool.job_status || "JOB"} · {tool.job_id.slice(0, 8)}
                    </Button>
                  )}
                </Stack>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}
      <Typography variant="caption" color="text.secondary">{formatDate(message.created_at)}</Typography>
    </Stack>
  );
}

function AnswerWarnings({ answer }: { answer: Partial<AiStructuredAnswer> }) {
  const warnings = [...(answer.warnings || []), ...(answer.caveats || [])];
  const mixed = (answer.currency_groups?.length || 0) > 1;
  const stale = String(answer.freshness || "").toUpperCase().includes("STALE");
  const partial = String(answer.completeness || "").toUpperCase() !== "COMPLETE";
  if (!warnings.length && !mixed && !stale && !partial) return null;
  return (
    <Stack spacing={1} aria-live="polite">
      {mixed && <Alert severity="warning">{ai("ai.mixedCurrency")}</Alert>}
      {stale && <Alert severity="warning">{ai("ai.stale")}</Alert>}
      {partial && <Alert severity="warning">{ai("ai.partial")}</Alert>}
      {warnings.map((warning, index) => <Alert key={`${warning}-${index}`} severity="warning">{warning}</Alert>)}
    </Stack>
  );
}

function CurrencyGroups({ groups }: { groups: AiStructuredAnswer["currency_groups"] }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 1 }}>
      {groups.map((group) => (
        <Box key={group.currency_code} sx={{ borderLeft: 3, borderColor: "primary.main", pl: 1.5, py: 0.5 }}>
          <Typography variant="caption" color="text.secondary">{group.currency_code}</Typography>
          <Typography fontWeight={800}>
            {group.cost_micros === null ? "—" : formatNumber(group.cost_micros / 1_000_000, { maximumFractionDigits: 2 })}
          </Typography>
          <Typography variant="caption" color="text.secondary">{group.accounts} {ai("ai.accountCount")}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function SafeChart({ chart }: { chart: AiStructuredAnswer["charts"][number] }) {
  const values = chart.series.flatMap((series) => series.points.map((point) => point.value));
  const max = Math.max(1, ...values.map((value) => Math.abs(value)));
  return (
    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 0 }}>
      <Typography variant="subtitle2" fontWeight={800}>{chart.title}</Typography>
      <Box sx={{ height: 180, mt: 1, display: "flex", alignItems: "end", gap: 1, overflowX: "auto" }} role="img" aria-label={chart.title}>
        {chart.series.flatMap((series) => series.points.map((point, index) => (
          <Stack key={`${series.name}-${point.label}-${index}`} sx={{ minWidth: 38, height: "100%", justifyContent: "end" }} alignItems="center">
            <Typography variant="caption" sx={{ fontSize: 10 }}>{formatNumber(point.value, { maximumFractionDigits: 1 })}</Typography>
            <Box
              sx={{
                width: 24,
                height: `${Math.max(3, Math.abs(point.value) / max * 125)}px`,
                bgcolor: series.color || "primary.main",
                borderRadius: "3px 3px 0 0"
              }}
            />
            <Typography variant="caption" noWrap sx={{ maxWidth: 52, fontSize: 10 }}>{point.label}</Typography>
          </Stack>
        )))}
      </Box>
      <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1 }}>
        {chart.series.map((series) => <Chip key={series.name} size="small" label={series.name} sx={{ borderLeft: 3, borderColor: series.color }} />)}
      </Stack>
    </Paper>
  );
}

function navigate(path: string, onNavigate?: (path: string) => void) {
  if (!path.startsWith("/")) return;
  if (onNavigate) onNavigate(path);
  else window.location.assign(path);
}
