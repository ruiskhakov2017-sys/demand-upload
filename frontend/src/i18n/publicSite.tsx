import AccountTreeOutlined from "@mui/icons-material/AccountTreeOutlined";
import AnalyticsOutlined from "@mui/icons-material/AnalyticsOutlined";
import ArrowForward from "@mui/icons-material/ArrowForward";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import CrisisAlertOutlined from "@mui/icons-material/CrisisAlertOutlined";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import EditNoteOutlined from "@mui/icons-material/EditNoteOutlined";
import FactCheckOutlined from "@mui/icons-material/FactCheckOutlined";
import FilterAltOutlined from "@mui/icons-material/FilterAltOutlined";
import HistoryOutlined from "@mui/icons-material/HistoryOutlined";
import LockOutlined from "@mui/icons-material/LockOutlined";
import Login from "@mui/icons-material/Login";
import PaidOutlined from "@mui/icons-material/PaidOutlined";
import SecurityOutlined from "@mui/icons-material/SecurityOutlined";
import TuneOutlined from "@mui/icons-material/TuneOutlined";
import {
  AppBar,
  Box,
  Button,
  Container,
  Link,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Toolbar,
  Typography
} from "@mui/material";
import { ReactNode, useEffect } from "react";

import { Locale, useLocale } from ".";

type PublicCopy = {
  nav: { product: string; api: string; security: string; privacy: string; terms: string; workspace: string };
  eyebrow: string;
  subtitle: string;
  heroBody: string;
  primaryAction: string;
  secondaryAction: string;
  proofLabel: string;
  proofCaption: string;
  overviewTitle: string;
  overviewLead: string;
  features: Array<{ title: string; body: string }>;
  productTitle: string;
  productParagraphs: string[];
  metricsTitle: string;
  metricsBody: string;
  metricLabels: string[];
  operationsTitle: string;
  operationsBody: string;
  operations: string[];
  apiTitle: string;
  apiBody: string;
  readTitle: string;
  readItems: string[];
  writeTitle: string;
  writeItems: string[];
  productionNotice: string;
  deploymentEyebrow: string;
  deploymentTitle: string;
  deploymentBody: string;
  deploymentSteps: string[];
  deploymentCaption: string;
  architectureTitle: string;
  architectureBody: string;
  architecture: string[];
  audienceTitle: string;
  audienceBody: string;
  affiliation: string;
  contactTitle: string;
  contactBody: string;
  footerProduct: string;
};

export const PUBLIC_SITE_TITLE = "Axyro Analytics | Private Google Ads Analytics & Control Center";

