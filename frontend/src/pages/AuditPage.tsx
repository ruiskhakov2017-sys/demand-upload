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

export function AuditPage() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: api.listAudit });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Журнал</Typography>
      <Card>
        <CardContent>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Время</TableCell>
                <TableCell>Действие</TableCell>
                <TableCell>Сущность</TableCell>
                <TableCell>Данные</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(audit.data || []).map((row) => (
                <TableRow key={String(row.id)}>
                  <TableCell>{new Date(String(row.created_at)).toLocaleString("ru-RU")}</TableCell>
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
                    <Typography color="text.secondary">Записей журнала пока нет.</Typography>
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

