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
import { formatDate, t } from "../i18n";

export function JobsPage() {
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.listJobs, refetchInterval: 5000 });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("ui.a11acfa069")}</Typography>
      <Card>
        <CardContent>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("ui.d25691ca40")}</TableCell>
                <TableCell>{t("ui.f7f293b5c5")}</TableCell>
                <TableCell>{t("ui.88d59af4fe")}</TableCell>
                <TableCell>{t("ui.72aecd9ad8")}</TableCell>
                <TableCell>{t("ui.484f3ba9b5")}</TableCell>
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
                    <TableCell>{formatDate(job.updated_at)}</TableCell>
                  </TableRow>
                );
              })}
              {!jobs.data?.length && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary">{t("ui.bdaa4eb749")}</Typography>
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