export const PUBLIC_COPY: Record<Locale, PublicCopy> = {
  en: {
    nav: {
      product: "Product",
      api: "Google Ads API",
      security: "Security",
      privacy: "Privacy",
      terms: "Terms",
      workspace: "Secure workspace"
    },
    eyebrow: "Independent analytics and operations project",
    subtitle: "Private Google Ads Analytics & Control Center",
    heroBody:
      "Centralized reporting, performance analysis, account monitoring, and controlled operations across multiple Google Ads manager and advertising accounts.",
    primaryAction: "View product",
    secondaryAction: "Open secure workspace",
    proofLabel: "Working control center",
    proofCaption:
      "The interface consolidates MCC hierarchy, account state, performance, conversion, policy, verification, issue, and audit data. Demonstration data is used in this public screenshot.",
    overviewTitle: "One operational view across Google Ads accounts",
    overviewLead:
      "Axyro Analytics normalizes account and campaign data from connected MCC hierarchies so its sole operator can compare markets, find issues, and document decisions in one place.",
    features: [
      { title: "MCC and GEO structure", body: "Group and filter advertising accounts by manager hierarchy and geographic market." },
      { title: "Account analytics", body: "Review cost, impressions, clicks, CTR, CPC, registrations, deposits, and CPA." },
      { title: "Performance comparison", body: "Compare accounts and campaigns across selected periods, currencies, statuses, and tags." },
      { title: "Issues and statuses", body: "Monitor account, campaign, policy, advertiser verification, and synchronization states." },
      { title: "Filters and saved views", body: "Build repeatable operational views with sorting, column controls, and saved filters." },
      { title: "History and audit", body: "Keep change history, internal notes, tags, action results, and Google Request IDs." },
      { title: "Reports and exports", body: "Export account and campaign views for analysis and internal reporting." },
      { title: "Controlled operations", body: "Preview and explicitly confirm permitted status and budget changes." }
    ],
    productTitle: "Product purpose",
    productParagraphs: [
      "Axyro Analytics is an independent Google Ads analytics and operations software project operated by Iskhakov Ruslan, an individual. It is not a registered company or a separate legal entity.",
      "The private tool consolidates connected manager and advertising accounts and synchronizes account hierarchy, campaign performance metrics, conversion data, policy and verification statuses, operational issues, and change history for its sole user.",
      "The primary purpose of the tool is centralized reporting, performance analysis, account monitoring, and operational control.",
      "The platform also includes secondary campaign management functions. Authorized users can create validated Demand Gen campaigns, pause or enable selected campaigns, and update budgets. All write operations are explicitly initiated by a user, validated before execution, confirmed in the interface, recorded in an audit log, and protected by production safety controls. Newly created campaigns are created in a paused state by default.",
      "Only Iskhakov Ruslan currently has access to the workspace. There are no employees, contractors, external clients, or public users, and the project is not offered as a public self-service advertising product."
    ],
    metricsTitle: "Metrics with explicit data semantics",
    metricsBody:
      "Google Ads delivery metrics and mapped conversion actions are kept distinct. Missing registration or deposit mappings are shown as unavailable data rather than zero.",
    metricLabels: ["Cost", "Impressions", "Clicks", "CTR", "CPC", "Registrations", "Deposits", "Registration CPA", "Deposit CPA"],
    operationsTitle: "Operational context stays attached to every account",
    operationsBody:
      "Local working status, owner notes, tags, alerts, verification deadlines, policy issues, synchronization errors, and action history are available alongside performance data.",
    operations: [
      "Accounts in work and local status filters",
      "Editable notes and reusable tags",
      "Policy and advertiser verification monitoring",
      "Alerts, status changes, and synchronization diagnostics",
      "AuditLog entries with actor, time, result, and Request ID"
    ],
    apiTitle: "How Google Ads API is used",
    apiBody:
      "Primary use: reporting, analytics and monitoring. Secondary use: explicitly confirmed campaign management operations.",
    readTitle: "Read operations",
    readItems: [
      "Accessible customers and MCC hierarchy",
      "Account, campaign, ad, policy, and verification status",
      "Performance and mapped conversion metrics",
      "Campaign budgets and supported billing information",
      "Post-change readback and Google Request IDs"
    ],
    writeTitle: "Write operations",
    writeItems: [
      "Create validated Demand Gen campaigns",
      "Pause or enable selected campaigns",
      "Update selected campaign budgets",
      "Run only after an authorized user reviews and confirms the action",
      "Record the requested and actual result in AuditLog"
    ],
    productionNotice:
      "Production write operations are currently disabled by an application safety guard while Google Ads API Basic Access is pending. Test-account operations remain isolated from production accounts.",
    deploymentEyebrow: "Secondary module",
    deploymentTitle: "Validated campaign deployment",
    deploymentBody:
      "The Demand Gen Uploader module prepares a reviewable campaign plan and keeps creation separate from automatic activation.",
    deploymentSteps: [
      "Build a preliminary plan",
      "Run local schema, asset, URL, and domain checks",
      "Run Google Ads validate_only",
      "Require explicit user confirmation",
      "Create new campaigns in PAUSED",
      "Read created resources back and write the result to AuditLog",
      "Never enable a newly created campaign automatically"
    ],
    deploymentCaption:
      "Campaign deployment is a secondary controlled workflow. The main product remains analytics, monitoring, reporting, and operational control.",
    architectureTitle: "Server-side architecture and credential boundary",
    architectureBody:
      "The browser communicates only with the protected application API. OAuth refresh tokens and Google Ads credentials stay encrypted on the backend and are never returned to frontend code.",
    architecture: ["React frontend", "FastAPI backend", "PostgreSQL", "Redis", "Worker", "Scheduler", "Google Ads API"],
    audienceTitle: "Sole-operator access",
    audienceBody:
      "The workspace is currently used only by Iskhakov Ruslan through the protected owner account. No employee, contractor, client, or member of the public has access.",
    affiliation: "Axyro Analytics is the name of an independent software project operated by Iskhakov Ruslan, an individual. It is not a registered company or separate legal entity and is not affiliated with, endorsed by, or sponsored by Google.",
    contactTitle: "Product and privacy contact",
    contactBody: "Questions about the product, Google Ads API use, privacy, or data deletion can be sent to:",
    footerProduct: "Axyro Analytics · Operated by Iskhakov Ruslan (individual)"
  },
  ru: {
    nav: {
      product: "Продукт",
      api: "Google Ads API",
      security: "Безопасность",
      privacy: "Конфиденциальность",
      terms: "Условия",
      workspace: "Защищённый кабинет"
    },
    eyebrow: "Независимый проект аналитики и управления",
    subtitle: "Личный центр аналитики и контроля Google Ads",
    heroBody:
      "Централизованная отчётность, анализ эффективности, мониторинг аккаунтов и контролируемые операции в нескольких управляющих и рекламных аккаунтах Google Ads.",
    primaryAction: "Посмотреть продукт",
    secondaryAction: "Открыть кабинет",
    proofLabel: "Рабочий центр контроля",
    proofCaption:
      "Интерфейс объединяет структуру MCC, состояния аккаунтов, эффективность, конверсии, policy и verification statuses, проблемы и аудит. На публичном скриншоте используются демонстрационные данные.",
    overviewTitle: "Единый операционный экран для Google Ads",
    overviewLead:
      "Axyro Analytics нормализует данные аккаунтов и кампаний из подключённых MCC, чтобы единственный оператор мог сравнивать рынки, находить проблемы и фиксировать решения в одном месте.",
    features: [
      { title: "Структура MCC и GEO", body: "Группировка и фильтрация рекламных аккаунтов по иерархии MCC и географическому рынку." },
      { title: "Аналитика аккаунтов", body: "Расходы, показы, клики, CTR, CPC, регистрации, депозиты и CPA." },
      { title: "Сравнение эффективности", body: "Сравнение аккаунтов и кампаний по периоду, валюте, статусу и тегам." },
      { title: "Проблемы и статусы", body: "Мониторинг аккаунтов, кампаний, правил, верификации рекламодателя и синхронизации." },
      { title: "Фильтры и представления", body: "Повторяемые рабочие выборки с сортировкой, настройкой колонок и сохранёнными фильтрами." },
      { title: "История и аудит", body: "История изменений, внутренние заметки, теги, результаты действий и Google Request ID." },
      { title: "Отчёты и экспорт", body: "Выгрузка представлений аккаунтов и кампаний для анализа и внутренней отчётности." },
      { title: "Контролируемые операции", body: "Предпросмотр и явное подтверждение разрешённых изменений статуса и бюджета." }
    ],
    productTitle: "Назначение продукта",
    productParagraphs: [
      "Axyro Analytics — независимый программный проект аналитики и управления Google Ads, которым управляет физическое лицо Iskhakov Ruslan. Это не зарегистрированная компания и не отдельное юридическое лицо.",
      "Личный инструмент объединяет подключённые управляющие и рекламные аккаунты и синхронизирует их структуру, статистику кампаний, данные о конверсиях, статусы правил и верификации, операционные проблемы и историю изменений для единственного пользователя.",
      "Основное назначение инструмента — централизованная отчётность, анализ эффективности, мониторинг аккаунтов и операционный контроль.",
      "Платформа также содержит второстепенные функции управления кампаниями. Авторизованные пользователи могут создавать проверенные Demand Gen кампании, приостанавливать или включать выбранные кампании и изменять бюджеты. Все изменяющие операции явно запускаются пользователем, проверяются до выполнения, подтверждаются в интерфейсе, записываются в журнал аудита и защищены предохранителями production-режима. Новые кампании по умолчанию создаются приостановленными.",
      "Доступ к рабочему кабинету сейчас есть только у Iskhakov Ruslan. Сотрудников, подрядчиков, внешних клиентов и публичных пользователей нет; проект не предлагается как публичный рекламный сервис самообслуживания."
    ],
    metricsTitle: "Метрики с однозначной семантикой данных",
    metricsBody:
      "Метрики показа Google Ads и сопоставленные действия-конверсии хранятся раздельно. Если регистрации или депозиты не сопоставлены, интерфейс показывает отсутствие данных, а не ноль.",
    metricLabels: ["Расходы", "Показы", "Клики", "CTR", "CPC", "Регистрации", "Депозиты", "CPA регистрации", "CPA депозита"],
    operationsTitle: "Операционный контекст хранится вместе с аккаунтом",
    operationsBody:
      "Локальный рабочий статус, заметки владельца, теги, уведомления, сроки верификации, policy issues, ошибки синхронизации и история действий доступны рядом со статистикой.",
    operations: [
      "Аккаунты в работе и фильтры по локальному статусу",
      "Редактируемые заметки и повторно используемые теги",
      "Мониторинг policy и advertiser verification",
      "Уведомления, изменения статусов и диагностика синхронизации",
      "AuditLog с пользователем, временем, результатом и Request ID"
    ],
    apiTitle: "Как используется Google Ads API",
    apiBody:
      "Основное использование: отчётность, аналитика и мониторинг. Вторичное использование: явно подтверждённые операции управления кампаниями.",
    readTitle: "Операции чтения",
    readItems: [
      "Доступные клиенты и иерархия MCC",
      "Статусы аккаунтов, кампаний, объявлений, policy и verification",
      "Метрики эффективности и сопоставленных конверсий",
      "Бюджеты кампаний и поддерживаемая billing-информация",
      "Повторное чтение после изменений и Google Request ID"
    ],
    writeTitle: "Изменяющие операции",
    writeItems: [
      "Создание проверенных Demand Gen кампаний",
      "Приостановка или включение выбранных кампаний",
      "Изменение бюджетов выбранных кампаний",
      "Запуск только после просмотра и подтверждения авторизованным пользователем",
      "Запись запрошенного и фактического результата в AuditLog"
    ],
    productionNotice:
      "Изменяющие операции в production сейчас отключены предохранителем приложения, пока ожидается Google Ads API Basic Access. Операции тестовых аккаунтов изолированы от рабочих аккаунтов.",
    deploymentEyebrow: "Дополнительный модуль",
    deploymentTitle: "Validated campaign deployment",
    deploymentBody:
      "Модуль Demand Gen Uploader подготавливает проверяемый план кампаний и отделяет создание от автоматического включения.",
    deploymentSteps: [
      "Сформировать предварительный план",
      "Выполнить локальную проверку схемы, материалов, URL и домена",
      "Выполнить Google Ads validate_only",
      "Получить явное подтверждение пользователя",
      "Создать новые кампании в PAUSED",
      "Повторно прочитать созданные ресурсы и записать результат в AuditLog",
      "Никогда не включать новую кампанию автоматически"
    ],
    deploymentCaption:
      "Развёртывание кампаний — вторичный контролируемый процесс. Основой продукта остаются аналитика, мониторинг, отчётность и операционный контроль.",
    architectureTitle: "Серверная архитектура и граница секретов",
    architectureBody:
      "Браузер обращается только к защищённому API приложения. OAuth refresh tokens и реквизиты Google Ads остаются зашифрованными на backend и никогда не возвращаются frontend-коду.",
    architecture: ["React frontend", "FastAPI backend", "PostgreSQL", "Redis", "Worker", "Scheduler", "Google Ads API"],
    audienceTitle: "Доступ только владельца",
    audienceBody:
      "Рабочим кабинетом сейчас пользуется только Iskhakov Ruslan через защищённую учётную запись владельца. Доступа нет ни у сотрудников, ни у подрядчиков, ни у клиентов, ни у посторонних лиц.",
    affiliation: "Axyro Analytics — название независимого программного проекта физического лица Iskhakov Ruslan. Это не зарегистрированная компания и не отдельное юридическое лицо; проект не связан с Google и не одобрен или спонсируется Google.",
    contactTitle: "Контакт по продукту и конфиденциальности",
    contactBody: "Вопросы о продукте, использовании Google Ads API, конфиденциальности или удалении данных можно направить на:",
    footerProduct: "Axyro Analytics · Оператор: Iskhakov Ruslan (физическое лицо)"
  }
};

