import {
  Alert,
  Box,
  Button,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, t } from "../i18n";

export function PlansPage({ navigate }: { navigate: Navigate }) {
  const plans = useQuery({ queryKey: ["plans"], queryFn: api.listPlans, refetchInterval: 5000 });
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
        <Typography variant="h4">{t("ui.50a0e24e0f")}</Typography>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => plans.refetch()}>{t("ui.c2f668e54f")}</Button>
      </Box>
      {plans.error && <Alert severity="error">{plans.error.message}</Alert>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small">
          <TableHead><TableRow><TableCell>{t("ui.33415c6ac4")}</TableCell><TableCell>{t("ui.ff0fbd56f4")}</TableCell><TableCell>{t("ui.4ad1aa5f4f")}</TableCell><TableCell>Fingerprint</TableCell><TableCell>{t("ui.f7f293b5c5")}</TableCell><TableCell>{t("ui.3e559b8cc3")}</TableCell><TableCell align="right">{t("ui.1259571a15")}</TableCell></TableRow></TableHead>
          <TableBody>
            {(plans.data || []).map((plan) => (
              <TableRow key={plan.id} hover>
                <TableCell>{formatDate(plan.created_at)}</TableCell>
                <TableCell><StatusBadge value={plan.execution_mode} /></TableCell>
                <TableCell>{plan.local_validation.campaign_count || 0}</TableCell>
                <TableCell sx={{ fontFamily: "monospace" }}>{plan.fingerprint.slice(0, 16)}…</TableCell>
                <TableCell><StatusBadge value={plan.status} /></TableCell>
                <TableCell>{plan.resource_names.length}</TableCell>
                <TableCell align="right"><Button size="small" endIcon={<OpenInNewIcon />} onClick={() => navigate(`/uploads/${plan.upload_id}`)}>{t("ui.dd16b9fb45")}</Button></TableCell>
              </TableRow>
            ))}
            {!plans.data?.length && <TableRow><TableCell colSpan={7}><Typography color="text.secondary">{t("ui.04c5428fb2")}</Typography></TableCell></TableRow>}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  );
}
