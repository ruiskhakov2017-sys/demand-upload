import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import YouTubeIcon from "@mui/icons-material/YouTube";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, MediaAsset } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { formatNumber, t } from "../i18n";

export function MediaPage() {
  const queryClient = useQueryClient();
  const media = useQuery({ queryKey: ["media"], queryFn: api.listMedia, refetchInterval: 5000 });
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });
  const [youtubeId, setYoutubeId] = useState("");
  const [target, setTarget] = useState<MediaAsset | null>(null);
  const [previewAsset, setPreviewAsset] = useState<MediaAsset | null>(null);
  const [queueForm, setQueueForm] = useState({
    execution_mode: "SIMULATION" as "SIMULATION" | "LIVE",
    connection_id: "",
    customer_id: "",
    title: "",
    description: ""
  });
  const [message, setMessage] = useState<string | null>(null);
  const upload = useMutation({
    mutationFn: api.uploadMedia,
    onSuccess: (asset) => {
      setMessage(t("media.fileAdded", { name: asset.name }));
      queryClient.invalidateQueries({ queryKey: ["media"] });
    }
  });
  const register = useMutation({
    mutationFn: () => api.registerYoutube(youtubeId),
    onSuccess: () => {
      setYoutubeId("");
      setMessage(t("ui.99dafadbae"));
      queryClient.invalidateQueries({ queryKey: ["media"] });
    }
  });
  const queue = useMutation({
    mutationFn: () => api.queueYoutubeUpload(target!.id, queueForm),
    onSuccess: (result) => {
      setTarget(null);
      setMessage(result.reused ? t("ui.428423e0dd") : t("ui.6647e6b2fd"));
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["media"] });
    }
  });
  const error = media.error || upload.error || register.error || queue.error;
  const visibleAccounts = (accounts.data || []).filter(
    (item) => !queueForm.connection_id || item.connection_id === queueForm.connection_id
  );

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box><Typography variant="h4">{t("ui.198be2a9a8")}</Typography><Typography color="text.secondary">{t("ui.ecf41dd810")}</Typography></Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => media.refetch()}>{t("ui.c2f668e54f")}</Button>
          <Button component="label" variant="contained" startIcon={<CloudUploadOutlinedIcon />} disabled={upload.isPending}>
            {t("ui.6212feb014")}{" "}<input hidden type="file" accept="image/png,image/jpeg,video/mp4,video/quicktime,video/webm" onChange={(event) => event.target.files?.[0] && upload.mutate(event.target.files[0])} />
          </Button>
        </Stack>
      </Box>
      {error && <Alert severity="error">{error.message}</Alert>}
      {message && <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField label={t("ui.403d582401")} value={youtubeId} onChange={(event) => setYoutubeId(event.target.value)} sx={{ minWidth: 300 }} />
        <Button variant="outlined" startIcon={<YouTubeIcon />} disabled={!youtubeId.trim() || register.isPending} onClick={() => register.mutate()}>{t("ui.559a87f7cc")}</Button>
      </Stack>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small">
          <TableHead><TableRow><TableCell>{t("ui.3de49828e8")}</TableCell><TableCell>{t("ui.d25691ca40")}</TableCell><TableCell>{t("ui.36b5a6a017")}</TableCell><TableCell>SHA-256 / YouTube ID</TableCell><TableCell>{t("ui.f7f293b5c5")}</TableCell><TableCell align="right">{t("ui.4fe9c0675c")}</TableCell></TableRow></TableHead>
          <TableBody>
            {(media.data || []).map((asset) => (
              <TableRow key={asset.id} hover>
                <TableCell>{asset.name}</TableCell>
                <TableCell>{asset.kind}</TableCell>
                <TableCell>{asset.width && asset.height ? `${asset.width} × ${asset.height}` : asset.duration_seconds ? t("media.durationSeconds", { count: formatNumber(asset.duration_seconds, { maximumFractionDigits: 1 }) }) : formatBytes(asset.size_bytes)}</TableCell>
                <TableCell sx={{ fontFamily: "monospace", maxWidth: 240, overflowWrap: "anywhere" }}>{asset.youtube_video_id || asset.sha256}</TableCell>
                <TableCell><StatusBadge value={asset.status} /></TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={0.5} justifyContent="flex-end" alignItems="center">
                    <Tooltip title={t("ui.5d092ca855")}>
                      <IconButton size="small" aria-label={t("media.previewLabel", { name: asset.name })} onClick={() => setPreviewAsset(asset)}>
                        <VisibilityOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    {asset.kind === "VIDEO" && !asset.youtube_video_id && <Button size="small" startIcon={<YouTubeIcon />} onClick={() => { setTarget(asset); setQueueForm((value) => ({ ...value, title: asset.name.replace(/\.[^.]+$/, "") })); }}>{t("ui.cc02f4b5b6")}</Button>}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!media.data?.length && <TableRow><TableCell colSpan={6}><Typography color="text.secondary">{t("ui.28543a9a06")}</Typography></TableCell></TableRow>}
          </TableBody>
        </Table>
      </Box>

      <Dialog open={Boolean(previewAsset)} onClose={() => setPreviewAsset(null)} fullWidth maxWidth="md">
        <DialogTitle sx={{ overflowWrap: "anywhere" }}>{previewAsset?.name}</DialogTitle>
        <DialogContent sx={{ display: "grid", placeItems: "center", minHeight: 240 }}>
          {previewAsset?.kind === "IMAGE" && (
            <Box
              component="img"
              src={api.mediaContentUrl(previewAsset.id)}
              alt={previewAsset.name}
              sx={{ display: "block", maxWidth: "100%", maxHeight: "70vh", objectFit: "contain" }}
            />
          )}
          {previewAsset?.kind === "VIDEO" && (
            <Box
              component="video"
              src={api.mediaContentUrl(previewAsset.id)}
              controls
              preload="metadata"
              sx={{ display: "block", width: "100%", maxHeight: "70vh", bgcolor: "common.black" }}
            />
          )}
          {previewAsset?.kind === "YOUTUBE" && previewAsset.youtube_video_id && (
            <Box
              component="iframe"
              src={`https://www.youtube-nocookie.com/embed/${previewAsset.youtube_video_id}`}
              title={previewAsset.name}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              sx={{ width: "100%", aspectRatio: "16 / 9", border: 0 }}
            />
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setPreviewAsset(null)}>{t("ui.4ae50d3073")}</Button></DialogActions>
      </Dialog>

      <Dialog open={Boolean(target)} onClose={() => setTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>{t("ui.9826673908")}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ pt: 1 }}>
            <Grid item xs={12} sm={6}><FormControl fullWidth><InputLabel>{t("ui.ff0fbd56f4")}</InputLabel><Select label={t("ui.ff0fbd56f4")} value={queueForm.execution_mode} onChange={(e) => setQueueForm({ ...queueForm, execution_mode: e.target.value as "SIMULATION" | "LIVE" })}><MenuItem value="SIMULATION">{t("ui.c69d7e0c09")}</MenuItem><MenuItem value="LIVE">Google Ads</MenuItem></Select></FormControl></Grid>
            <Grid item xs={12} sm={6}><FormControl fullWidth><InputLabel>{t("ui.79e350f743")}</InputLabel><Select label={t("ui.79e350f743")} value={queueForm.connection_id} onChange={(e) => setQueueForm({ ...queueForm, connection_id: e.target.value })}><MenuItem value="">{t("ui.fad95c5cb0")}</MenuItem>{(connections.data || []).map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.status}</MenuItem>)}</Select></FormControl></Grid>
            <Grid item xs={12}><FormControl fullWidth><InputLabel>Customer ID</InputLabel><Select label="Customer ID" value={queueForm.customer_id} onChange={(e) => setQueueForm({ ...queueForm, customer_id: e.target.value })}>{visibleAccounts.map((item) => <MenuItem key={item.id} value={item.customer_id}>{item.customer_id} · {item.descriptive_name || t("ui.32b74a3c47")}</MenuItem>)}</Select></FormControl></Grid>
            {!visibleAccounts.length && <Grid item xs={12}><TextField fullWidth label="Customer ID" value={queueForm.customer_id} onChange={(e) => setQueueForm({ ...queueForm, customer_id: e.target.value })} /></Grid>}
            <Grid item xs={12}><TextField fullWidth label={t("ui.d4cf7388b0")} value={queueForm.title} onChange={(e) => setQueueForm({ ...queueForm, title: e.target.value })} /></Grid>
            <Grid item xs={12}><TextField fullWidth multiline minRows={3} label={t("ui.f5441f6aee")} value={queueForm.description} onChange={(e) => setQueueForm({ ...queueForm, description: e.target.value })} /></Grid>
            <Grid item xs={12}><Alert severity={queueForm.execution_mode === "LIVE" ? "warning" : "info"}>{queueForm.execution_mode === "LIVE" ? t("ui.b083a83c9c") : t("ui.eef262846e")}</Alert></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setTarget(null)}>{t("ui.0ec753be8d")}</Button><Button variant="contained" disabled={!queueForm.customer_id || !queueForm.title || queue.isPending} onClick={() => queue.mutate()}>{t("ui.9da5491295")}</Button></DialogActions>
      </Dialog>
    </Stack>
  );
}

function formatBytes(value: number) {
  if (!value) return "—";
  if (value < 1024 * 1024) return t("media.kilobytes", { count: formatNumber(value / 1024, { maximumFractionDigits: 1 }) });
  return t("media.megabytes", { count: formatNumber(value / 1024 / 1024, { maximumFractionDigits: 1 }) });
}