const featureIcons = [
  <AccountTreeOutlined />,
  <AnalyticsOutlined />,
  <PaidOutlined />,
  <CrisisAlertOutlined />,
  <FilterAltOutlined />,
  <HistoryOutlined />,
  <DownloadOutlined />,
  <TuneOutlined />
];

export function PublicSitePage() {
  const { locale } = useLocale();
  const copy = PUBLIC_COPY[locale];

  useEffect(() => {
    document.title = PUBLIC_SITE_TITLE;
  }, []);

  return (
    <PublicFrame copy={copy}>
      <Box
        component="section"
        sx={{
          position: "relative",
          minHeight: { xs: 720, md: 760 },
          display: "flex",
          alignItems: "flex-start",
          color: "common.white",
          backgroundImage: "url('/product/control-center-desktop.png')",
          backgroundSize: "cover",
          backgroundPosition: "center top",
          borderBottom: 1,
          borderColor: "divider"
        }}
      >
        <Box sx={{ position: "absolute", inset: "0 0 auto", height: { xs: "73%", md: "62%" }, bgcolor: "rgba(9, 19, 34, 0.91)" }} />
        <Container maxWidth="lg" sx={{ position: "relative", pt: { xs: 9, md: 13 }, pb: 8 }}>
          <Typography sx={{ color: "#79d6c4", fontWeight: 800, mb: 2 }}>{copy.eyebrow}</Typography>
          <Typography component="h1" sx={{ fontSize: { xs: 44, md: 62 }, lineHeight: 1.05, fontWeight: 850, maxWidth: 780, letterSpacing: 0 }}>
            Axyro Analytics
          </Typography>
          <Typography component="p" sx={{ fontSize: { xs: 22, md: 28 }, lineHeight: 1.25, mt: 2, maxWidth: 820, fontWeight: 650 }}>
            {copy.subtitle}
          </Typography>
          <Typography sx={{ mt: 3, maxWidth: 760, fontSize: 18, lineHeight: 1.65, color: "rgba(255,255,255,0.84)" }}>
            {copy.heroBody}
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 4, alignItems: { xs: "stretch", sm: "center" } }}>
            <Button component="a" href="#product" variant="contained" color="secondary" size="large" endIcon={<ArrowForward />}>
              {copy.primaryAction}
            </Button>
            <Button component="a" href="/login" variant="outlined" size="large" startIcon={<LockOutlined />} sx={{ color: "common.white", borderColor: "rgba(255,255,255,0.72)", "&:hover": { borderColor: "common.white", bgcolor: "rgba(255,255,255,0.08)" } }}>
              {copy.secondaryAction}
            </Button>
          </Stack>
        </Container>
      </Box>

      <Section id="product">
        <SectionHeading eyebrow={copy.proofLabel} title={copy.overviewTitle} body={copy.overviewLead} />
        <Box component="img" src="/product/control-center-desktop.png" alt={copy.proofLabel} sx={{ display: "block", width: "100%", mt: 5, border: 1, borderColor: "divider", borderRadius: 1 }} />
        <Typography color="text.secondary" sx={{ mt: 1.5, maxWidth: 980 }}>{copy.proofCaption}</Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" }, gap: 0, mt: 7, borderTop: 1, borderLeft: 1, borderColor: "divider" }}>
          {copy.features.map((item, index) => (
            <Box key={item.title} sx={{ minHeight: 210, p: 3, borderRight: 1, borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
              <Box sx={{ color: index % 2 === 0 ? "primary.main" : "secondary.main", mb: 2 }}>{featureIcons[index]}</Box>
              <Typography component="h3" variant="h6" sx={{ fontSize: 17 }}>{item.title}</Typography>
              <Typography color="text.secondary" sx={{ mt: 1.25, lineHeight: 1.6 }}>{item.body}</Typography>
            </Box>
          ))}
        </Box>
      </Section>

      <Section tone="muted">
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "0.8fr 1.2fr" }, gap: { xs: 4, lg: 8 } }}>
          <Typography component="h2" variant="h3" sx={{ fontSize: { xs: 32, md: 40 }, fontWeight: 800 }}>{copy.productTitle}</Typography>
          <Stack spacing={2.5}>
            {copy.productParagraphs.map((paragraph) => (
              <Typography key={paragraph} sx={{ fontSize: 17, lineHeight: 1.75 }}>{paragraph}</Typography>
            ))}
          </Stack>
        </Box>
      </Section>

      <Section>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" }, gap: { xs: 7, lg: 10 } }}>
          <Box>
            <SectionHeading icon={<AnalyticsOutlined />} title={copy.metricsTitle} body={copy.metricsBody} />
            <Stack direction="row" useFlexGap flexWrap="wrap" gap={1} sx={{ mt: 4 }}>
              {copy.metricLabels.map((label) => (
                <Box key={label} sx={{ px: 1.5, py: 1, border: 1, borderColor: "divider", bgcolor: "background.paper", borderRadius: 1, fontWeight: 700 }}>{label}</Box>
              ))}
            </Stack>
          </Box>
          <Box>
            <SectionHeading icon={<EditNoteOutlined />} title={copy.operationsTitle} body={copy.operationsBody} />
            <CheckList items={copy.operations} />
          </Box>
        </Box>
      </Section>

      <Section id="google-ads-api" tone="dark">
        <SectionHeading icon={<SecurityOutlined />} title={copy.apiTitle} body={copy.apiBody} inverted />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 1, mt: 5 }}>
          <OperationColumn title={copy.readTitle} items={copy.readItems} icon={<AnalyticsOutlined />} />
          <OperationColumn title={copy.writeTitle} items={copy.writeItems} icon={<FactCheckOutlined />} />
        </Box>
        <Box sx={{ mt: 4, p: 2.5, border: 1, borderColor: "rgba(255,255,255,0.28)", bgcolor: "rgba(255,255,255,0.06)", borderRadius: 1 }}>
          <Typography sx={{ color: "rgba(255,255,255,0.86)", lineHeight: 1.7 }}>{copy.productionNotice}</Typography>
        </Box>
      </Section>

      <Section>
        <Typography color="secondary.main" fontWeight={850}>{copy.deploymentEyebrow}</Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "0.8fr 1.2fr" }, gap: { xs: 4, lg: 8 }, mt: 1.5 }}>
          <Box>
            <Typography component="h2" sx={{ fontSize: { xs: 34, md: 44 }, fontWeight: 850, lineHeight: 1.1 }}>{copy.deploymentTitle}</Typography>
            <Typography sx={{ mt: 3, fontSize: 18, lineHeight: 1.7, color: "text.secondary" }}>{copy.deploymentBody}</Typography>
            <CheckList items={copy.deploymentSteps} />
            <Typography sx={{ mt: 3, fontWeight: 700 }}>{copy.deploymentCaption}</Typography>
          </Box>
          <Box component="img" src="/product/creation-paused-desktop.png" alt={copy.deploymentTitle} sx={{ display: "block", width: "100%", alignSelf: "start", border: 1, borderColor: "divider", borderRadius: 1 }} />
        </Box>
      </Section>

      <Section id="security" tone="muted">
        <SectionHeading icon={<LockOutlined />} title={copy.architectureTitle} body={copy.architectureBody} />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(7, 1fr)" }, mt: 5, borderTop: 1, borderLeft: 1, borderColor: "divider" }}>
          {copy.architecture.map((item, index) => (
            <Box key={item} sx={{ p: 2.25, minHeight: 92, display: "flex", alignItems: "center", fontWeight: 750, borderRight: 1, borderBottom: 1, borderColor: "divider", bgcolor: index === copy.architecture.length - 1 ? "#e8f5f1" : "background.paper" }}>
              {item}
            </Box>
          ))}
        </Box>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "repeat(2, minmax(0, 1fr))" }, gap: { xs: 5, lg: 10 }, mt: 9 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography component="h2" variant="h4">{copy.audienceTitle}</Typography>
            <Typography sx={{ mt: 2, lineHeight: 1.75 }}>{copy.audienceBody}</Typography>
            <Typography color="text.secondary" sx={{ mt: 2, lineHeight: 1.7 }}>{copy.affiliation}</Typography>
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography component="h2" variant="h4">{copy.contactTitle}</Typography>
            <Typography sx={{ mt: 2, lineHeight: 1.75 }}>{copy.contactBody}</Typography>
            <Link href="mailto:support@axyro.tech" sx={{ display: "inline-block", mt: 2, fontSize: 22, fontWeight: 800 }}>support@axyro.tech</Link>
          </Box>
        </Box>
      </Section>
    </PublicFrame>
  );
}

