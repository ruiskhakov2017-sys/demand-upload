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
import { t } from "../i18n";

export function AccountsPage() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("ui.b2018fe9b9")}</Typography>
      <Card>
        <CardContent>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Customer ID</TableCell>
                  <TableCell>{t("ui.3de49828e8")}</TableCell>
                  <TableCell>{t("table.manager")}</TableCell>
                  <TableCell>{t("ui.18be059f5f")}</TableCell>
                  <TableCell>{t("ui.47947a0c46")}</TableCell>
                  <TableCell>{t("ui.f7f293b5c5")}</TableCell>
                  <TableCell>TEST</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(accounts.data || []).map((account) => (
                  <TableRow key={account.id}>
                    <TableCell>{account.customer_id}</TableCell>
                    <TableCell>{account.descriptive_name || t("ui.32b74a3c47")}</TableCell>
                    <TableCell>{account.manager_customer_id || "—"}</TableCell>
                    <TableCell>{account.currency_code || "—"}</TableCell>
                    <TableCell>{account.time_zone || "—"}</TableCell>
                    <TableCell>
                      <StatusBadge value={account.status} />
                    </TableCell>
                    <TableCell>{account.is_test_account ? t("ui.8d2fab2d12") : t("ui.f82a821941")}</TableCell>
                  </TableRow>
                ))}
                {!accounts.data?.length && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Typography color="text.secondary">{t("ui.a52abac8ec")}</Typography>
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
