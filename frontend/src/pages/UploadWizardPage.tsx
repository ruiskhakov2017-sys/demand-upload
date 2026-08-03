import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Step,
  StepButton,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import YouTubeIcon from "@mui/icons-material/YouTube";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  api,
  CampaignInstance,
  CustomerAccount,
  DeploymentPlan,
  DomainValidationReport,
  DomainValidationResult,
  ExecutionMode,
  GoogleConnection,
  LaunchBatch,
  MediaAsset
} from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { ScheduleEditor } from "../components/ScheduleEditor";
import { applyCampaignCount, normalizeCampaignCount, QUICK_CAMPAIGN_COUNTS } from "../domain/campaignCounts";
import { formatDate, formatNumber, localeTag, t } from "../i18n";

const steps = [
  "builder.step.connection",
  "builder.step.mcc",
  "builder.step.accounts",
  "builder.step.creationMode",
  "builder.step.template",
  "builder.step.campaign",
  "builder.step.adGroup",
  "builder.step.audience",
  "builder.step.ads",
  "builder.step.count",
  "builder.step.budget",
  "builder.step.creatives",
  "builder.step.overrides",
  "builder.step.matrix",
  "builder.step.schedule",
  "builder.step.localValidation",
  "builder.step.googleValidation",
  "builder.step.financial",
  "builder.step.confirmation",
  "builder.step.creation",
  "builder.step.report"
];

type CreationMode = "FROM_TEMPLATE" | "FULL_SETUP" | "FROM_EXISTING" | "FILE";

export function executionModeLabel(mode: ExecutionMode): string {
  if (mode === "GOOGLE_TEST") return t("googleMode.testShort");
  if (mode === "PRODUCTION") return t("googleMode.productionShort");
  return t("googleMode.simulationLabel");
}

export function executionModeDescription(mode: ExecutionMode): string {
  if (mode === "GOOGLE_TEST") {
    return t("googleMode.testDescription");
  }
  if (mode === "PRODUCTION") {
    return t("googleMode.productionDescription");
  }
  return t("googleMode.simulationDescription");
}
type BuilderAccount = {
  id?: string;
  customer_id: string;
  account_name: string;
  currency_code: string;
  time_zone: string;
  campaigns_count?: number;
  overrides: Record<string, any>;
};

type BuilderForm = {
  execution_mode: ExecutionMode;
  creation_mode: CreationMode;
  template_id: string;
  batch_name: string;
  name_pattern: string;
  generation_seed: string;
  ad_type: "VIDEO" | "IMAGE" | "CAROUSEL";
  ad_group_name: string;
  business_name: string;
  final_url: string;
  mobile_final_url: string;
  tracking_template: string;
  final_url_suffix: string;
  display_path: string;
  custom_parameters: string;
  append_instance_parameter: boolean;
  start_date_time: string;
  end_date_time: string;
  bidding_strategy: "TARGET_CPA" | "MAXIMIZE_CONVERSIONS" | "TARGET_ROAS" | "MAXIMIZE_CLICKS";
  target_cpa: string;
  target_roas: string;
  conversion_actions: string;
  location_ids: string;
  excluded_location_ids: string;
  language_ids: string;
  audience_resource_names: string;
  user_list_resource_names: string;
  custom_audience_resource_names: string;
  user_interest_resource_names: string;
  life_event_ids: string;
  age_ranges: string[];
  genders: string[];
  parental_statuses: string[];
  income_ranges: string[];
  optimized_targeting: boolean;
  channel_mode: "ALL_CHANNELS" | "GOOGLE_OWNED" | "MANUAL";
  channels: Record<string, boolean>;
  headlines: string;
  long_headline: string;
  descriptions: string;
  carousel_card_headlines: string;
  call_to_action: string;
  youtube_video_id: string;
  media_ids: string[];
  logo_media_id: string;
  campaigns_per_account: number;
  copy_mode: string;
  budget_mode: "FIXED" | "RANGE" | "MANUAL_LIST" | "PER_ACCOUNT_OVERRIDE" | "PER_CAMPAIGN_OVERRIDE";
  budget_distribution: "BALANCED_RANDOM" | "RANDOM" | "SEQUENTIAL" | "MANUAL_AFTER_GENERATION";
  budget_fixed: string;
  budget_minimum: string;
  budget_maximum: string;
  budget_step: string;
  budget_manual_values: string;
  allow_repeats: boolean;
  password_confirmation: string;
};

export function createEmptyForm(): BuilderForm {
  return {
  execution_mode: "SIMULATION",
  creation_mode: "FROM_TEMPLATE",
  template_id: "",
  batch_name: `Demand Gen test ${new Date().toLocaleDateString(localeTag())}`,
  name_pattern: "{account_name}_{template_name}_{date}_{sequence}",
  generation_seed: "dgu-balanced-v1",
  ad_type: "VIDEO",
  ad_group_name: t("ui.5cd09a3025"),
  business_name: "Demo Brand",
  final_url: "https://example.com",
  mobile_final_url: "",
  tracking_template: "",
  final_url_suffix: "utm_source=dgu",
  display_path: "",
  custom_parameters: "",
  append_instance_parameter: false,
  start_date_time: "",
  end_date_time: "",
  bidding_strategy: "TARGET_CPA",
  target_cpa: "25",
  target_roas: "300",
  conversion_actions: "",
  location_ids: "2203",
  excluded_location_ids: "",
  language_ids: "1000",
  audience_resource_names: "",
  user_list_resource_names: "",
  custom_audience_resource_names: "",
  user_interest_resource_names: "",
  life_event_ids: "",
  age_ranges: ["AGE_RANGE_18_24", "AGE_RANGE_25_34", "AGE_RANGE_35_44"],
  genders: ["MALE", "FEMALE", "UNDETERMINED"],
  parental_statuses: [],
  income_ranges: [],
  optimized_targeting: true,
  channel_mode: "ALL_CHANNELS",
  channels: {
    youtube_in_stream: true,
    youtube_in_feed: true,
    youtube_shorts: true,
    discover: true,
    gmail: true,
    display: true,
    maps: false
  },
  headlines: t("ui.8cfbfe58bd"),
  long_headline: t("ui.1eb0692330"),
  descriptions: t("ui.8180b56500"),
  carousel_card_headlines: t("ui.58ba9ea2dd"),
  call_to_action: "LEARN_MORE",
  youtube_video_id: "dQw4w9WgXcQ",
  media_ids: [],
  logo_media_id: "",
  campaigns_per_account: 3,
  copy_mode: "SAME_SETTINGS_RANDOM_BUDGET",
  budget_mode: "RANGE",
  budget_distribution: "BALANCED_RANDOM",
  budget_fixed: "250",
  budget_minimum: "200",
  budget_maximum: "300",
  budget_step: "1",
  budget_manual_values: "",
  allow_repeats: true,
  password_confirmation: ""
  };
}

export function NewUploadPage({ navigate }: { navigate: Navigate }) {
  const [name, setName] = useState(`Demand Gen ${new Date().toLocaleDateString(localeTag())}`);
  const [mode, setMode] = useState<ExecutionMode>("SIMULATION");
  const create = useMutation({
    mutationFn: () => api.createUpload({ name, execution_mode: mode }),
    onSuccess: (upload) => navigate(`/uploads/${upload.id}`, true)
  });
  return (
    <Stack spacing={3} sx={{ maxWidth: 760 }}>
      <Typography variant="h4">{t("ui.7075f72219")}</Typography>
      {create.error && <Alert severity="error">{create.error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }}>
        <Stack spacing={3}>
          <TextField label={t("ui.3de49828e8")} value={name} onChange={(event) => setName(event.target.value)} fullWidth />
          <ToggleButtonGroup exclusive value={mode} onChange={(_, value) => value && setMode(value)} size="small">
            <ToggleButton value="SIMULATION">Simulation</ToggleButton>
            <ToggleButton value="GOOGLE_TEST">Google Test</ToggleButton>
            <ToggleButton value="PRODUCTION">Production</ToggleButton>
          </ToggleButtonGroup>
          <Alert severity={mode === "PRODUCTION" ? "error" : mode === "GOOGLE_TEST" ? "success" : "info"}>
            {executionModeDescription(mode)}
          </Alert>
          <Box>
            <Button
              variant="contained"
              startIcon={create.isPending ? <CircularProgress size={18} color="inherit" /> : <ArrowForwardIcon />}
              disabled={name.trim().length < 2 || create.isPending}
              onClick={() => create.mutate()}
            >
              {t("ui.e75d2f26e8")}</Button>
          </Box>
        </Stack>
      </Paper>
    </Stack>
  );
}