function PublicFrame({ copy, children }: { copy: PublicCopy; children: ReactNode }) {
  const { locale, setLocale } = useLocale();
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ minHeight: 68, gap: 2 }}>
            <Link href="/" color="inherit" underline="none" sx={{ fontWeight: 900, fontSize: 20, whiteSpace: "nowrap" }}>Axyro Analytics</Link>
            <Stack direction="row" spacing={0.5} sx={{ ml: "auto", display: { xs: "none", lg: "flex" } }}>
              <Button component="a" href="/#product" color="inherit">{copy.nav.product}</Button>
              <Button component="a" href="/#google-ads-api" color="inherit">{copy.nav.api}</Button>
              <Button component="a" href="/#security" color="inherit">{copy.nav.security}</Button>
              <Button component="a" href="/privacy" color="inherit">{copy.nav.privacy}</Button>
              <Button component="a" href="/terms" color="inherit">{copy.nav.terms}</Button>
            </Stack>
            <ToggleButtonGroup exclusive size="small" value={locale} onChange={(_event, value: Locale | null) => value && setLocale(value)} aria-label="Language" sx={{ ml: { xs: "auto", lg: 1 } }}>
              <ToggleButton value="en" aria-label="English">EN</ToggleButton>
              <ToggleButton value="ru" aria-label="Русский">RU</ToggleButton>
            </ToggleButtonGroup>
            <Button component="a" href="/login" variant="outlined" startIcon={<Login />} sx={{ display: { xs: "none", sm: "inline-flex" } }}>{copy.nav.workspace}</Button>
          </Toolbar>
        </Container>
      </AppBar>
      {children}
      <Box component="footer" sx={{ py: 5, bgcolor: "#101a29", color: "common.white" }}>
        <Container maxWidth="lg">
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ xs: "flex-start", md: "center" }}>
            <Typography fontWeight={750}>{copy.footerProduct}</Typography>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={{ xs: 1.25, sm: 2.5 }}
              alignItems={{ xs: "flex-start", sm: "center" }}
              sx={{ ml: { md: "auto" } }}
            >
              <Link href="/privacy" color="inherit">{copy.nav.privacy}</Link>
              <Link href="/terms" color="inherit">{copy.nav.terms}</Link>
              <Link href="mailto:support@axyro.tech" color="inherit">support@axyro.tech</Link>
            </Stack>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
}

