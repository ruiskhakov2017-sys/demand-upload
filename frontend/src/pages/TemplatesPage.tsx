import {
  Alert,
  Box,
  Button,
  Grid,
  IconButton,
  Paper,
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
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import UpgradeOutlinedIcon from "@mui/icons-material/UpgradeOutlined";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import type { Navigate } from "../app/App";

export function TemplatesPage({ navigate }: { navigate: Navigate }) {
  const queryClient = useQueryClient();
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const [form, setForm] = useState({ name: "", description: "", business_name: "", daily_budget: "10", target_cpa: "5", location_ids: "2840", language_ids: "1000" });
  const create = useMutation({
    mutationFn: () => api.createTemplate({
      name: form.name,
      description: form.description || null,
      payload: {
        campaign: { business_name: form.business_name, ad_group_name: "Основная группа", ad_type: "VIDEO" },
        bidding: { strategy: "TARGET_CPA", target_cpa: form.target_cpa },
        budget: { mode: "FIXED", fixed: form.daily_budget },
        targeting: { location_ids: split(form.location_ids), language_ids: split(form.language_ids) },
        url: { final_url: "https://example.com" },
        texts: { business_name: form.business_name, call_to_action: "LEARN_MORE", headlines: ["Новый заголовок"], long_headline: "Новый длинный заголовок", descriptions: ["Описание предложения"] }
      }
    }),
    onSuccess: () => { setForm({ ...form, name: "", description: "" }); queryClient.invalidateQueries({ queryKey: ["templates"] }); }
  });
  const remove = useMutation({ mutationFn: api.deleteTemplate, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }) });
  const copy = useMutation({ mutationFn: (templateId: string) => { const template = templates.data!.find((item) => item.id === templateId)!; return api.copyTemplate(templateId, { name: `${template.name} · копия ${Date.now().toString().slice(-4)}` }); }, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }) });
  const version = useMutation({ mutationFn: (templateId: string) => { const template = templates.data!.find((item) => item.id === templateId)!; return api.createTemplateVersion(templateId, { payload: template.payload, change_summary: "Новая зафиксированная версия" }); }, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }) });
  const useTemplate = useMutation({
    mutationFn: async (templateId: string) => {
      const template = templates.data!.find((item) => item.id === templateId)!;
      const upload = await api.createUpload({ name: `${template.name} · ${new Date().toLocaleDateString("ru-RU")}`, execution_mode: "SIMULATION" });
      await api.updateUpload(upload.id, { draft: { execution_mode: "SIMULATION", source_mode: "MANUAL", builder: { creation_mode: "FROM_TEMPLATE", template_id: template.id, template_defaults: template.payload } } });
      return upload;
    },
    onSuccess: (upload) => navigate(`/uploads/${upload.id}`)
  });
  const error = templates.error || create.error || remove.error || copy.error || version.error || useTemplate.error;
  return (
    <Stack spacing={3}>
      <Typography variant="h4">Шаблоны</Typography>
      {error && <Alert severity="error">{error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>Новый шаблон</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}><TextField fullWidth label="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Grid>
          <Grid item xs={12} md={8}><TextField fullWidth label="Описание" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Grid>
          <Grid item xs={12} md={4}><TextField fullWidth label="Название компании" value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} /></Grid>
          <Grid item xs={6} md={2}><TextField fullWidth label="Бюджет" value={form.daily_budget} onChange={(e) => setForm({ ...form, daily_budget: e.target.value })} /></Grid>
          <Grid item xs={6} md={2}><TextField fullWidth label="Target CPA" value={form.target_cpa} onChange={(e) => setForm({ ...form, target_cpa: e.target.value })} /></Grid>
          <Grid item xs={6} md={2}><TextField fullWidth label="Гео ID" value={form.location_ids} onChange={(e) => setForm({ ...form, location_ids: e.target.value })} /></Grid>
          <Grid item xs={6} md={2}><TextField fullWidth label="Язык ID" value={form.language_ids} onChange={(e) => setForm({ ...form, language_ids: e.target.value })} /></Grid>
        </Grid>
        <Button sx={{ mt: 2 }} variant="contained" startIcon={<AddIcon />} disabled={form.name.trim().length < 2 || create.isPending} onClick={() => create.mutate()}>Сохранить шаблон</Button>
      </Paper>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small"><TableHead><TableRow><TableCell>Название</TableCell><TableCell>Версия</TableCell><TableCell>Описание</TableCell><TableCell>Обновлён</TableCell><TableCell align="right">Действия</TableCell></TableRow></TableHead>
          <TableBody>{(templates.data || []).map((item) => <TableRow key={item.id}><TableCell sx={{ fontWeight: 700 }}>{item.name}<Typography variant="caption" color="text.secondary" display="block">{item.semantic_key}</Typography></TableCell><TableCell>v{item.current_version}</TableCell><TableCell>{item.description || "—"}</TableCell><TableCell>{new Date(item.updated_at).toLocaleString("ru-RU")}</TableCell><TableCell align="right"><Button size="small" startIcon={<PlayArrowIcon />} onClick={() => useTemplate.mutate(item.id)}>Использовать</Button><Tooltip title="Новая версия"><IconButton size="small" onClick={() => version.mutate(item.id)}><UpgradeOutlinedIcon /></IconButton></Tooltip><Tooltip title="Копировать"><IconButton size="small" onClick={() => copy.mutate(item.id)}><ContentCopyOutlinedIcon /></IconButton></Tooltip><Tooltip title="Архивировать"><IconButton size="small" onClick={() => remove.mutate(item.id)}><DeleteOutlineIcon /></IconButton></Tooltip></TableCell></TableRow>)}{!templates.data?.length && <TableRow><TableCell colSpan={5}><Typography color="text.secondary">Шаблонов пока нет.</Typography></TableCell></TableRow>}</TableBody>
        </Table>
      </Box>
    </Stack>
  );
}

function split(value: string) { return value.split(/[,;|]/).map((item) => item.trim()).filter(Boolean); }
