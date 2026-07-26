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
    setMessage(`Данные обновлены ${new Date().toLocaleTimeString("ru-RU")}`);
  };
  const data = summary.data;

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2, flexWrap: "wrap" }}>
        <Box>
          <Typography variant="h4">Обзор</Typography>
          {data?.refreshed_at && (
            <Typography variant="body2" color="text.secondary">
              Состояние на {new Date(data.refreshed_at).toLocaleString("ru-RU")}
            </Typography>
          )}
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<RefreshIcon />} disabled={refreshing} onClick={refresh}>
            Обновить
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate("/uploads/new")}>
            Новая загрузка
          </Button>
        </Stack>
      </Box>
      {(summary.isLoading || refreshing) && <LinearProgress />}
      {summary.error && <Alert severity="error">{summary.error.message}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}

      <Grid container spacing={2}>
        <Kpi title="Подключения" value={data?.connections?.total || 0} detail={`${data?.connections?.connected || 0} активных`} />
        <Kpi title="Аккаунты MCC" value={data?.accounts?.total || 0} detail="синхронизировано" />
        <Kpi title="Загрузки" value={data?.uploads?.total || 0} detail={`${data?.uploads?.draft || 0} черновиков`} />
        <Kpi title="Активные задания" value={data?.jobs?.active || 0} detail={`${data?.jobs?.failed || 0} с ошибкой`} />
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Последние загрузки</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Название</TableCell>
                <TableCell>Источник</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell>Обновлено</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(uploads.data || []).slice(0, 8).map((upload) => (
                <TableRow key={upload.id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/uploads/${upload.id}`)}>
                  <TableCell sx={{ fontWeight: 700 }}>{upload.name}</TableCell>
                  <TableCell>{upload.source_type}</TableCell>
                  <TableCell><StatusBadge value={upload.status} /></TableCell>
                  <TableCell>{new Date(upload.updated_at).toLocaleString("ru-RU")}</TableCell>
                </TableRow>
              ))}
              {!uploads.data?.length && (
                <TableRow><TableCell colSpan={4}><Typography color="text.secondary">Загрузок пока нет.</Typography></TableCell></TableRow>
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
