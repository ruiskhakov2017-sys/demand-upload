import {
  Card,
  CardContent,
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
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function AccountsPage() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Аккаунты MCC</Typography>
      <Card>
        <CardContent>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Customer ID</TableCell>
                  <TableCell>Название</TableCell>
                  <TableCell>Manager</TableCell>
                  <TableCell>Валюта</TableCell>
                  <TableCell>Часовой пояс</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell>TEST</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(accounts.data || []).map((account) => (
                  <TableRow key={account.id}>
                    <TableCell>{account.customer_id}</TableCell>
                    <TableCell>{account.descriptive_name || "Без названия"}</TableCell>
                    <TableCell>{account.manager_customer_id || "—"}</TableCell>
                    <TableCell>{account.currency_code || "—"}</TableCell>
                    <TableCell>{account.time_zone || "—"}</TableCell>
                    <TableCell>
                      <StatusBadge value={account.status} />
                    </TableCell>
                    <TableCell>{account.is_test_account ? "Да" : "Нет"}</TableCell>
                  </TableRow>
                ))}
                {!accounts.data?.length && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Typography color="text.secondary">Синхронизированные аккаунты пока отсутствуют.</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Stack>
  );
}

