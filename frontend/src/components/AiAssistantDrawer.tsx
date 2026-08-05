import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CloseIcon from "@mui/icons-material/Close";
import OpenInFullIcon from "@mui/icons-material/OpenInFull";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { AiAuthorityMode, api, ExecutionMode, streamAiMessage } from "../api/client";
import type { Navigate } from "../app/App";
import { AiMessageView } from "./AiAnswerView";
import { useLocale } from "../i18n";
import { ai } from "../i18n/aiAnalyst";

export function AiAssistantDrawer({ path, navigate }: { path: string; navigate: Navigate }) {
  const queryClient = useQueryClient();
  const { locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem("axyro.ai.conversation"));
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [authority, setAuthority] = useState<AiAuthorityMode>("READ_ONLY");
  const [environment, setEnvironment] = useState<ExecutionMode>("SIMULATION");
  const capabilities = useQuery({ queryKey: ["ai-capabilities"], queryFn: api.aiCapabilities, enabled: open, retry: false });
  const conversations = useQuery({ queryKey: ["ai-conversations"], queryFn: () => api.aiConversations(false), enabled: open });
  const detail = useQuery({ queryKey: ["ai-conversation", conversationId], queryFn: () => api.getAiConversation(conversationId!), enabled: open && Boolean(conversationId) });
  const interactionDisabled = !capabilities.data?.enabled
    || capabilities.data.kill_switch
    || capabilities.data.provider.configured === false;

  useEffect(() => {
    if (!open || conversations.isLoading || !conversations.data) return;
    const selectedExists = conversationId && conversations.data.some((item) => item.id === conversationId);
    if (!selectedExists) setConversationId(conversations.data[0]?.id || null);
  }, [conversationId, conversations.data, conversations.isLoading, open]);
  useEffect(() => {
    if (detail.data) {
      setAuthority(detail.data.authority_mode);
      setEnvironment(detail.data.google_environment);
    }
  }, [detail.data]);
  useEffect(() => {
    if (conversationId) localStorage.setItem("axyro.ai.conversation", conversationId);
  }, [conversationId]);

  if (path === "/ai-analyst") return null;

  const send = async (text = prompt) => {
    const content = text.trim();
    if (!content || sending || interactionDisabled) return;
    setError(null);
    setLastPrompt(content);
    let id = conversationId;
    try {
      if (!id) {
        const item = await api.createAiConversation({
          title: content.slice(0, 80),
          authority_mode: authority,
          google_environment: environment,
          scope: inheritedScope(path),
          locale,
          time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow"
        });
        id = item.id;
        setConversationId(id);
      } else {
        await api.patchAiConversation(id, { authority_mode: authority, google_environment: environment });
      }
      setPrompt("");
      setSending(true);
      setStreamText("");
      await streamAiMessage(id, { content, model_profile: "FAST", idempotency_key: crypto.randomUUID() }, (event, data) => {
        if (event === "message.delta") setStreamText((value) => value + String(data.text || ""));
        if (event === "run.error") setError(String(data.message || data.code || ai("ai.error")));
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai-conversation", id] }),
        queryClient.invalidateQueries({ queryKey: ["ai-conversations"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-drafts"] })
      ]);
    } catch (value) {
      setError(value instanceof Error ? value.message : String(value));
    } finally {
      setSending(false);
      setStreamText("");
    }
  };

  return (
    <>
      <Tooltip title={ai("ai.assistant")}>
        <IconButton
          color="primary"
          aria-label={ai("ai.assistant")}
          onClick={() => setOpen(true)}
          sx={{ position: "fixed", right: { xs: 16, sm: 24 }, bottom: { xs: 16, sm: 24 }, zIndex: (theme) => theme.zIndex.drawer + 2, width: 52, height: 52, bgcolor: "primary.main", color: "primary.contrastText", boxShadow: 4, "&:hover": { bgcolor: "primary.dark" } }}
        >
          <AutoAwesomeIcon />
        </IconButton>
      </Tooltip>
      <Drawer anchor="right" open={open} onClose={() => setOpen(false)} PaperProps={{ sx: { width: { xs: "100%", sm: 440 }, maxWidth: "100vw" } }}>
        <Stack sx={{ height: "100%" }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, py: 1.5 }}>
            <Box>
              <Typography fontWeight={800}>{ai("ai.assistant")}</Typography>
              <Typography variant="caption" color="text.secondary">{path}</Typography>
            </Box>
            <Stack direction="row">
              <Tooltip title={ai("ai.openFull")}><IconButton onClick={() => { setOpen(false); navigate("/ai-analyst"); }}><OpenInFullIcon /></IconButton></Tooltip>
              <Tooltip title={ai("ai.close")}><IconButton onClick={() => setOpen(false)}><CloseIcon /></IconButton></Tooltip>
            </Stack>
          </Stack>
          <Divider />
          <Stack direction="row" gap={1} sx={{ p: 1.5 }}>
            <FormControl size="small" fullWidth>
              <InputLabel>{ai("ai.conversations")}</InputLabel>
              <Select label={ai("ai.conversations")} value={conversationId || ""} onChange={(event) => setConversationId(event.target.value || null)}>
                {(conversations.data || []).map((item) => <MenuItem key={item.id} value={item.id}>{item.title}</MenuItem>)}
              </Select>
            </FormControl>
            <Button variant="outlined" onClick={() => setConversationId(null)}>+</Button>
          </Stack>
          <Stack direction="row" gap={1} sx={{ px: 1.5, pb: 1.5 }}>
            <FormControl size="small" fullWidth><InputLabel>{ai("ai.authority")}</InputLabel><Select label={ai("ai.authority")} value={authority} onChange={(event) => setAuthority(event.target.value as AiAuthorityMode)}><MenuItem value="READ_ONLY">{ai("ai.readOnly")}</MenuItem>{capabilities.data?.authority_modes.includes("DRAFT_ONLY") && <MenuItem value="DRAFT_ONLY">{ai("ai.draftOnly")}</MenuItem>} {capabilities.data?.authority_modes.includes("CONFIRM_REQUIRED") && <MenuItem value="CONFIRM_REQUIRED">{ai("ai.confirmRequired")}</MenuItem>}</Select></FormControl>
            <FormControl size="small" fullWidth><InputLabel>{ai("ai.environment")}</InputLabel><Select label={ai("ai.environment")} value={environment} onChange={(event) => setEnvironment(event.target.value as ExecutionMode)}><MenuItem value="SIMULATION">{ai("ai.simulation")}</MenuItem><MenuItem value="GOOGLE_TEST">{ai("ai.googleTest")}</MenuItem><MenuItem value="PRODUCTION" disabled={!capabilities.data?.production.read_enabled}>{ai("ai.production")}</MenuItem></Select></FormControl>
          </Stack>
          <Divider />
          <Box sx={{ flex: 1, overflowY: "auto", p: 2 }} aria-live="polite">
            {detail.isLoading && <CircularProgress size={24} />}
            <Stack spacing={2}>
              {(detail.data?.messages || []).map((message) => <AiMessageView key={message.id} message={message} onNavigate={(target) => { setOpen(false); navigate(target); }} />)}
              {sending && <Paper variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" gap={1} alignItems="center"><CircularProgress size={18} /><Typography variant="body2">{streamText || ai("ai.loading")}</Typography></Stack></Paper>}
              {!detail.isLoading && !detail.data?.messages?.length && <Typography color="text.secondary">{ai("ai.emptyText")}</Typography>}
            </Stack>
          </Box>
          {capabilities.data?.provider.configured === false && <Alert severity="warning">{ai("ai.providerMissing")}</Alert>}
          {capabilities.data?.kill_switch && <Alert severity="error">{ai("ai.killSwitch")}</Alert>}
          {capabilities.data?.enabled === false && <Alert severity="error">{ai("ai.disabled")}</Alert>}
          {error && <Alert severity="error" onClose={() => setError(null)} action={lastPrompt && !sending ? <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={() => void send(lastPrompt)}>{ai("ai.retry")}</Button> : undefined}>{error}</Alert>}
          <Box sx={{ p: 1.5, borderTop: 1, borderColor: "divider" }}>
            <TextField fullWidth multiline minRows={2} maxRows={5} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={ai("ai.askPlaceholder")} disabled={sending || interactionDisabled} inputProps={{ maxLength: 20_000 }} />
            <Button fullWidth sx={{ mt: 1 }} variant="contained" endIcon={<SendIcon />} disabled={!prompt.trim() || sending || interactionDisabled} onClick={() => void send()}>{ai("ai.send")}</Button>
          </Box>
        </Stack>
      </Drawer>
    </>
  );
}

function inheritedScope(path: string) {
  const empty = {
    connection_ids: [], mcc_ids: [], geo_ids: [], account_ids: [], campaign_ids: [],
    period: "7d", start_date: null, end_date: null, metric_source: "GOOGLE_ADS", currency: null
  };
  const account = path.match(/^\/control-center\/accounts\/([0-9a-f-]{36})/i)?.[1];
  const campaign = path.match(/^\/control-center\/campaigns\/([0-9a-f-]{36})/i)?.[1];
  return { ...empty, account_ids: account ? [account] : [], campaign_ids: campaign ? [campaign] : [] };
}