export function UploadWizardPage({ uploadId, navigate }: { uploadId: string; navigate: Navigate }) {
  const queryClient = useQueryClient();
  const uploadQuery = useQuery({ queryKey: ["upload", uploadId], queryFn: () => api.getUpload(uploadId) });
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const media = useQuery({ queryKey: ["media"], queryFn: api.listMedia });
  const plans = useQuery({ queryKey: ["plans"], queryFn: api.listPlans });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: api.getCapabilities });
  const domainValidation = useQuery({
    queryKey: ["domain-validation", uploadId],
    queryFn: () => api.getDomainValidation(uploadId),
    refetchInterval: (query) => query.state.data?.status === "PENDING" ? 1500 : false
  });
  const [form, setForm] = useState<BuilderForm>(() => createEmptyForm());
  const [selectedAccounts, setSelectedAccounts] = useState<BuilderAccount[]>([]);
  const [connectionId, setConnectionId] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [step, setStep] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [matrixFilter, setMatrixFilter] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [matrixEdits, setMatrixEdits] = useState<Record<string, { name: string; budget: string }>>({});
  const [bulkBudget, setBulkBudget] = useState("");
  const [youtubeInput, setYoutubeInput] = useState("");

  useEffect(() => {
    if (!uploadQuery.data || hydrated) return;
    const upload = uploadQuery.data;
    const builder = (upload.draft?.builder || {}) as Record<string, any>;
    setUploadName(upload.name);
    setConnectionId(upload.connection_id || "");
    setStep(Math.min(upload.current_step || 0, steps.length - 1));
    setBatchId(upload.draft?.launch_batch_id || null);
    setScheduleId(upload.draft?.schedule_id || null);
    setSelectedAccounts((builder.accounts || []).map(normalizeBuilderAccount));
    setForm(hydrateBuilderForm(upload.draft?.execution_mode || "SIMULATION", builder));
    setHydrated(true);
  }, [hydrated, uploadQuery.data]);

  const latestPlan = useMemo(
    () => (plans.data || [])
      .filter((item) => item.upload_id === uploadId && (!batchId || item.launch_batch_id === batchId))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
    [batchId, plans.data, uploadId]
  );
  useEffect(() => {
    if (!planId && latestPlan) setPlanId(latestPlan.id);
  }, [latestPlan, planId]);

  const batchQuery = useQuery({
    queryKey: ["launch-batch", batchId],
    queryFn: () => api.getLaunchBatch(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: 3000
  });
  const planQuery = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => api.getPlan(planId!),
    enabled: Boolean(planId),
    refetchInterval: (query) => ["QUEUED", "RUNNING"].includes(query.state.data?.status || "") ? 2000 : false
  });
  const batch = batchQuery.data;
  const activePlan = planQuery.data || (latestPlan?.id === planId ? latestPlan : undefined);

  const save = useMutation({
    mutationFn: (targetStep: number) => api.updateUpload(uploadId, {
      name: uploadName,
      connection_id: connectionId || null,
      current_step: targetStep,
      draft: {
        ...(uploadQuery.data?.draft || {}),
        execution_mode: form.execution_mode,
        source_mode: form.creation_mode === "FILE" ? "FILE" : "MANUAL",
        launch_batch_id: batchId,
        schedule_id: scheduleId,
        builder: buildBatchPayload(form, selectedAccounts)
      }
    }),
    onSuccess: (upload) => {
      queryClient.setQueryData(["upload", uploadId], upload);
      setNotice(t("ui.64ab0b5dce"));
    }
  });
  const generate = useMutation({
    mutationFn: async () => {
      await save.mutateAsync(13);
      return api.generateLaunchBatch(uploadId, buildBatchPayload(form, selectedAccounts));
    },
    onSuccess: (result) => {
      setBatchId(result.id);
      setScheduleId(null);
      setPlanId(null);
      queryClient.setQueryData(["launch-batch", result.id], result);
      queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
      queryClient.invalidateQueries({ queryKey: ["launch-batches"] });
      setSelectedRows([]);
      setMatrixEdits({});
      setNotice(t("upload.instancesGenerated", { count: result.campaigns_count }));
    }
  });
  const buildPlan = useMutation({
    mutationFn: () => api.buildPlan(uploadId, form.execution_mode, scheduleId),
    onSuccess: (plan) => {
      setPlanId(plan.id);
      queryClient.setQueryData(["plan", plan.id], plan);
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice(plan.local_validation.valid ? t("ui.e841f3fa00") : t("ui.31ffe8311b"));
    }
  });
  const validatePlan = useMutation({
    mutationFn: () => api.validatePlan(planId!),
    onSuccess: (result) => {
      queryClient.setQueryData(["plan", result.plan.id], result.plan);
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice(result.ok ? t("ui.2b60f8a282") : t("ui.c67a1047bc"));
    }
  });
  const confirmPlan = useMutation({
    mutationFn: () => api.confirmPlan(planId!),
    onSuccess: (result) => {
      queryClient.setQueryData(["plan", result.plan.id], result.plan);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setNotice(result.reused ? t("ui.77c2dc4228") : t("ui.b26405fdc7"));
      planQuery.refetch();
    }
  });
  const patchInstance = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, any> }) => api.patchCampaignInstance(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice(t("ui.0c82ce4869"));
    }
  });
  const importFile = useMutation({
    mutationFn: (file: File) => api.importUpload(uploadId, file),
    onSuccess: (result) => {
      queryClient.setQueryData(["upload", uploadId], result.upload);
      queryClient.invalidateQueries({ queryKey: ["domain-validation", uploadId] });
      setNotice(t("upload.rowsImported", { count: result.row_count }));
    }
  });
  const retryDomainValidation = useMutation({
    mutationFn: () => api.retryDomainValidation(uploadId),
    onSuccess: (result) => {
      queryClient.setQueryData(["domain-validation", uploadId], result.report);
      queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
      setNotice(result.reused ? t("domain.retryAlreadyRunning") : t("domain.retryStarted"));
    }
  });
  const uploadMedia = useMutation({
    mutationFn: api.uploadMedia,
    onSuccess: (asset) => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setForm((value) => ({ ...value, media_ids: [...new Set([...value.media_ids, asset.id])] }));
    }
  });
  const registerYoutube = useMutation({
    mutationFn: () => api.registerYoutube(youtubeInput),
    onSuccess: (asset) => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setForm((value) => ({
        ...value,
        youtube_video_id: asset.youtube_video_id || youtubeInput,
        media_ids: [...new Set([...value.media_ids, asset.id])]
      }));
      setYoutubeInput("");
    }
  });

  const mutationError = save.error || generate.error || buildPlan.error || validatePlan.error || confirmPlan.error ||
    patchInstance.error || importFile.error || uploadMedia.error || registerYoutube.error;
  if (uploadQuery.isLoading || !hydrated) return <CircularProgress />;
  if (uploadQuery.error) return <Alert severity="error">{uploadQuery.error.message}</Alert>;

  const set = <K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const move = async (next: number) => {
    await save.mutateAsync(next);
    setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const visibleAccounts = (accounts.data || []).filter((item) => !connectionId || item.connection_id === connectionId);
  const allInstances = (batch?.bundles || []).flatMap((item) => item.instances || []);
  const filteredInstances = allInstances.filter((item) => {
    const needle = matrixFilter.toLowerCase();
    return !needle || `${item.account_name} ${item.customer_id} ${item.campaign_name} ${item.status}`.toLowerCase().includes(needle);
  });
  const busy = [save, generate, buildPlan, validatePlan, confirmPlan, patchInstance].some((item) => item.isPending);

  return (
    <Stack spacing={2.5} sx={{ minWidth: 0 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" sx={{ overflowWrap: "anywhere" }}>{uploadName}</Typography>
          <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
            <StatusBadge value={uploadQuery.data!.status} />
            <Chip
              size="small"
              color={form.execution_mode === "PRODUCTION" ? "error" : form.execution_mode === "GOOGLE_TEST" ? "success" : "info"}
              label={executionModeLabel(form.execution_mode)}
            />
            {batch && <StatusBadge value={batch.status} />}
          </Stack>
        </Box>
        <Button variant="outlined" startIcon={<SaveOutlinedIcon />} disabled={busy} onClick={() => save.mutate(step)}>
          {t("ui.4864057d62")}</Button>
      </Box>
      {mutationError && <Alert severity="error">{mutationError.message}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}
      <DomainValidationPanel
        report={domainValidation.data}
        loading={domainValidation.isLoading || retryDomainValidation.isPending}
        error={domainValidation.error?.message || retryDomainValidation.error?.message}
        onRetry={() => retryDomainValidation.mutate()}
      />

      <Paper variant="outlined" sx={{ overflow: "hidden", minWidth: 0 }}>
        <Box sx={{ overflowX: "auto", px: 2, pt: 2 }}>
          <Stepper nonLinear activeStep={step} sx={{ minWidth: 2500 }}>
            {steps.map((labelKey, index) => (
              <Step key={labelKey} completed={index < step}>
                <StepButton onClick={() => move(index)}>{index + 1}. {t(labelKey)}</StepButton>
              </Step>
            ))}
          </Stepper>
        </Box>
        <Divider sx={{ mt: 2 }} />
        <Box sx={{ p: { xs: 2, sm: 3 }, minHeight: 470 }}>
          <BuilderStep
            step={step}
            form={form}
            set={set}
            uploadName={uploadName}
            setUploadName={setUploadName}
            connectionId={connectionId}
            setConnectionId={setConnectionId}
            connections={connections.data || []}
            accounts={visibleAccounts}
            selectedAccounts={selectedAccounts}
            setSelectedAccounts={setSelectedAccounts}
            templates={templates.data || []}
            media={media.data || []}
            capabilities={capabilities.data?.fields || []}
            batch={batch}
            plan={activePlan}
            domainValidation={
              (activePlan?.snapshot.domain_validation as DomainValidationReport | undefined)
              || domainValidation.data
            }
            allInstances={allInstances}
            filteredInstances={filteredInstances}
            matrixFilter={matrixFilter}
            setMatrixFilter={setMatrixFilter}
            selectedRows={selectedRows}
            setSelectedRows={setSelectedRows}
            matrixEdits={matrixEdits}
            setMatrixEdits={setMatrixEdits}
            bulkBudget={bulkBudget}
            setBulkBudget={setBulkBudget}
            confirmed={confirmed}
            setConfirmed={setConfirmed}
            youtubeInput={youtubeInput}
            setYoutubeInput={setYoutubeInput}
            busy={busy}
            onGenerate={() => generate.mutate()}
            onBuildPlan={() => buildPlan.mutate()}
            onValidate={() => validatePlan.mutate()}
            onConfirm={() => confirmPlan.mutate()}
            onPatch={(id, payload) => patchInstance.mutate({ id, payload })}
            onImport={(file) => importFile.mutate(file)}
            onUploadMedia={(file) => uploadMedia.mutate(file)}
            onRegisterYoutube={() => registerYoutube.mutate()}
            scheduleId={scheduleId}
            onScheduleCreated={(schedule) => {
              setScheduleId(schedule.id);
              queryClient.setQueryData(["schedule", schedule.id], schedule);
              queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
              setNotice(t("ui.9492b28ded"));
            }}
            navigate={navigate}
          />
        </Box>
        <Divider />
        <Box sx={{ p: 2, display: "flex", justifyContent: "space-between", gap: 2 }}>
          <Button startIcon={<ArrowBackIcon />} disabled={step === 0 || busy} onClick={() => move(step - 1)}>
            {t("ui.f6dab074d7")}</Button>
          {step < steps.length - 1 && (
            <Button variant="contained" endIcon={<ArrowForwardIcon />} disabled={busy} onClick={() => move(step + 1)}>
              {t("ui.9c24f10191")}</Button>
          )}
        </Box>
      </Paper>
    </Stack>
  );
}

type BuilderStepProps = {
  step: number;
  form: BuilderForm;
  set: <K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) => void;
  uploadName: string;
  setUploadName: (value: string) => void;
  connectionId: string;
  setConnectionId: (value: string) => void;
  connections: GoogleConnection[];
  accounts: CustomerAccount[];
  selectedAccounts: BuilderAccount[];
  setSelectedAccounts: (value: BuilderAccount[]) => void;
  templates: Array<{ id: string; name: string; current_version: number }>;
  media: MediaAsset[];
  capabilities: Array<Record<string, any>>;
  batch?: LaunchBatch;
  plan?: DeploymentPlan;
  domainValidation?: DomainValidationReport;
  allInstances: CampaignInstance[];
  filteredInstances: CampaignInstance[];
  matrixFilter: string;
  setMatrixFilter: (value: string) => void;
  selectedRows: string[];
  setSelectedRows: (value: string[]) => void;
  matrixEdits: Record<string, { name: string; budget: string }>;
  setMatrixEdits: (value: Record<string, { name: string; budget: string }>) => void;
  bulkBudget: string;
  setBulkBudget: (value: string) => void;
  confirmed: boolean;
  setConfirmed: (value: boolean) => void;
  youtubeInput: string;
  setYoutubeInput: (value: string) => void;
  busy: boolean;
  onGenerate: () => void;
  onBuildPlan: () => void;
  onValidate: () => void;
  onConfirm: () => void;
  onPatch: (id: string, payload: Record<string, any>) => void;
  onImport: (file: File) => void;
  onUploadMedia: (file: File) => void;
  onRegisterYoutube: () => void;
  scheduleId: string | null;
  onScheduleCreated: (schedule: import("../api/client").DeploymentSchedule) => void;
  navigate: Navigate;
};

function BuilderStep(props: BuilderStepProps) {
  const { step, form, set } = props;
  if (step === 0) return (
    <StepSection title={t("builder.step.connection")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("ui.7924c4c015")} value={props.uploadName} onChange={(e) => props.setUploadName(e.target.value)} /></Grid>
        <Grid item xs={12} md={6}>
          <ToggleButtonGroup exclusive size="small" value={form.execution_mode} onChange={(_, value) => value && set("execution_mode", value)}>
            <ToggleButton value="SIMULATION">Simulation</ToggleButton>
            <ToggleButton value="GOOGLE_TEST">Google Test</ToggleButton>
            <ToggleButton value="PRODUCTION">Production</ToggleButton>
          </ToggleButtonGroup>
        </Grid>
        <Grid item xs={12} md={6}>
          <FormControl fullWidth><InputLabel>{t("ui.79e350f743")}</InputLabel><Select label={t("ui.79e350f743")} value={props.connectionId} onChange={(e) => props.setConnectionId(e.target.value)}><MenuItem value="">{t("ui.fad95c5cb0")}</MenuItem>{props.connections.filter((item) => form.execution_mode === "SIMULATION" || item.connection_mode === form.execution_mode).map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {executionModeLabel(item.connection_mode)} · {item.status}</MenuItem>)}</Select></FormControl>
        </Grid>
      </Grid>
      <Alert severity={form.execution_mode === "PRODUCTION" ? "error" : form.execution_mode === "GOOGLE_TEST" ? "success" : "info"}>{executionModeDescription(form.execution_mode)}</Alert>
    </StepSection>
  );
  if (step === 1) {
    const selected = props.connections.find((item) => item.id === props.connectionId);
    return <StepSection title={t("builder.step.mcc")}><InfoTable rows={[[t("ui.79e350f743"), selected?.name || t("ui.92250813ce")], [t("field.loginCustomerId"), selected?.login_customer_id || "—"], [t("ui.f7f293b5c5"), selected?.status || "SIMULATION"]]} /></StepSection>;
  }
  if (step === 2) return <AccountsStep {...props} />;
  if (step === 3) return (
    <StepSection title={t("ui.80273e4838")}>
      <ToggleButtonGroup exclusive value={form.creation_mode} onChange={(_, value) => value && set("creation_mode", value)} sx={{ flexWrap: "wrap" }}>
        <ToggleButton value="FROM_TEMPLATE">{t("ui.0f525e514f")}</ToggleButton><ToggleButton value="FULL_SETUP">{t("ui.c1d422cb61")}</ToggleButton><ToggleButton value="FROM_EXISTING">{t("ui.7a7e9452a3")}</ToggleButton><ToggleButton value="FILE">CSV / XLSX</ToggleButton>
      </ToggleButtonGroup>
      {form.creation_mode === "FILE" && <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />}>{t("ui.eee147777a")}<input hidden type="file" accept=".csv,.xlsx,.xlsm" onChange={(e) => e.target.files?.[0] && props.onImport(e.target.files[0])} /></Button>}
      {form.creation_mode === "FROM_EXISTING" && <Alert severity="info">{t("ui.8eb86afb6a")}</Alert>}
    </StepSection>
  );
  if (step === 4) return (
    <StepSection title={t("ui.14b700a309")}>
      <FormControl fullWidth sx={{ maxWidth: 620 }}><InputLabel>{t("ui.7bd54e8998")}</InputLabel><Select label={t("ui.7bd54e8998")} value={form.template_id} onChange={(e) => set("template_id", e.target.value)}><MenuItem value="">{t("ui.1786536fe3")}</MenuItem>{props.templates.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · v{item.current_version}</MenuItem>)}</Select></FormControl>
      <TextField fullWidth label={t("ui.9d6646ca4e")} value={form.batch_name} onChange={(e) => set("batch_name", e.target.value)} />
      <TextField fullWidth label={t("ui.01201ebdfc")} value={form.name_pattern} onChange={(e) => set("name_pattern", e.target.value)} helperText="{account_name} {customer_id} {template_name} {batch_name} {date} {time} {sequence} {budget} {creative_set} {random_suffix}" />
      <TextField label={t("field.generationSeed")} value={form.generation_seed} onChange={(e) => set("generation_seed", e.target.value)} sx={{ maxWidth: 420 }} />
    </StepSection>
  );
  if (step === 5) return <CampaignSettingsStep {...props} />;
  if (step === 6) return <AdGroupStep {...props} />;
  if (step === 7) return <AudienceStep {...props} />;
  if (step === 8) return <AdsAssetsStep {...props} />;
  if (step === 9) return <CampaignCountStep {...props} />;
  if (step === 10) return <BudgetGeneratorStep {...props} />;
  if (step === 11) return <CreativeDistributionStep {...props} />;
  if (step === 12) return <AccountOverridesStep {...props} />;
  if (step === 13) return <CampaignMatrixStep {...props} />;
  if (step === 14) return (
    <StepSection title={t("ui.f04bd0a064")}>
      <ScheduleEditor batch={props.batch} scheduleId={props.scheduleId} onCreated={props.onScheduleCreated} />
    </StepSection>
  );
  if (step === 15) return <LocalValidationStep {...props} />;
  if (step === 16) return <GoogleValidationStep {...props} />;
  if (step === 17) return <FinancialStep {...props} />;
  if (step === 18) return (
    <StepSection title={t("ui.846aff7071")}>
      <FinancialSummary batch={props.batch} />
      <DomainValidationPanel report={props.domainValidation} compact />
      <FormControlLabel control={<Checkbox checked={props.confirmed} onChange={(e) => props.setConfirmed(e.target.checked)} />} label={t("ui.c2917d9e32")} />
      <TextField type="password" label={t("ui.d78097f97a")} value={form.password_confirmation} onChange={(e) => set("password_confirmation", e.target.value)} sx={{ maxWidth: 440 }} />
    </StepSection>
  );
  if (step === 19) return <CreationStep {...props} />;
  return <ReportStep {...props} />;
}