function Section({ id, tone = "plain", children }: { id?: string; tone?: "plain" | "muted" | "dark"; children: ReactNode }) {
  const colors = tone === "dark" ? { bgcolor: "#101a29", color: "common.white" } : tone === "muted" ? { bgcolor: "#eef3f4" } : {};
  return (
    <Box component="section" id={id} sx={{ ...colors, py: { xs: 8, md: 12 }, scrollMarginTop: 80 }}>
      <Container maxWidth="lg">{children}</Container>
    </Box>
  );
}

function SectionHeading({ eyebrow, icon, title, body, inverted = false }: { eyebrow?: string; icon?: ReactNode; title: string; body: string; inverted?: boolean }) {
  return (
    <Box sx={{ maxWidth: 860 }}>
      {eyebrow && <Typography color={inverted ? "#79d6c4" : "secondary.main"} fontWeight={850}>{eyebrow}</Typography>}
      {icon && <Box sx={{ color: inverted ? "#79d6c4" : "primary.main", mb: 1.5 }}>{icon}</Box>}
      <Typography component="h2" sx={{ fontSize: { xs: 32, md: 42 }, lineHeight: 1.15, fontWeight: 850, letterSpacing: 0 }}>{title}</Typography>
      <Typography sx={{ mt: 2.5, fontSize: 18, lineHeight: 1.7, color: inverted ? "rgba(255,255,255,0.78)" : "text.secondary" }}>{body}</Typography>
    </Box>
  );
}

