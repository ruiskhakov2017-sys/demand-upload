import {
  Card,
  CardContent,
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
import { formatDate, t } from "../i18n";

export function AuditPage() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: api.listAudit });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("ui.67ade741ae")}</Typography>
      <Card>
        <CardContent>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("ui.c80d7e8172")}</TableCell>
                <TableCell>{t("ui.4fe9c0675c")}</TableCell>
                <TableCell>{t("ui.0af19ba296")}</TableCell>
                <TableCell>{t("ui.d8e5fd81c5")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(audit.data || []).map((row) => (
                <TableRow key={String(row.id)}>
                  <TableCell>{formatDate(String(row.created_at))}</TableCell>
                  <TableCell>{String(row.action)}</TableCell>
                  <TableCell>
                    {row.entity_type ? `${String(row.entity_type)} ${String(row.entity_id || "")}` : "—"}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: "monospace" }}>
                      {JSON.stringify(row.summary)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {!audit.data?.length && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography color="text.secondary">{t("ui.ec2d6865cd")}</Typography>
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
