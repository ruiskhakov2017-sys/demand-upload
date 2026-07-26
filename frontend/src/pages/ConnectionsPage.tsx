import {
  Alert,
  Box,
  Button,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import AddLinkIcon from "@mui/icons-material/AddLink";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import GoogleIcon from "@mui/icons-material/Google";
import LinkOffIcon from "@mui/icons-material/LinkOff";
import SyncIcon from "@mui/icons-material/Sync";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { t } from "../i18n";

type AuthType = "SERVICE_ACCOUNT" | "OAUTH_WEB";
type Environment = "TEST" | "PRODUCTION";
type Notice = { message: string; severity: "success" | "error" | "info" };

export function ConnectionsPage() {
  const queryClient = useQueryClient();
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
  const params = new URLSearchParams(window.location.search);
  const [form, setForm] = useState({
    name: "",
    login_customer_id: "",
    auth_type: "OAUTH_WEB" as AuthType,
    environment: "TEST" as Environment,
    developer_token: "",
    oauth_client_id: "",
    oauth_client_secret: "",
    service_account_json_text: ""
  });
  const oauthMessage = params.get("message");
  const [notice, setNotice] = useState<Notice | null>(
    oauthMessage
      ? { message: oauthMessage, severity: params.get("oauth") === "error" ? "error" : "success" }
      : null
  );
  const oauth = useMutation({
    mutationFn: api.startOauth,
    onSuccess: (result) => window.location.assign(result.authorization_url)
  });
  const create = useMutation({
    mutationFn: async () => {
      const service_account_json = form.auth_type === "SERVICE_ACCOUNT" && form.service_account_json_text.trim()
        ? JSON.parse(form.service_account_json_text)
        : undefined;
      return api.createConnection({
        name: form.name,
        login_customer_id: form.login_customer_id,
        auth_type: form.auth_type,
        environment: form.environment,
        developer_token: form.developer_token || undefined,
        oauth_client_id: form.auth_type === "OAUTH_WEB" ? form.oauth_client_id : undefined,
        oauth_client_secret: form.auth_type === "OAUTH_WEB" ? form.oauth_client_secret : undefined,
        service_account_json
      });
    },
    onSuccess: (connection) => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      if (connection.auth_type === "OAUTH_WEB") oauth.mutate(connection.id);
      else setNotice({ message: t("ui.8122ea8c55"), severity: "info" });
    }
  });
  const test = useMutation({ mutationFn: api.testConnection, onSuccess: (result) => { setNotice({ message: result.message, severity: result.ok ? "success" : "error" }); queryClient.invalidateQueries({ queryKey: ["connections"] }); } });
  const sync = useMutation({ mutationFn: api.syncAccounts, onSuccess: (result) => { setNotice({ message: t("connections.syncedAccounts", { count: result.synced }), severity: "success" }); queryClient.invalidateQueries({ queryKey: ["accounts"] }); } });
  const disconnect = useMutation({ mutationFn: api.disconnectOauth, onSuccess: () => { setNotice({ message: t("ui.2bed1afe2b"), severity: "success" }); queryClient.invalidateQueries({ queryKey: ["connections"] }); } });
  const error = connections.error || create.error || oauth.error || test.error || sync.error || disconnect.error;

  return (
    <Stack spacing={3}>
      <Box><Typography variant="h4">{t("ui.451c32c81d")}</Typography><Typography color="text.secondary">{t("ui.014714f9ac")}</Typography></Box>
      {error && <Alert severity="error">{error.message}</Alert>}
      {notice && <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>{t("ui.80355ccf86")}</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}><TextField fullWidth label={t("ui.3de49828e8")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Grid>
          <Grid item xs={12} md={4}><TextField fullWidth label="MCC Customer ID" value={form.login_customer_id} onChange={(e) => setForm({ ...form, login_customer_id: e.target.value })} /></Grid>
          <Grid item xs={6} md={2}><FormControl fullWidth><InputLabel>{t("ui.f81e505f9b")}</InputLabel><Select label={t("ui.f81e505f9b")} value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value as Environment })}><MenuItem value="TEST">TEST</MenuItem><MenuItem value="PRODUCTION">PRODUCTION</MenuItem></Select></FormControl></Grid>
          <Grid item xs={6} md={2}><FormControl fullWidth><InputLabel>{t("ui.93900fccba")}</InputLabel><Select label={t("ui.93900fccba")} value={form.auth_type} onChange={(e) => setForm({ ...form, auth_type: e.target.value as AuthType })}><MenuItem value="OAUTH_WEB">OAuth Web</MenuItem><MenuItem value="SERVICE_ACCOUNT">Service account</MenuItem></Select></FormControl></Grid>
          <Grid item xs={12}><TextField fullWidth type="password" label={t("field.developerToken")} value={form.developer_token} onChange={(e) => setForm({ ...form, developer_token: e.target.value })} /></Grid>
          {form.auth_type === "OAUTH_WEB" ? (
            <>
              <Grid item xs={12} md={6}><TextField fullWidth label={t("field.oauthClientId")} value={form.oauth_client_id} onChange={(e) => setForm({ ...form, oauth_client_id: e.target.value })} /></Grid>
              <Grid item xs={12} md={6}><TextField fullWidth type="password" label={t("field.oauthClientSecret")} value={form.oauth_client_secret} onChange={(e) => setForm({ ...form, oauth_client_secret: e.target.value })} /></Grid>
              <Grid item xs={12}><Alert severity="info">{t("ui.b8943a071c")}{" "}{window.location.origin}/api/google-connections/oauth/callback</Alert></Grid>
            </>
          ) : (
            <Grid item xs={12}><TextField fullWidth multiline minRows={6} label={t("field.serviceAccountJson")} value={form.service_account_json_text} onChange={(e) => setForm({ ...form, service_account_json_text: e.target.value })} /></Grid>
          )}
        </Grid>
        <Button sx={{ mt: 2 }} variant="contained" startIcon={form.auth_type === "OAUTH_WEB" ? <GoogleIcon /> : <AddLinkIcon />} disabled={create.isPending || oauth.isPending || !form.name || !form.login_customer_id} onClick={() => create.mutate()}>{form.auth_type === "OAUTH_WEB" ? t("ui.ba5527f9f1") : t("ui.b40f28bb9c")}</Button>
      </Paper>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6">{t("ui.8399b77ec7")}</Typography><Divider sx={{ my: 2 }} />
        <Stack spacing={2} divider={<Divider flexItem />}>
          {(connections.data || []).map((connection) => (
            <Box key={connection.id} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(260px, 1fr) auto" }, gap: 2, alignItems: "center" }}>
              <Box><Typography fontWeight={700}>{connection.name}</Typography><Typography variant="body2" color="text.secondary">MCC {connection.login_customer_id} · {connection.auth_type} · {connection.api_version}</Typography>{connection.last_error && <Typography variant="body2" color="error">{connection.last_error}</Typography>}</Box>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <StatusBadge value={connection.environment} /><StatusBadge value={connection.status} />
                {connection.auth_type === "OAUTH_WEB" && <Button size="small" variant="outlined" startIcon={<GoogleIcon />} onClick={() => oauth.mutate(connection.id)}>{connection.status === "NEEDS_CREDENTIALS" ? t("ui.124298ec71") : t("ui.deda92776c")}</Button>}
                <Button size="small" variant="outlined" startIcon={<FactCheckIcon />} disabled={test.isPending} onClick={() => test.mutate(connection.id)}>{t("ui.52dec92eda")}</Button>
                <Button size="small" variant="outlined" startIcon={<SyncIcon />} disabled={sync.isPending} onClick={() => sync.mutate(connection.id)}>{t("ui.e9af21d100")}</Button>
                {connection.auth_type === "OAUTH_WEB" && connection.status !== "NEEDS_CREDENTIALS" && <Button size="small" color="error" startIcon={<LinkOffIcon />} onClick={() => disconnect.mutate(connection.id)}>{t("ui.94d07a2171")}</Button>}
              </Stack>
            </Box>
          ))}
          {!connections.data?.length && <Typography color="text.secondary">{t("ui.5614a3849a")}</Typography>}
        </Stack>
      </Paper>
    </Stack>
  );
}
