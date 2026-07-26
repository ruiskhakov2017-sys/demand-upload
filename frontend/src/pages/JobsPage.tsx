import {
  Card,
  CardContent,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function JobsPage() {
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.listJobs, refetchInterval: 5000 });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Задания</Typography>
      <Card>
        <CardContent>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Тип</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell>Прогресс</TableCell>
                <TableCell>Ошибка</TableCell>
                <TableCell>Обновлено</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(jobs.data || []).map((job) => {
                const progress =
                  job.progress_total > 0 ? (job.progress_current / job.progress_total) * 100 : 0;
                return (
                  <TableRow key={job.id}>
                    <TableCell>{job.type}</TableCell>
                    <TableCell>
                      <StatusBadge value={job.status} />
                    </TableCell>
                    <TableCell sx={{ minWidth: 180 }}>
                      <LinearProgress variant="determinate" value={progress} />
                    </TableCell>
                    <TableCell>{job.error_message || "—"}</TableCell>
                    <TableCell>{new Date(job.updated_at).toLocaleString("ru-RU")}</TableCell>
                  </TableRow>
                );
              })}
              {!jobs.data?.length && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary">Заданий пока нет.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Stack>
  );
}