function CheckList({ items }: { items: string[] }) {
  return (
    <Stack spacing={1.5} sx={{ mt: 4 }}>
      {items.map((item) => (
        <Stack key={item} direction="row" spacing={1.5} alignItems="flex-start">
          <CheckCircleOutline color="success" fontSize="small" sx={{ mt: 0.25, flex: "0 0 auto" }} />
          <Typography sx={{ lineHeight: 1.55 }}>{item}</Typography>
        </Stack>
      ))}
    </Stack>
  );
}

function OperationColumn({ title, items, icon }: { title: string; items: string[]; icon: ReactNode }) {
  return (
    <Box sx={{ p: { xs: 3, md: 4 }, bgcolor: "rgba(255,255,255,0.06)", border: 1, borderColor: "rgba(255,255,255,0.18)", borderRadius: 1 }}>
      <Box sx={{ color: "#79d6c4" }}>{icon}</Box>
      <Typography component="h3" variant="h5" sx={{ mt: 1.5 }}>{title}</Typography>
      <Stack spacing={1.5} sx={{ mt: 3 }}>
        {items.map((item) => (
          <Stack key={item} direction="row" spacing={1.25} alignItems="flex-start">
            <CheckCircleOutline sx={{ fontSize: 19, color: "#79d6c4", mt: 0.2, flex: "0 0 auto" }} />
            <Typography sx={{ color: "rgba(255,255,255,0.82)", lineHeight: 1.55 }}>{item}</Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}
