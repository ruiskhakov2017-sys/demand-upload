import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, t } from "../i18n";

export function DashboardPage({ navigate }: { navigate: Navigate }) {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const uploads = useQuery({ queryKey: ["uploads"], queryFn: api.listUploads });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.listJobs });
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    setRefreshing(true);
    setMessage(null);
    await Promise.all([
      summary.refetch(),
      uploads.refetch(),
      jobs.refetch(),
      queryClient.invalidateQueries({ queryKey: ["connections"] }),
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    ]);
    setRefreshing(false);
    setMessage(t("dashboard.refreshedAt", {
      time: formatDate(new Date(), { timeStyle: "medium" })
    }));
  };
  const data = summary.data;

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2, flexWrap: "wrap" }}>
        <Box>
          <Typography variant="h4">{t("ui.39c6387206")}</Typography>
          {data?.refreshed_at && (
            <Typography variant="body2" color="text.secondary">
              {t("ui.e0a9c29190")}{" "}{formatDate(data.refreshed_at)}
            </Typography>
          )}
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<RefreshIcon />} disabled={refreshing} onClick={refresh}>
            {t("ui.c2f668e54f")}</Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate("/uploads/new")}>
            {t("ui.7075f72219")}</Button>
        </Stack>
      </Box>
      {(summary.isLoading || refreshing) && <LinearProgress />}
      {summary.error && <Alert severity="error">{summary.error.message}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}

      <Grid container spacing={2}>
        <Kpi title={t("ui.c188eb08a1")} value={data?.connections?.total || 0} detail={t("dashboard.activeCount", { count: data?.connections?.connected || 0 })} />
        <Kpi title={t("ui.b2018fe9b9")} value={data?.accounts?.total || 0} detail={t("ui.59ef0a7e00")} />
        <Kpi title={t("ui.dbf2a0e234")} value={data?.uploads?.total || 0} detail={t("dashboard.draftCount", { count: data?.uploads?.draft || 0 })} />
        <Kpi title={t("ui.b4e80d3c38")} value={data?.jobs?.active || 0} detail={t("dashboard.failedCount", { count: data?.jobs?.failed || 0 })} />
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>{t("ui.b5606f56e3")}</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("ui.3de49828e8")}</TableCell>
                <TableCell>{t("ui.8290a3dbc0")}</TableCell>
                <TableCell>{t("ui.f7f293b5c5")}</TableCell>
                <TableCell>{t("ui.484f3ba9b5")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(uploads.data || []).slice(0, 8).map((upload) => (
                <TableRow key={upload.id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/uploads/${upload.id}`)}>
                  <TableCell sx={{ fontWeight: 700 }}>{upload.name}</TableCell>
                  <TableCell>{upload.source_type}</TableCell>
                  <TableCell><StatusBadge value={upload.status} /></TableCell>
                  <TableCell>{formatDate(upload.updated_at)}</TableCell>
                </TableRow>
              ))}
              {!uploads.data?.length && (
                <TableRow><TableCell colSpan={4}><Typography color="text.secondary">{t("ui.13a82fd106")}</Typography></TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Stack>
  );
}

function Kpi({ title, value, detail }: { title: string; value: number; detail: string }) {
  return (
    <Grid item xs={12} sm={6} lg={3}>
      <Card sx={{ height: "100%" }}>
        <CardContent>
          <Typography variant="body2" color="text.secondary">{title}</Typography>
          <Typography variant="h4" sx={{ my: 0.5 }}>{value}</Typography>
          <Typography variant="body2" color="text.secondary">{detail}</Typography>
        </CardContent>
      </Card>
    </Grid>
  );
}
