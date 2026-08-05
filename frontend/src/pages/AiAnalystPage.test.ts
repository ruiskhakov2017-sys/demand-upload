import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const page = fs.readFileSync(path.resolve("src/pages/AiAnalystPage.tsx"), "utf8");
const drawer = fs.readFileSync(path.resolve("src/components/AiAssistantDrawer.tsx"), "utf8");
const answer = fs.readFileSync(path.resolve("src/components/AiAnswerView.tsx"), "utf8");
const app = fs.readFileSync(path.resolve("src/app/App.tsx"), "utf8");
const main = fs.readFileSync(path.resolve("src/main.tsx"), "utf8");
const boundary = fs.readFileSync(path.resolve("src/app/AppErrorBoundary.tsx"), "utf8");
const uploadWizard = fs.readFileSync(path.resolve("src/pages/UploadWizardPage.tsx"), "utf8");

describe("AI Analyst UI contract", () => {
  it("exposes the full page and a conversation-preserving global drawer", () => {
    expect(app).toContain('path: "/ai-analyst"');
    expect(app).toContain("<AiAssistantDrawer path={path}");
    expect(drawer).toContain('localStorage.getItem("axyro.ai.conversation")');
    expect(drawer).toContain('navigate("/ai-analyst")');
    expect(drawer).toContain("const selectedExists = conversationId && conversations.data.some");
  });

  it("contains every required scope axis and authority mode", () => {
    for (const field of ["connection_ids", "geo_ids", "mcc_ids", "account_ids", "campaign_ids", "metric_source", "currency"]) {
      expect(page).toContain(field);
    }
    for (const mode of ["READ_ONLY", "DRAFT_ONLY", "CONFIRM_REQUIRED"]) expect(page).toContain(mode);
    expect(page).toContain('disabled={!props.capabilities?.production.read_enabled}');
  });

  it("keeps voice transcription editable and never auto-sends it", () => {
    expect(page).toContain("navigator.mediaDevices.getUserMedia");
    expect(page).toContain("const result = await api.transcribeAiAudio(blob)");
    expect(page).toContain("onChange(result.transcript)");
    expect(page).not.toContain("onSend(result.transcript)");
  });

  it("renders allowlisted structures without raw HTML", () => {
    expect(answer).toContain("answer.tables.map");
    expect(answer).toContain("answer.charts.map");
    expect(answer).toContain("answer.sources.map");
    expect(answer).toContain("message.tool_timeline.map");
    expect(answer).not.toContain("dangerouslySetInnerHTML");
  });

  it("requires an explicit user gesture for draft apply", () => {
    expect(page).toContain("window.confirm(ai(\"ai.confirmDraft\"))");
    expect(page).toContain("api.applyAiDraft");
    expect(page).toContain("api.previewAiDraft");
    expect(uploadWizard).toContain('get("ai_draft")');
    expect(uploadWizard).toContain('requestedEditorStep === "schedule"');
  });

  it("includes all nine agreed quick scenarios", () => {
    const block = page.match(/const QUICK_PROMPT_KEYS = \[([\s\S]*?)\];/)?.[1] || "";
    expect(block.match(/ai\.quick\.\d/g)).toHaveLength(9);
    expect(page).toContain("disabled={disabled}");
    expect(page).toContain("capabilities.data?.provider.configured === false");
    expect(drawer).toContain("const interactionDisabled = !capabilities.data?.enabled");
    expect(drawer).toContain("disabled={sending || interactionDisabled}");
    expect(drawer).toContain("if (!content || sending || interactionDisabled) return;");
    expect(drawer).toContain('ai("ai.providerMissing")');
  });

  it("shows personal cost and supports archive restore", () => {
    expect(page).toContain("api.aiMyUsage(30)");
    expect(page).toContain('ai("ai.cost")');
    expect(page).toContain("setShowArchived");
    expect(page).toContain('archived: !showArchived');
    expect(page).toContain("<UnarchiveOutlinedIcon");
    expect(page).toContain('queryClient.removeQueries({ queryKey: ["ai-conversation", removedId] })');
    expect(page).toContain("const activeMessages = conversationId ?");
    expect(page).toContain("const selectedExists = conversationId && conversations.data.some");
  });

  it("shows a recoverable screen instead of a blank page after a render failure", () => {
    expect(main).toContain("<AppErrorBoundary>");
    expect(boundary).toContain("getDerivedStateFromError");
    expect(boundary).toContain("window.location.reload()");
  });

  it("does not return the scroll result as a React effect cleanup", () => {
    expect(page).toContain("const container = messageListRef.current");
    expect(page).toContain("container.scrollTo({ top: container.scrollHeight");
    expect(page).not.toContain("scrollIntoView");
  });
});