function AccountsStep(props: BuilderStepProps) {
  const selectedIds = new Set(props.selectedAccounts.map((item) => item.customer_id));
  const toggle = (account: CustomerAccount) => {
    if (selectedIds.has(account.customer_id)) props.setSelectedAccounts(props.selectedAccounts.filter((item) => item.customer_id !== account.customer_id));
    else props.setSelectedAccounts([...props.selectedAccounts, normalizeBuilderAccount(account)]);
  };
  const addTestAccounts = () => props.setSelectedAccounts(Array.from({ length: 20 }, (_, index) => ({
    customer_id: String(9000000001 + index),
    account_name: `CZ-${501 + index} · Test account`,
    currency_code: "USD",
    time_zone: "Europe/Prague",
    campaigns_count: props.form.campaigns_per_account,
    overrides: {}
  })));
  return (
    <StepSection title={t("ui.e9af21d100")}>
      {props.form.execution_mode === "SIMULATION" && <Button variant="outlined" startIcon={<ScienceOutlinedIcon />} onClick={addTestAccounts}>{t("ui.c0e7c09f72")}</Button>}
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}><Chip label={t("upload.selectedCount", { count: props.selectedAccounts.length })} /><Chip label={t("upload.currencies", { currencies: [...new Set(props.selectedAccounts.map((item) => item.currency_code))].join(", ") || "—" })} /></Stack>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>{t("ui.5b16fcdd97")}</TableCell><TableCell>Customer ID</TableCell><TableCell>{t("ui.18be059f5f")}</TableCell><TableCell>{t("ui.47947a0c46")}</TableCell></TableRow></TableHead><TableBody>
          {props.accounts.map((item) => <TableRow key={item.id} hover><TableCell padding="checkbox"><Checkbox checked={selectedIds.has(item.customer_id)} onChange={() => toggle(item)} /></TableCell><TableCell>{item.descriptive_name || t("ui.32b74a3c47")}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code || "—"}</TableCell><TableCell>{item.time_zone || "—"}</TableCell></TableRow>)}
          {!props.accounts.length && !props.selectedAccounts.length && <TableRow><TableCell colSpan={5}>{t("ui.9de2e07fbf")}</TableCell></TableRow>}
          {props.selectedAccounts.filter((item) => !props.accounts.some((account) => account.customer_id === item.customer_id)).map((item) => <TableRow key={item.customer_id}><TableCell padding="checkbox"><Checkbox checked onChange={() => props.setSelectedAccounts(props.selectedAccounts.filter((row) => row.customer_id !== item.customer_id))} /></TableCell><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code}</TableCell><TableCell>{item.time_zone}</TableCell></TableRow>)}
        </TableBody></Table>
      </Box>
    </StepSection>
  );
}

