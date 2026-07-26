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

export function PlansPage({ navigate }: { navigate: Navigate }) {
  const plans = useQuery({ queryKey: ["plans"], queryFn: api.listPlans, refetchInterval: 5000 });
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
        <Typography variant="h4">Планы</Typography>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => plans.refetch()}>Обновить</Button>
      </Box>
      {plans.error && <Alert severity="error">{plans.error.message}</Alert>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small">
          <TableHead><TableRow><TableCell>Создан</TableCell><TableCell>Режим</TableCell><TableCell>Кампании</TableCell><TableCell>Fingerprint</TableCell><TableCell>Статус</TableCell><TableCell>Ресурсы</TableCell><TableCell align="right">Открыть</TableCell></TableRow></TableHead>
          <TableBody>
            {(plans.data || []).map((plan) => (
              <TableRow key={plan.id} hover>
                <TableCell>{new Date(plan.created_at).toLocaleString("ru-RU")}</TableCell>
                <TableCell><StatusBadge value={plan.execution_mode} /></TableCell>
                <TableCell>{plan.local_validation.campaign_count || 0}</TableCell>
                <TableCell sx={{ fontFamily: "monospace" }}>{plan.fingerprint.slice(0, 16)}…</TableCell>
                <TableCell><StatusBadge value={plan.status} /></TableCell>
                <TableCell>{plan.resource_names.length}</TableCell>
                <TableCell align="right"><Button size="small" endIcon={<OpenInNewIcon />} onClick={() => navigate(`/uploads/${plan.upload_id}`)}>Мастер</Button></TableCell>
              </TableRow>
            ))}
            {!plans.data?.length && <TableRow><TableCell colSpan={7}><Typography color="text.secondary">Планы ещё не собраны.</Typography></TableCell></TableRow>}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  );
}