function CampaignSettingsStep({ form, set, capabilities }: BuilderStepProps) {
  return (
    <StepSection title={t("builder.step.campaign")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>{t("ui.24cf56a313")}</InputLabel><Select label={t("ui.24cf56a313")} value={form.bidding_strategy} onChange={(e) => set("bidding_strategy", e.target.value as BuilderForm["bidding_strategy"])}><MenuItem value="TARGET_CPA">{t("field.targetCpa")}</MenuItem><MenuItem value="MAXIMIZE_CONVERSIONS">{t("option.maximizeConversions")}</MenuItem><MenuItem value="TARGET_ROAS">{t("field.targetRoas")}</MenuItem><MenuItem value="MAXIMIZE_CLICKS">{t("option.maximizeClicks")}</MenuItem><MenuItem disabled value="MAXIMIZE_CONVERSION_VALUE">{t("ui.81699af962")}</MenuItem></Select></FormControl></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label={t("field.targetCpa")} value={form.target_cpa} onChange={(e) => set("target_cpa", e.target.value)} /></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label={t("field.targetRoas")} value={form.target_roas} onChange={(e) => set("target_roas", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth label={t("field.conversionActions")} value={form.conversion_actions} onChange={(e) => set("conversion_actions", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth type="datetime-local" label={t("ui.cb26bdc6c6")} InputLabelProps={{ shrink: true }} value={form.start_date_time} onChange={(e) => set("start_date_time", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth type="datetime-local" label={t("ui.ec5bfc700b")} InputLabelProps={{ shrink: true }} value={form.end_date_time} onChange={(e) => set("end_date_time", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.trackingTemplate")} value={form.tracking_template} onChange={(e) => set("tracking_template", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.finalUrlSuffix")} value={form.final_url_suffix} onChange={(e) => set("final_url_suffix", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.mobileFinalUrl")} value={form.mobile_final_url} onChange={(e) => set("mobile_final_url", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.displayPath")} value={form.display_path} onChange={(e) => set("display_path", e.target.value)} helperText={t("builder.url.displayPathHelp")} /></Grid>
        <Grid item xs={12}><TextField fullWidth multiline minRows={2} label={t("field.customParameters")} value={form.custom_parameters} onChange={(e) => set("custom_parameters", e.target.value)} helperText={t("builder.url.customParametersHelp")} /></Grid>
      </Grid>
      <FormControlLabel
        control={<Checkbox checked={form.append_instance_parameter} onChange={(e) => set("append_instance_parameter", e.target.checked)} />}
        label={t("ui.1db8937e85")}
      />
      <Typography variant="caption" color="text.secondary">{t("ui.d843b0fcc8")}{" "}{"{campaignid}"}{t("ui.549df07677")}</Typography>
      <Alert severity="info">{t("ui.3e7da9d996")}</Alert>
      <CapabilityStrip capabilities={capabilities} prefix="campaign." />
    </StepSection>
  );
}

function AdGroupStep({ form, set, capabilities }: BuilderStepProps) {
  return (
    <StepSection title={t("builder.step.adGroup")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("ui.22d67742ad")} value={form.ad_group_name} onChange={(e) => set("ad_group_name", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label={t("field.geoIds")} value={form.location_ids} onChange={(e) => set("location_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label={t("ui.4239db2d5f")} value={form.excluded_location_ids} onChange={(e) => set("excluded_location_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth label={t("field.languageIds")} value={form.language_ids} onChange={(e) => set("language_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={8}><FormControl fullWidth><InputLabel>{t("field.channelControls")}</InputLabel><Select label={t("field.channelControls")} value={form.channel_mode} onChange={(e) => set("channel_mode", e.target.value as BuilderForm["channel_mode"])}><MenuItem value="ALL_CHANNELS">{t("ui.a745f4e319")}</MenuItem><MenuItem value="GOOGLE_OWNED">{t("ui.425453d2ea")}</MenuItem><MenuItem value="MANUAL">{t("ui.3711716b26")}</MenuItem></Select></FormControl></Grid>
      </Grid>
      {form.channel_mode === "MANUAL" && <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap" }}>{channelLabels.map(([key, label]) => <FormControlLabel key={key} control={<Checkbox checked={Boolean(form.channels[key])} disabled={key === "maps"} onChange={(e) => set("channels", { ...form.channels, [key]: e.target.checked })} />} label={key === "maps" ? t("capability.unavailable", { label }) : label} />)}</Stack>}
      <CapabilityStrip capabilities={capabilities} prefix="channels." />
    </StepSection>
  );
}

function AudienceStep(props: BuilderStepProps) {
  const { form, set } = props;
  const [catalog, setCatalog] = useState<Record<string, any> | null>(null);
  const [catalogSearch, setCatalogSearch] = useState("");
  const catalogAccountId = props.selectedAccounts.find((item) => item.id)?.id;
  const loadCatalog = useMutation({
    mutationFn: () => api.getAccountCatalog(catalogAccountId!),
    onSuccess: setCatalog
  });
  const selectedInterests = splitValues(form.user_interest_resource_names);
  const selectedLifeEvents = splitValues(form.life_event_ids);
  const catalogItems = ((catalog?.user_interests || []) as Array<Record<string, any>>)
    .filter((item) => !catalogSearch.trim() ||
      `${item.name || ""} ${item.taxonomy_type || ""}`.toLocaleLowerCase().includes(catalogSearch.trim().toLocaleLowerCase()))
    .slice(0, 100);
  const addCatalogItem = (item: Record<string, any>) => {
    if (item.taxonomy_type === "LIFE_EVENT") {
      set("life_event_ids", [...new Set([...selectedLifeEvents, String(item.user_interest_id)])].join("\n"));
      return;
    }
    set("user_interest_resource_names", [...new Set([...selectedInterests, String(item.resource_name)])].join("\n"));
  };
  return (
    <StepSection title={t("ui.c8092d2f64")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label={t("field.audienceResources")} value={form.audience_resource_names} onChange={(e) => set("audience_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label={t("field.userList")} value={form.user_list_resource_names} onChange={(e) => set("user_list_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label={t("field.customAudienceResources")} value={form.custom_audience_resource_names} onChange={(e) => set("custom_audience_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label={t("builder.field.userInterests")} value={form.user_interest_resource_names} onChange={(e) => set("user_interest_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label={t("builder.field.lifeEvents")} value={form.life_event_ids} onChange={(e) => set("life_event_ids", e.target.value)} /></Grid>
      </Grid>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
        <Button variant="outlined" startIcon={<RefreshIcon />} disabled={!catalogAccountId || loadCatalog.isPending} onClick={() => loadCatalog.mutate()}>{t("builder.audience.loadCatalog")}</Button>
        {catalog && <TextField size="small" label={t("builder.audience.catalogSearch")} value={catalogSearch} onChange={(event) => setCatalogSearch(event.target.value)} sx={{ minWidth: 300 }} />}
      </Stack>
      {!catalogAccountId && <Alert severity="info">{t("builder.audience.selectAccountFirst")}</Alert>}
      {loadCatalog.error && <Alert severity="error">{loadCatalog.error.message}</Alert>}
      {catalog && <Box sx={{ maxHeight: 300, overflow: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small">
          <TableHead><TableRow><TableCell>{t("common.name")}</TableCell><TableCell>{t("ui.d25691ca40")}</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {catalogItems.map((item) => {
              const selected = item.taxonomy_type === "LIFE_EVENT"
                ? selectedLifeEvents.includes(String(item.user_interest_id))
                : selectedInterests.includes(String(item.resource_name));
              return <TableRow key={String(item.resource_name)}><TableCell>{String(item.name || item.user_interest_id)}</TableCell><TableCell>{String(item.taxonomy_type || "UNKNOWN")}</TableCell><TableCell align="right"><Button size="small" disabled={selected} onClick={() => addCatalogItem(item)}>{selected ? t("builder.audience.added") : t("common.add")}</Button></TableCell></TableRow>;
            })}
            {!catalogItems.length && <TableRow><TableCell colSpan={3}>{t("builder.audience.emptyCatalog")}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Box>}
      <ChoiceChecks label={t("ui.f73f17a2bf")} values={ageOptions} selected={form.age_ranges} onChange={(value) => set("age_ranges", value)} />
      <ChoiceChecks label={t("ui.31c8bce4fe")} values={genderOptions} selected={form.genders} onChange={(value) => set("genders", value)} />
      <ChoiceChecks label={t("builder.field.parentalStatus")} values={parentalOptions} selected={form.parental_statuses} onChange={(value) => set("parental_statuses", value)} />
      <ChoiceChecks label={t("builder.field.incomeRange")} values={incomeOptions} selected={form.income_ranges} onChange={(value) => set("income_ranges", value)} />
      <FormControlLabel control={<Checkbox checked={form.optimized_targeting} onChange={(e) => set("optimized_targeting", e.target.checked)} />} label={t("ui.9456363417")} />
      <Alert severity="info">{t("ui.743bb69eb0")}</Alert>
    </StepSection>
  );
}

function AdsAssetsStep(props: BuilderStepProps) {
  const { form, set } = props;
  const selectedLogoOptions = props.media.filter((item) =>
    form.media_ids.includes(item.id) &&
    item.kind === "IMAGE" &&
    item.status === "READY" &&
    Boolean(item.width && item.height && item.width === item.height)
  );
  const toggleMedia = (item: MediaAsset) => {
    const removing = form.media_ids.includes(item.id);
    set("media_ids", removing ? form.media_ids.filter((id) => id !== item.id) : [...form.media_ids, item.id]);
    if (removing && form.logo_media_id === item.id) set("logo_media_id", "");
  };
  const selectLogo = (mediaId: string) => {
    if (mediaId && !form.media_ids.includes(mediaId)) set("media_ids", [...form.media_ids, mediaId]);
    set("logo_media_id", mediaId);
  };
  return (
    <StepSection title={t("ui.9edf62a387")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={3}><FormControl fullWidth><InputLabel>{t("ui.b9563c38ab")}</InputLabel><Select label={t("ui.b9563c38ab")} value={form.ad_type} onChange={(e) => set("ad_type", e.target.value as BuilderForm["ad_type"])}><MenuItem value="VIDEO">{t("option.videoResponsive")}</MenuItem><MenuItem value="IMAGE">{t("option.multiAsset")}</MenuItem><MenuItem value="CAROUSEL">{t("option.carousel")}</MenuItem></Select></FormControl></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label={t("field.businessName")} value={form.business_name} inputProps={{ maxLength: 25 }} onChange={(e) => set("business_name", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.finalUrl")} value={form.final_url} onChange={(e) => set("final_url", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label={t("ui.e3917b6fa1")} value={form.headlines} onChange={(e) => set("headlines", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label={t("ui.eabed68dff")} value={form.descriptions} onChange={(e) => set("descriptions", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("field.longHeadline")} value={form.long_headline} onChange={(e) => set("long_headline", e.target.value)} /></Grid>
        {form.ad_type === "CAROUSEL" && <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label={t("builder.field.carouselHeadlines")} value={form.carousel_card_headlines} onChange={(e) => set("carousel_card_headlines", e.target.value)} /></Grid>}
        <Grid item xs={12} md={3}><TextField fullWidth label={t("field.youtubeVideoId")} value={form.youtube_video_id} onChange={(e) => set("youtube_video_id", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><FormControl fullWidth><InputLabel>{t("field.callToAction")}</InputLabel><Select label={t("field.callToAction")} value={form.call_to_action} onChange={(e) => set("call_to_action", e.target.value)}>{["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "APPLY_NOW", "GET_QUOTE"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>{t("builder.field.logo")}</InputLabel>
            <Select label={t("builder.field.logo")} value={form.logo_media_id} onChange={(e) => selectLogo(String(e.target.value))}>
              <MenuItem value="">{t("builder.assets.selectLogo")}</MenuItem>
              {selectedLogoOptions.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.width} x {item.height}</MenuItem>)}
            </Select>
          </FormControl>
        </Grid>
      </Grid>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <TextField label={t("ui.94ade8a20a")} value={props.youtubeInput} onChange={(e) => props.setYoutubeInput(e.target.value)} sx={{ flex: 1 }} />
        <Button variant="outlined" startIcon={<YouTubeIcon />} disabled={!props.youtubeInput || props.busy} onClick={props.onRegisterYoutube}>{t("ui.559a87f7cc")}</Button>
        <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={props.busy}>{t("ui.d381669265")}<input hidden type="file" accept="image/png,image/jpeg,video/mp4,video/quicktime,video/webm" onChange={(e) => e.target.files?.[0] && props.onUploadMedia(e.target.files[0])} /></Button>
      </Stack>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>{t("common.asset")}</TableCell><TableCell>{t("ui.d25691ca40")}</TableCell><TableCell>{t("ui.98713e8814")}</TableCell><TableCell>{t("builder.assets.role")}</TableCell><TableCell>{t("ui.f7f293b5c5")}</TableCell></TableRow></TableHead><TableBody>{props.media.map((item) => <TableRow key={item.id}><TableCell padding="checkbox"><Checkbox checked={form.media_ids.includes(item.id)} onChange={() => toggleMedia(item)} /></TableCell><TableCell>{item.name}</TableCell><TableCell>{item.kind}</TableCell><TableCell>{item.width && item.height ? `${item.width} x ${item.height}` : item.duration_seconds ? t("media.durationSeconds", { count: formatNumber(item.duration_seconds, { maximumFractionDigits: 1 }) }) : "—"}</TableCell><TableCell>{form.logo_media_id === item.id ? t("builder.assets.logoSelected") : mediaRoleLabel(item)}</TableCell><TableCell><StatusBadge value={item.status} /></TableCell></TableRow>)}</TableBody></Table></Box>
      {!form.logo_media_id && <Alert severity="warning">{t("builder.assets.logoRequired")}</Alert>}
      <Alert severity="info">{t("builder.assets.previewUnavailable")}</Alert>
    </StepSection>
  );
}

function BudgetGeneratorStep({ form, set }: BuilderStepProps) {
  return (
    <StepSection title={t("ui.4b6192d1c8")}>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>{t("ui.ff0fbd56f4")}</InputLabel><Select label={t("ui.ff0fbd56f4")} value={form.budget_mode} onChange={(e) => set("budget_mode", e.target.value as BuilderForm["budget_mode"])}>{["FIXED", "RANGE", "MANUAL_LIST", "PER_ACCOUNT_OVERRIDE", "PER_CAMPAIGN_OVERRIDE"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>{t("ui.1aff9ed9b2")}</InputLabel><Select label={t("ui.1aff9ed9b2")} value={form.budget_distribution} onChange={(e) => set("budget_distribution", e.target.value as BuilderForm["budget_distribution"])}>{["BALANCED_RANDOM", "RANDOM", "SEQUENTIAL", "MANUAL_AFTER_GENERATION"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label={t("field.fixed")} value={form.budget_fixed} onChange={(e) => set("budget_fixed", e.target.value)} /></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label={t("ui.ee899dd5cc")} value={form.budget_step} onChange={(e) => set("budget_step", e.target.value)} /></Grid>
        <Grid item xs={6} md={3}><TextField fullWidth type="number" label={t("ui.54ddf3d43e")} value={form.budget_minimum} onChange={(e) => set("budget_minimum", e.target.value)} /></Grid>
        <Grid item xs={6} md={3}><TextField fullWidth type="number" label={t("ui.c6ba85417d")} value={form.budget_maximum} onChange={(e) => set("budget_maximum", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label={t("ui.4287a7976f")} value={form.budget_manual_values} onChange={(e) => set("budget_manual_values", e.target.value)} /></Grid>
      </Grid>
      <FormControlLabel control={<Checkbox checked={form.allow_repeats} onChange={(e) => set("allow_repeats", e.target.checked)} />} label={t("ui.3c476800b6")} />
      <Alert severity="info">{t("ui.df97077380")}</Alert>
    </StepSection>
  );
}

function CampaignCountStep(props: BuilderStepProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkCount, setBulkCount] = useState(String(props.form.campaigns_per_account));
  const quickCounts = QUICK_CAMPAIGN_COUNTS;
  const updateAccounts = (ids: string[] | null, value: number) => {
    const count = normalizeCampaignCount(value);
    props.setSelectedAccounts(applyCampaignCount(props.selectedAccounts, ids, count));
    if (ids === null) props.set("campaigns_per_account", count);
  };
  const total = props.selectedAccounts.reduce(
    (sum, item) => sum + (item.campaigns_count || props.form.campaigns_per_account),
    0
  );
  const allSelected = props.selectedAccounts.length > 0 && props.selectedAccounts.every((item) => selectedIds.includes(item.customer_id));
  return (
    <StepSection title={t("ui.230537b9a2")}>
      <FormControl sx={{ minWidth: 360 }}>
        <InputLabel>{t("ui.ca498ad7f0")}</InputLabel>
        <Select label={t("ui.ca498ad7f0")} value={props.form.copy_mode} onChange={(event) => props.set("copy_mode", event.target.value)}>
          {copyModes.map(([value, labelKey]) => <MenuItem key={value} value={value}>{t(labelKey)}</MenuItem>)}
        </Select>
      </FormControl>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
        <TextField
          type="number"
          size="small"
          label={t("ui.ac996ae319")}
          value={props.form.campaigns_per_account}
          inputProps={{ min: 1, max: 500 }}
          onChange={(event) => props.set("campaigns_per_account", normalizeCampaignCount(Number(event.target.value)))}
          sx={{ width: 230 }}
        />
        <Button variant="outlined" onClick={() => updateAccounts(null, props.form.campaigns_per_account)}>{t("ui.679bd2d438")}</Button>
        <ToggleButtonGroup exclusive size="small" aria-label={t("ui.d567f69de6")}>
          {quickCounts.map((count) => <ToggleButton key={count} value={count} onClick={() => updateAccounts(null, count)}>{count}</ToggleButton>)}
        </ToggleButtonGroup>
      </Stack>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
        <TextField type="number" size="small" label={t("ui.c4c7b44944")} value={bulkCount} inputProps={{ min: 1, max: 500 }} onChange={(event) => setBulkCount(event.target.value)} sx={{ width: 190 }} />
        <Button variant="contained" disabled={!selectedIds.length} onClick={() => updateAccounts(selectedIds, Number(bulkCount))}>{t("ui.33ecf3ea24")}</Button>
        <ToggleButtonGroup exclusive size="small" aria-label={t("ui.a13cb6b088")}>
          {quickCounts.map((count) => <ToggleButton key={count} value={count} disabled={!selectedIds.length} onClick={() => updateAccounts(selectedIds, count)}>{count}</ToggleButton>)}
        </ToggleButtonGroup>
      </Stack>
      <InfoTable rows={[[t("ui.8bc2e747ff"), props.selectedAccounts.length], [t("ui.813654a42f"), total]]} />
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small" sx={{ minWidth: 940 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox"><Checkbox checked={allSelected} onChange={(event) => setSelectedIds(event.target.checked ? props.selectedAccounts.map((item) => item.customer_id) : [])} /></TableCell>
              <TableCell>{t("ui.5b16fcdd97")}</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>{t("ui.65739df6c0")}</TableCell>
              <TableCell>{t("ui.74d2c71605")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.selectedAccounts.map((item) => {
              const count = item.campaigns_count || props.form.campaigns_per_account;
              return (
                <TableRow key={item.customer_id}>
                  <TableCell padding="checkbox"><Checkbox checked={selectedIds.includes(item.customer_id)} onChange={(event) => setSelectedIds(event.target.checked ? [...selectedIds, item.customer_id] : selectedIds.filter((id) => id !== item.customer_id))} /></TableCell>
                  <TableCell>{item.account_name}</TableCell>
                  <TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell>
                  <TableCell><ToggleButtonGroup exclusive size="small" value={quickCounts.some((value) => value === count) ? count : null} onChange={(_, value) => value && updateAccounts([item.customer_id], value)}>{quickCounts.map((value) => <ToggleButton key={value} value={value}>{value}</ToggleButton>)}</ToggleButtonGroup></TableCell>
                  <TableCell><TextField size="small" type="number" value={count} inputProps={{ min: 1, max: 500 }} onChange={(event) => updateAccounts([item.customer_id], Number(event.target.value))} sx={{ width: 130 }} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>
    </StepSection>
  );
}

function CreativeDistributionStep({ form, set, media }: BuilderStepProps) {
  return (
    <StepSection title={t("ui.21a8b879e3")}>
      <FormControl sx={{ minWidth: 380 }}><InputLabel>{t("field.copyMode")}</InputLabel><Select label={t("field.copyMode")} value={form.copy_mode} onChange={(e) => set("copy_mode", e.target.value)}>{copyModes.map(([value, labelKey]) => <MenuItem key={value} value={value}>{t(labelKey)}</MenuItem>)}</Select></FormControl>
      <InfoTable rows={[[t("ui.0212ec2cf4"), form.media_ids.length], [t("ui.abd0ba2902"), media.filter((item) => item.status === "READY").length], [t("ui.633e83237b"), t("ui.7ef952fa2c")]]} />
    </StepSection>
  );
}

function AccountOverridesStep(props: BuilderStepProps) {
  const update = (index: number, patch: Partial<BuilderAccount>) => props.setSelectedAccounts(props.selectedAccounts.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  return (
    <StepSection title={t("builder.step.overrides")}>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell>{t("ui.5b16fcdd97")}</TableCell><TableCell>Customer ID</TableCell><TableCell>{t("ui.cf645a44e5")}</TableCell><TableCell>{t("ui.18be059f5f")}</TableCell><TableCell>{t("ui.47947a0c46")}</TableCell></TableRow></TableHead><TableBody>{props.selectedAccounts.map((item, index) => <TableRow key={item.customer_id}><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell><TextField size="small" type="number" value={item.campaigns_count || props.form.campaigns_per_account} inputProps={{ min: 1, max: 500 }} onChange={(e) => update(index, { campaigns_count: Number(e.target.value) })} sx={{ width: 100 }} /></TableCell><TableCell><TextField size="small" value={item.currency_code} disabled={props.form.execution_mode !== "SIMULATION"} onChange={(e) => update(index, { currency_code: e.target.value.toUpperCase() })} sx={{ width: 100 }} /></TableCell><TableCell><TextField size="small" value={item.time_zone} disabled={props.form.execution_mode !== "SIMULATION"} onChange={(e) => update(index, { time_zone: e.target.value })} sx={{ width: 190 }} /></TableCell></TableRow>)}</TableBody></Table></Box>
    </StepSection>
  );
}

function CampaignMatrixStep(props: BuilderStepProps) {
  const locked = Boolean(props.plan);
  const saveRow = (item: CampaignInstance) => {
    const edit = props.matrixEdits[item.id];
    if (!edit) return;
    props.onPatch(item.id, { campaign_name: edit.name, budget: Number(edit.budget) });
  };
  const applyBulk = () => props.selectedRows.forEach((id) => props.onPatch(id, { budget: Number(props.bulkBudget) }));
  return (
    <StepSection title={t("builder.step.matrix")}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <Button variant="contained" startIcon={<RefreshIcon />} disabled={!props.selectedAccounts.length || props.busy || locked} onClick={props.onGenerate}>{props.batch ? t("ui.5ce3895b0e") : t("ui.ab4c43c32f")}</Button>
        {props.batch && <><Button component="a" href={api.launchBatchExportUrl(props.batch.id, "xlsx")} startIcon={<DownloadOutlinedIcon />}>XLSX</Button><Button component="a" href={api.launchBatchExportUrl(props.batch.id, "csv")} startIcon={<DownloadOutlinedIcon />}>CSV</Button></>}
        <TextField size="small" label={t("ui.3a4e343cd0")} value={props.matrixFilter} onChange={(e) => props.setMatrixFilter(e.target.value)} sx={{ minWidth: 260 }} />
      </Stack>
      {locked && <Alert severity="info">{t("ui.b21bfde008")}</Alert>}
      {props.batch && <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}><StatusBadge value={props.batch.status} /><Chip label={t("common.launchGroupCount", { count: props.batch.bundles_count })} /><Chip label={t("common.campaignCount", { count: props.batch.campaigns_count })} /><Chip label={`${t("field.generationSeed")}: ${props.batch.generation_seed}`} /></Stack>}
      {props.selectedRows.length > 0 && !locked && <Stack direction="row" spacing={1}><TextField size="small" type="number" label={t("ui.1e40c95ea2")} value={props.bulkBudget} onChange={(e) => props.setBulkBudget(e.target.value)} /><Button variant="outlined" disabled={!props.bulkBudget || props.busy} onClick={applyBulk}>{t("ui.524b49df7e")}</Button></Stack>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", maxHeight: 620 }}>
        <Table size="small" stickyHeader sx={{ minWidth: 1900 }}><TableHead><TableRow><TableCell padding="checkbox"><Checkbox checked={props.filteredInstances.length > 0 && props.filteredInstances.every((item) => props.selectedRows.includes(item.id))} onChange={(e) => props.setSelectedRows(e.target.checked ? props.filteredInstances.map((item) => item.id) : [])} /></TableCell><TableCell>{t("common.launchBatch")}</TableCell><TableCell>{t("ui.a4adc0974e")}</TableCell><TableCell>Customer ID</TableCell><TableCell>{t("table.currencyTimeZone")}</TableCell><TableCell>{t("table.sequence")}</TableCell><TableCell>{t("table.campaignName")}</TableCell><TableCell>{t("ui.b9f1d1e1e4")}</TableCell><TableCell>{t("table.bidding")}</TableCell><TableCell>{t("table.geoLanguage")}</TableCell><TableCell>{t("table.channels")}</TableCell><TableCell>Final URL</TableCell><TableCell>{t("table.creativeSet")}</TableCell><TableCell>{t("table.validation")}</TableCell><TableCell /></TableRow></TableHead><TableBody>
          {props.filteredInstances.map((item) => {
            const edit = props.matrixEdits[item.id] || { name: item.campaign_name, budget: String(item.budget) };
            return <TableRow key={item.id} hover><TableCell padding="checkbox"><Checkbox checked={props.selectedRows.includes(item.id)} onChange={(e) => props.setSelectedRows(e.target.checked ? [...props.selectedRows, item.id] : props.selectedRows.filter((id) => id !== item.id))} /></TableCell><TableCell>{props.batch?.name}</TableCell><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code}<Typography variant="caption" display="block">{item.time_zone}</Typography></TableCell><TableCell>{item.campaign_sequence}</TableCell><TableCell><TextField size="small" value={edit.name} disabled={locked} onChange={(e) => props.setMatrixEdits({ ...props.matrixEdits, [item.id]: { ...edit, name: e.target.value } })} sx={{ width: 260 }} /></TableCell><TableCell><TextField size="small" type="number" value={edit.budget} disabled={locked} onChange={(e) => props.setMatrixEdits({ ...props.matrixEdits, [item.id]: { ...edit, budget: e.target.value } })} sx={{ width: 110 }} /></TableCell><TableCell>{item.bidding.strategy || "—"}</TableCell><TableCell>{(item.targeting.location_ids || []).join(", ")} / {(item.targeting.language_ids || []).join(", ")}</TableCell><TableCell>{item.targeting.channel_controls?.mode || "ALL_CHANNELS"}</TableCell><TableCell sx={{ maxWidth: 220, overflowWrap: "anywhere" }}>{item.url_settings.final_url}</TableCell><TableCell>{item.creative_assignment.set_key || "default"} · {(item.creative_assignment.media_ids || []).length}</TableCell><TableCell><StatusBadge value={item.local_validation.valid ? "VALID" : item.status} /></TableCell><TableCell><Tooltip title={t("ui.29d4c3cca8")}><span><IconButton size="small" disabled={locked || !props.matrixEdits[item.id]} onClick={() => saveRow(item)}><SaveOutlinedIcon fontSize="small" /></IconButton></span></Tooltip></TableCell></TableRow>;
          })}
          {!props.filteredInstances.length && <TableRow><TableCell colSpan={15}>{t("ui.cf90a64d52")}</TableCell></TableRow>}
        </TableBody></Table>
      </Box>
    </StepSection>
  );
}

function LocalValidationStep(props: BuilderStepProps) {
  const validation = props.plan?.local_validation;
  return (
    <StepSection title={t("builder.step.localValidation")}>
      {!props.scheduleId && <Alert severity="warning">{t("ui.fc4d362b49")}</Alert>}
      <Button variant="contained" startIcon={<LockOutlinedIcon />} disabled={!props.batch || !props.scheduleId || props.busy || Boolean(props.plan)} onClick={props.onBuildPlan}>{t("ui.4da285d19c")}</Button>
      {props.plan && <><InfoTable rows={[[t("common.fingerprint"), props.plan.fingerprint], [t("ui.cf645a44e5"), validation?.campaign_count || 0], [t("ui.9b92cdaa6e"), validation?.account_count || 0]]} /><IssueList severity="error" title={t("ui.681b5ae3d2")} items={validation?.errors || []} /><IssueList severity="warning" title={t("ui.4cbde65e99")} items={validation?.warnings || []} />{validation?.valid && <Alert severity="success">{t("ui.556cb09d07")}</Alert>}</>}
    </StepSection>
  );
}

function GoogleValidationStep(props: BuilderStepProps) {
  const result = props.plan?.google_validation;
  return (
    <StepSection title={t("builder.step.googleValidation")}>
      <Alert severity={props.form.execution_mode === "PRODUCTION" ? "error" : props.form.execution_mode === "GOOGLE_TEST" ? "warning" : "info"}>{props.form.execution_mode === "SIMULATION" ? t("ui.a8558225b1") : props.form.execution_mode === "GOOGLE_TEST" ? t("googleMode.validateTest") : t("googleMode.validateProductionBlocked")}</Alert>
      <Button variant="contained" startIcon={<FactCheckOutlinedIcon />} disabled={!props.plan?.local_validation.valid || props.busy} onClick={props.onValidate}>{t("ui.34f3cdcfdb")}</Button>
      {props.plan?.validated_at && <><Alert severity={result?.ok ? "success" : "error"}>{result?.ok ? t("ui.cfff2f91e4") : t("ui.fa25f1de8e")}</Alert><IssueList severity="error" title={t("ui.681b5ae3d2")} items={result?.errors || []} /><Typography variant="body2">{t("common.requestIds")} {props.plan.request_ids.length ? props.plan.request_ids.join(", ") : t("ui.0d691505ba")}</Typography></>}
    </StepSection>
  );
}

function FinancialStep({ batch }: BuilderStepProps) {
  return <StepSection title={t("builder.step.financial")}><FinancialSummary batch={batch} /></StepSection>;
}

function CreationStep(props: BuilderStepProps) {
  const plan = props.plan;
  return (
    <StepSection title={t("builder.step.creation")}>
      <Alert severity={props.form.execution_mode === "PRODUCTION" ? "error" : props.form.execution_mode === "GOOGLE_TEST" ? "warning" : "info"}>{props.form.execution_mode === "SIMULATION" ? t("ui.9c49d94bbc") : props.form.execution_mode === "GOOGLE_TEST" ? t("googleMode.createTest") : t("googleMode.productionMutateBlocked")}</Alert>
      <Button variant="contained" color="warning" startIcon={<PlayArrowIcon />} disabled={!props.confirmed || plan?.status !== "VALIDATED" || props.busy || props.form.execution_mode === "PRODUCTION"} onClick={props.onConfirm}>{t("ui.318f6d31be")}</Button>
      {plan && <Stack direction="row" spacing={1}><StatusBadge value={plan.status} /><Chip label={t("common.resourceCount", { count: plan.resource_names.length })} /></Stack>}
    </StepSection>
  );
}

function ReportStep(props: BuilderStepProps) {
  return (
    <StepSection title={t("builder.step.report")}>
      <InfoTable rows={[[t("common.launchBatch"), props.batch?.name || "—"], [t("ui.279f79d8f0"), props.batch?.bundles_count || 0], [t("common.campaignInstance"), props.batch?.campaigns_count || 0], [t("common.plan"), props.plan?.fingerprint || "—"], [t("ui.f7f293b5c5"), props.plan?.status || props.batch?.status || "DRAFT"], [t("ui.ff0fbd56f4"), props.form.execution_mode]]} />
      {props.plan?.status === "SUCCEEDED" && <Alert severity="success">{t("ui.530843faac")}</Alert>}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}><Button variant="contained" onClick={() => props.navigate(props.scheduleId ? `/schedules/${props.scheduleId}` : "/schedules")}>{t("ui.dcaee1d5cc")}</Button><Button variant="outlined" onClick={() => props.navigate("/launch-groups")}>{t("ui.81569b2f4f")}</Button><Button variant="outlined" onClick={() => props.navigate("/audit")}>{t("ui.f28b0859f1")}</Button></Stack>
    </StepSection>
  );
}

function FinancialSummary({ batch }: { batch?: LaunchBatch }) {
  const financial = batch?.financial_preview || {};
  const currencies = (financial.by_currency || []) as Array<Record<string, any>>;
  if (!batch) return <Alert severity="info">{t("ui.259dd04093")}</Alert>;
  return <Stack spacing={2}><InfoTable rows={[[t("ui.9b92cdaa6e"), financial.accounts || batch.bundles_count], [t("ui.72fbe98b2f"), financial.launch_groups || batch.bundles_count], [t("ui.cf645a44e5"), financial.campaigns || batch.campaigns_count], [t("ui.8f286b40b5"), financial.campaigns || batch.campaigns_count], [t("ui.2099d83eb5"), 0]]} /><Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell>{t("ui.18be059f5f")}</TableCell><TableCell>{t("ui.cf645a44e5")}</TableCell><TableCell>{t("ui.54ddf3d43e")}</TableCell><TableCell>{t("ui.c6ba85417d")}</TableCell><TableCell>{t("ui.b9f1d1e1e4")}</TableCell></TableRow></TableHead><TableBody>{currencies.map((item) => <TableRow key={item.currency_code}><TableCell>{item.currency_code}</TableCell><TableCell>{item.campaigns}</TableCell><TableCell>{item.minimum}</TableCell><TableCell>{item.maximum}</TableCell><TableCell sx={{ fontWeight: 700 }}>{item.assigned}</TableCell></TableRow>)}</TableBody></Table></Box></Stack>;
}

function StepSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <Stack spacing={2.5}><Typography variant="h6">{title}</Typography>{children}</Stack>;
}

function DomainValidationPanel({
  report,
  loading = false,
  error,
  onRetry,
  compact = false
}: {
  report?: DomainValidationReport;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const groups = groupDomainResults(report?.results || []);
  const status = groups[0]?.status || report?.status || "PENDING";
  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 1, overflow: "hidden" }}>
      <Box sx={{ px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
        <Box sx={{ flex: 1, minWidth: 180 }}>
          <Typography fontWeight={700}>{t("ui.a54933578c")}</Typography>
          <Typography variant="caption" color="text.secondary">
            {report
              ? t("domain.summary", {
                domains: report.summary.domains,
                urls: report.summary.urls,
                mode: report.enforcement
              })
              : t("ui.fe7d04e399")}
          </Typography>
        </Box>
        <DomainStatusChip status={status} />
        {onRetry && (
          <Button
            size="small"
            variant="outlined"
            disabled={loading}
            onClick={onRetry}
            startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
          >
            {t("ui.a54933578c")}
          </Button>
        )}
      </Box>
      {error && <Alert severity="error" sx={{ borderRadius: 0 }}>{error}</Alert>}
      {!compact && groups.map((group) => (
        <Accordion key={group.domain} disableGutters elevation={0} square>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0, width: "100%" }}>
              <Typography sx={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{group.domain || t("ui.25d2877d6a")}</Typography>
              <DomainStatusChip status={group.status} />
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Stack spacing={1.5}>
              {group.items.map((item) => <DomainResultDetails key={item.url_hash} item={item} />)}
            </Stack>
          </AccordionDetails>
        </Accordion>
      ))}
      {compact && (
        <Box sx={{ px: 2, pb: 1.5 }}>
          <Typography variant="body2" color={report?.summary.blocked ? "error.main" : "text.secondary"}>
            {report
              ? t("domain.compactSummary", {
                working: report.summary.working,
                blocked: report.summary.blocked,
                warnings: report.summary.warnings
              })
              : t("ui.f2a6a1924d")}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

function DomainResultDetails({ item }: { item: DomainValidationResult }) {
  const providers = item.reputation.providers || [];
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", pt: 1.5 }}>
      <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>{item.checked_url}</Typography>
      <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
        <Chip size="small" label={`HTTP: ${item.availability.http_status ?? "—"}`} />
        <Chip size="small" label={t("domain.responseMs", { value: item.availability.response_ms ?? "—" })} />
        <Chip size="small" label={t("domain.attempts", { count: item.availability.attempts ?? "—" })} />
        {item.cached && <Chip size="small" variant="outlined" label={t("ui.7563df248a")} />}
      </Stack>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, overflowWrap: "anywhere" }}>
        {t("ui.9187b5b24b")}{" "}{item.availability.final_url || "—"}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block">
        {t("ui.c4d1c15d4b")}{" "}{formatDate(item.checked_at)}
      </Typography>
      {item.code !== "OK" && (
        <Alert severity={item.blocking ? "error" : "warning"} sx={{ mt: 1 }}>
          {domainReason(item)}
        </Alert>
      )}
      {!!providers.length && (
        <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
          {providers.map((provider) => (
            <Tooltip
              key={provider.provider}
              title={t("domain.providerAttempts", {
                categories: provider.categories.join(", ") || t("ui.ce5733adc2"),
                count: provider.attempts
              })}
            >
              <Chip
                size="small"
                variant="outlined"
                color={provider.verdict === "THREAT" ? "error" : provider.verdict === "CLEAN" ? "success" : "warning"}
                label={`${provider.provider}: ${provider.verdict}`}
              />
            </Tooltip>
          ))}
        </Stack>
      )}
    </Box>
  );
}

function DomainStatusChip({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const label = domainStatusLabel(normalized);
  const color = normalized === "THREAT" || normalized === "UNAVAILABLE"
    ? "error"
    : normalized === "WORKING_CLEAN" || normalized === "COMPLETED"
      ? "success"
      : "warning";
  return <Chip size="small" color={color} variant={normalized === "PENDING" ? "outlined" : "filled"} label={label} />;
}

function groupDomainResults(items: DomainValidationResult[]) {
  const rank: Record<string, number> = {
    THREAT: 6,
    UNAVAILABLE: 5,
    CHECK_UNAVAILABLE: 4,
    RECHECK_REQUIRED: 3,
    PENDING: 2,
    REPUTATION_NOT_CONFIGURED: 2,
    LOW_REPUTATION: 1,
    WORKING_CLEAN: 0
  };
  const groups = new Map<string, DomainValidationResult[]>();
  items.forEach((item) => groups.set(item.domain, [...(groups.get(item.domain) || []), item]));
  return [...groups.entries()].map(([domain, values]) => ({
    domain,
    items: values,
    status: [...values].sort((a, b) => (rank[b.status] || 0) - (rank[a.status] || 0))[0]?.status || "PENDING"
  }));
}

function domainStatusLabel(status: string) {
  return ({
    COMPLETED: t("ui.7b3bb04ef1"),
    PENDING: t("ui.fe7d04e399"),
    CHECKING: t("ui.9568c47fde"),
    RECHECK_REQUIRED: t("ui.60b2eb0058"),
    WORKING_CLEAN: t("ui.ec796bd25b"),
    UNAVAILABLE: t("ui.37cc8757db"),
    THREAT: t("ui.1a6d3c8caf"),
    LOW_REPUTATION: t("ui.e3f03d1873"),
    CHECK_UNAVAILABLE: t("ui.583c537187"),
    REPUTATION_NOT_CONFIGURED: t("ui.90838de802")
  } as Record<string, string>)[status] || status;
}

function domainReason(item: DomainValidationResult) {
  const reason = ({
    DNS_ERROR: t("ui.9c8b3103ee"),
    TIMEOUT: t("ui.e2d71d2bdd"),
    TLS_ERROR: t("ui.d4a497522e"),
    CONNECTION_ERROR: t("ui.6bd21210b3"),
    HTTP_4XX: t("domain.httpStatus", { status: item.availability.http_status ?? "4xx" }),
    HTTP_5XX: t("domain.httpStatus", { status: item.availability.http_status ?? "5xx" }),
    REDIRECT_LOOP: t("ui.5edf463e06"),
    TOO_MANY_REDIRECTS: t("ui.9c3cdcb38f"),
    INVALID_REDIRECT: t("ui.c7fa739414"),
    SSRF_BLOCKED: t("ui.c2535a2e37"),
    INVALID_URL: t("ui.25d2877d6a"),
    EMPTY_URL: t("ui.1b35f4bb76"),
    UNSUPPORTED_SCHEME: t("ui.3d80baa72c"),
    CREDENTIALS_IN_URL: t("ui.5cb71ba081"),
    DOMAIN_REPUTATION_THREAT: t("domain.threatFound", { categories: (item.reputation.categories || []).join(", ") }),
    DOMAIN_LOW_REPUTATION: t("ui.53421299c2"),
    DOMAIN_REPUTATION_UNAVAILABLE: t("ui.b6765fef6c"),
    DOMAIN_REPUTATION_NOT_CONFIGURED: t("ui.4a4c26e6b5")
  } as Record<string, string>)[item.code] || item.code;
  return item.blocking
    ? t("domain.blockedMessage", { domain: item.domain || "—", reason })
    : reason;
}

function InfoTable({ rows }: { rows: Array<[string, React.ReactNode]> }) {
  return <Box sx={{ maxWidth: 780, borderTop: 1, borderColor: "divider" }}>{rows.map(([label, value]) => <Box key={label} sx={{ display: "grid", gridTemplateColumns: "minmax(180px, 1fr) minmax(0, 2fr)", gap: 2, py: 1.25, borderBottom: 1, borderColor: "divider" }}><Typography color="text.secondary">{label}</Typography><Typography sx={{ overflowWrap: "anywhere" }}>{value}</Typography></Box>)}</Box>;
}

function CapabilityStrip({ capabilities, prefix }: { capabilities: Array<Record<string, any>>; prefix: string }) {
  const unavailable = capabilities.filter((item) => String(item.key).startsWith(prefix) && !item.supports_create);
  if (!unavailable.length) return null;
  return <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>{unavailable.map((item) => <Tooltip key={item.key} title={item.reason || t("ui.18d68a6c33")}><Chip size="small" variant="outlined" color="default" label={t("capability.unavailable", { label: item.label })} /></Tooltip>)}</Stack>;
}

function ChoiceChecks({ label, values, selected, onChange }: { label: string; values: Array<[string, string]>; selected: string[]; onChange: (value: string[]) => void }) {
  return <Box><Typography variant="body2" fontWeight={700}>{label}</Typography><Stack direction="row" useFlexGap sx={{ flexWrap: "wrap" }}>{values.map(([value, text]) => <FormControlLabel key={value} control={<Checkbox checked={selected.includes(value)} onChange={(e) => onChange(e.target.checked ? [...selected, value] : selected.filter((item) => item !== value))} />} label={text.includes(".") ? t(text) : text} />)}</Stack></Box>;
}

function IssueList({ title, severity, items }: { title: string; severity: "error" | "warning"; items: Array<{ message: string; path?: string }> }) {
  if (!items.length) return null;
  return <Alert severity={severity}><Typography fontWeight={700}>{title}: {items.length}</Typography>{items.slice(0, 20).map((item, index) => <Typography variant="body2" key={`${item.path}-${index}`}>{item.path ? `${item.path}: ` : ""}{item.message}</Typography>)}</Alert>;
}

export function buildBatchPayload(form: BuilderForm, accounts: BuilderAccount[]) {
  return {
    batch_name: form.batch_name,
    execution_mode: form.execution_mode,
    creation_mode: form.creation_mode,
    template_id: form.template_id || null,
    template_name: form.template_id ? "Template" : "DemandGen",
    accounts: accounts.map((item) => ({ ...item, campaigns_count: item.campaigns_count || form.campaigns_per_account })),
    campaigns_per_account: form.campaigns_per_account,
    copy_mode: form.copy_mode,
    name_pattern: form.name_pattern,
    generation_seed: form.generation_seed,
    template_defaults: {
      campaign: {
        ad_type: form.ad_type,
        ad_group_name: form.ad_group_name,
        business_name: form.business_name,
        youtube_video_id: form.youtube_video_id,
        start_date_time: form.start_date_time || null,
        end_date_time: form.end_date_time || null,
        conversion_action_resource_names: splitValues(form.conversion_actions)
      },
      bidding: { strategy: form.bidding_strategy, target_cpa: form.target_cpa, target_roas: form.target_roas },
      targeting: {
        location_ids: splitValues(form.location_ids),
        excluded_location_ids: splitValues(form.excluded_location_ids),
        language_ids: splitValues(form.language_ids),
        audience_resource_names: splitValues(form.audience_resource_names),
        user_list_resource_names: splitValues(form.user_list_resource_names),
        custom_audience_resource_names: splitValues(form.custom_audience_resource_names),
        user_interest_resource_names: splitValues(form.user_interest_resource_names),
        life_event_ids: splitValues(form.life_event_ids),
        demographics: {
          age_ranges: form.age_ranges,
          genders: form.genders,
          parental_statuses: form.parental_statuses,
          income_ranges: form.income_ranges
        },
        optimized_targeting: form.optimized_targeting,
        channel_controls: { mode: form.channel_mode, selected: form.channels }
      },
      url: {
        final_url: form.final_url,
        mobile_final_url: form.mobile_final_url || null,
        tracking_template: form.tracking_template || null,
        final_url_suffix: form.final_url_suffix || null,
        display_path: form.display_path || null,
        append_dgu_instance: form.append_instance_parameter,
        custom_parameters: parseCustomParameters(form.custom_parameters)
      },
      texts: {
        business_name: form.business_name,
        headlines: splitLines(form.headlines),
        long_headline: form.long_headline,
        descriptions: splitLines(form.descriptions),
        carousel_card_headlines: splitLines(form.carousel_card_headlines),
        call_to_action: form.call_to_action
      }
    },
    budget: {
      mode: form.budget_mode,
      distribution: form.budget_distribution,
      fixed: numberValue(form.budget_fixed),
      minimum: numberValue(form.budget_minimum),
      maximum: numberValue(form.budget_maximum),
      step: numberValue(form.budget_step),
      manual_values: splitValues(form.budget_manual_values).map(Number),
      allow_repeats: form.allow_repeats,
      seed: form.generation_seed
    },
    creative: {
      media_ids: form.media_ids,
      logo_media_id: form.logo_media_id || null,
      subset_size: Math.max(1, Math.min(5, form.media_ids.length))
    },
    campaign_overrides: {},
    password_confirmation: form.password_confirmation || null
  };
}

function hydrateBuilderForm(mode: string, builder: Record<string, any>): BuilderForm {
  const emptyForm = createEmptyForm();
  const defaults = builder.template_defaults || {};
  const campaign = defaults.campaign || {};
  const bidding = defaults.bidding || {};
  const targeting = defaults.targeting || {};
  const urls = defaults.url || {};
  const texts = defaults.texts || {};
  const budget = builder.budget || {};
  return {
    ...emptyForm,
    execution_mode: mode === "GOOGLE_TEST" || mode === "PRODUCTION" ? mode : "SIMULATION",
    creation_mode: builder.creation_mode || emptyForm.creation_mode,
    template_id: builder.template_id || "",
    batch_name: builder.batch_name || emptyForm.batch_name,
    name_pattern: builder.name_pattern || emptyForm.name_pattern,
    generation_seed: builder.generation_seed || emptyForm.generation_seed,
    ad_type: campaign.ad_type || emptyForm.ad_type,
    ad_group_name: campaign.ad_group_name || emptyForm.ad_group_name,
    business_name: texts.business_name || campaign.business_name || emptyForm.business_name,
    final_url: urls.final_url || emptyForm.final_url,
    mobile_final_url: urls.mobile_final_url || "",
    tracking_template: urls.tracking_template || "",
    final_url_suffix: urls.final_url_suffix || "",
    display_path: urls.display_path || "",
    custom_parameters: customParametersText(urls.custom_parameters),
    append_instance_parameter: Boolean(urls.append_dgu_instance),
    start_date_time: campaign.start_date_time || "",
    end_date_time: campaign.end_date_time || "",
    bidding_strategy: bidding.strategy || emptyForm.bidding_strategy,
    target_cpa: String(bidding.target_cpa || emptyForm.target_cpa),
    target_roas: String(bidding.target_roas || emptyForm.target_roas),
    conversion_actions: listText(campaign.conversion_action_resource_names),
    location_ids: listText(targeting.location_ids) || emptyForm.location_ids,
    excluded_location_ids: listText(targeting.excluded_location_ids),
    language_ids: listText(targeting.language_ids) || emptyForm.language_ids,
    audience_resource_names: listText(targeting.audience_resource_names),
    user_list_resource_names: listText(targeting.user_list_resource_names),
    custom_audience_resource_names: listText(targeting.custom_audience_resource_names),
    user_interest_resource_names: listText(targeting.user_interest_resource_names),
    life_event_ids: listText(targeting.life_event_ids),
    age_ranges: targeting.demographics?.age_ranges || emptyForm.age_ranges,
    genders: targeting.demographics?.genders || emptyForm.genders,
    parental_statuses: targeting.demographics?.parental_statuses || [],
    income_ranges: targeting.demographics?.income_ranges || [],
    optimized_targeting: targeting.optimized_targeting ?? true,
    channel_mode: targeting.channel_controls?.mode || emptyForm.channel_mode,
    channels: { ...emptyForm.channels, ...(targeting.channel_controls?.selected || {}) },
    headlines: listLines(texts.headlines) || emptyForm.headlines,
    long_headline: texts.long_headline || emptyForm.long_headline,
    descriptions: listLines(texts.descriptions) || emptyForm.descriptions,
    carousel_card_headlines: listLines(texts.carousel_card_headlines) || emptyForm.carousel_card_headlines,
    call_to_action: texts.call_to_action || emptyForm.call_to_action,
    youtube_video_id: campaign.youtube_video_id || emptyForm.youtube_video_id,
    media_ids: builder.creative?.media_ids || [],
    logo_media_id: builder.creative?.logo_media_id || "",
    campaigns_per_account: Number(builder.campaigns_per_account || emptyForm.campaigns_per_account),
    copy_mode: builder.copy_mode || emptyForm.copy_mode,
    budget_mode: budget.mode || emptyForm.budget_mode,
    budget_distribution: budget.distribution || emptyForm.budget_distribution,
    budget_fixed: String(budget.fixed || emptyForm.budget_fixed),
    budget_minimum: String(budget.minimum || emptyForm.budget_minimum),
    budget_maximum: String(budget.maximum || emptyForm.budget_maximum),
    budget_step: String(budget.step || emptyForm.budget_step),
    budget_manual_values: listText(budget.manual_values),
    allow_repeats: budget.allow_repeats ?? true,
    password_confirmation: ""
  };
}

function normalizeBuilderAccount(value: any): BuilderAccount {
  return {
    id: value.id,
    customer_id: String(value.customer_id),
    account_name: value.account_name || value.descriptive_name || value.customer_id,
    currency_code: value.currency_code || "USD",
    time_zone: value.time_zone || "UTC",
    campaigns_count: value.campaigns_count,
    overrides: value.overrides || {}
  };
}

const copyModes = [
  ["EXACT_COPY", "ui.a19e93d695"],
  ["SAME_SETTINGS_RANDOM_BUDGET", "ui.dea24ffe0e"],
  ["RANDOM_CREATIVE_SUBSET", "ui.882667abb8"],
  ["ROTATE_CREATIVE_SETS", "ui.3026613f2a"],
  ["BIDDING_VARIATIONS", "ui.91e969dc0f"],
  ["AUDIENCE_VARIATIONS", "ui.38d4983ef4"],
  ["CUSTOM_MATRIX", "ui.4beb9f5339"]
];
const channelLabels = [["youtube_in_stream", "YouTube In-stream"], ["youtube_in_feed", "YouTube In-feed"], ["youtube_shorts", "YouTube Shorts"], ["discover", "Discover"], ["gmail", "Gmail"], ["display", "Display"], ["maps", "Maps"]];
const ageOptions: Array<[string, string]> = [["AGE_RANGE_18_24", "18–24"], ["AGE_RANGE_25_34", "25–34"], ["AGE_RANGE_35_44", "35–44"], ["AGE_RANGE_45_54", "45–54"], ["AGE_RANGE_55_64", "55–64"], ["AGE_RANGE_65_UP", "65+"]];
const genderOptions: Array<[string, string]> = [["MALE", "ui.e19b9f8774"], ["FEMALE", "ui.e94aa18bcf"], ["UNDETERMINED", "ui.1962b53a94"]];
const parentalOptions: Array<[string, string]> = [["PARENT", "builder.audience.parent"], ["NOT_A_PARENT", "builder.audience.notParent"], ["UNDETERMINED", "builder.audience.undetermined"]];
const incomeOptions: Array<[string, string]> = [["INCOME_RANGE_0_50", "builder.audience.income0to50"], ["INCOME_RANGE_50_60", "builder.audience.income50to60"], ["INCOME_RANGE_60_70", "builder.audience.income60to70"], ["INCOME_RANGE_70_80", "builder.audience.income70to80"], ["INCOME_RANGE_80_90", "builder.audience.income80to90"], ["INCOME_RANGE_90_UP", "builder.audience.income90plus"], ["INCOME_RANGE_UNDETERMINED", "builder.audience.undetermined"]];

function parseCustomParameters(value: string) {
  return splitLines(value).flatMap((line) => {
    const separator = line.indexOf("=");
    if (separator < 1) return [];
    const key = line.slice(0, separator).trim().replace(/^\{_?|\}$/g, "");
    const parameterValue = line.slice(separator + 1).trim();
    return key ? [{ key, value: parameterValue }] : [];
  });
}
function customParametersText(value: unknown) {
  if (!Array.isArray(value)) return "";
  return value
    .map((item) => `${String(item?.key || "")}=${String(item?.value || "")}`)
    .join("\n");
}
function mediaRoleLabel(item: MediaAsset) {
  const role = String(item.validation?.suggested_role || "").trim();
  return role || "—";
}
function splitLines(value: string) { return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean); }
function splitValues(value: string) { return value.split(/[\n,;|]/).map((item) => item.trim()).filter(Boolean); }
function listText(value: unknown) { return Array.isArray(value) ? value.join(", ") : value ? String(value) : ""; }
function listLines(value: unknown) { return Array.isArray(value) ? value.join("\n") : value ? String(value) : ""; }
function numberValue(value: string) { return Number(String(value).replace(",", ".")) || 0; }
