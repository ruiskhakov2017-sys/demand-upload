import type { Locale } from ".";

type SalesLandingCopy = {
  title: string;
  nav: { label: string; language: string; product: string; workflow: string; access: string; login: string };
  audience: string;
  hero: [string, string];
  lead: string;
  demo: string;
  seeProduct: string;
  screen: string;
  screenAlt: string;
  sample: string;
  exampleStatus: string;
  exampleAction: string;
  proof: string[];
  workflowTitle: string;
  workflowLead: string;
  workflowLabel: string;
  steps: Array<{ label: string; title: string; body: string; alt: string }>;
  featuresTitle: string;
  features: Array<{ title: string; body: string }>;
  campaignLabel: string;
  campaignTitle: string;
  campaignBody: string;
  campaignSteps: string[];
  campaignAlt: string;
  contactTitle: string;
  contactBody: string;
  questionsTitle: string;
  questions: Array<{ question: string; answer: string }>;
};

export const DEMO_REQUEST_URL = "mailto:support@axyro.tech?subject=Axyro%20Analytics%20demo";

export const SALES_COPY: Record<Locale, SalesLandingCopy> = {
  ru: {
    title: "Axyro Analytics | Управление и аналитика Google Ads",
    nav: { label: "Разделы страницы", language: "Язык", product: "Возможности", workflow: "Как это работает", access: "Доступ", login: "Вход" },
    audience: "Для тех, кто ведёт несколько аккаунтов Google Ads",
    hero: ["Весь Google Ads", "под контролем"],
    lead: "Сравнивайте расходы и конверсии, находите проблемы с показом и проверяйте изменения кампаний из одного кабинета.",
    demo: "Запросить демо",
    seeProduct: "Посмотреть сценарий",
    screen: "Центр контроля",
    screenAlt: "Интерфейс Axyro со сводкой по аккаунтам, расходам и кампаниям Google Ads",
    sample: "Демоданные",
    exampleStatus: "активных проблем",
    exampleAction: "Проверить статусы и причины",
    proof: ["Несколько аккаунтов", "Расходы и конверсии", "Проверка изменений"],
    workflowTitle: "С чего начать проверку аккаунтов",
    workflowLead: "Пример работы в Axyro. Выберите шаг, чтобы посмотреть соответствующий участок интерфейса.",
    workflowLabel: "Шаги сценария",
    steps: [
      { label: "Сравнить", title: "Посмотрите, куда уходит бюджет", body: "Выберите период и сравните расходы, клики и конверсии. Отфильтруйте аккаунты по управляющему аккаунту, рынку, статусу или тегу.", alt: "Сводные карточки аккаунтов и расходов в Центре контроля" },
      { label: "Найти проблему", title: "Откройте аккаунты, где нужна проверка", body: "Отделите проблемы синхронизации, статусы аккаунтов и вопросы верификации от обычных изменений показателей. Рабочие заметки и история остаются рядом с данными.", alt: "Таблица аккаунтов с выделенными статусами Google Ads" },
      { label: "Поделиться", title: "Выгрузите нужную выборку", body: "Сохраните набор фильтров для следующей проверки. Выгрузите данные аккаунтов или кампаний в CSV или XLSX, чтобы передать их коллегам или продолжить анализ.", alt: "Фильтры, сохранённые представления и кнопки CSV и XLSX" }
    ],
    featuresTitle: "Что можно делать в Axyro",
    features: [
      { title: "Следить за показателями", body: "Расходы, показы, клики, CTR, CPC и сопоставленные конверсии. Axyro показывает, когда для расчёта метрики не хватает данных." },
      { title: "Вести работу по аккаунтам", body: "Фильтры, заметки, теги, задачи на проверку и история помогают вернуться к тому, что уже было сделано." },
      { title: "Проверять изменения", body: "Посмотрите, какие кампании затронет ручное изменение статуса или бюджета. Подтвердите действие и проверьте результат в журнале." }
    ],
    campaignLabel: "Дополнительный модуль",
    campaignTitle: "Сначала план. Затем создание кампаний",
    campaignBody: "Подготовьте кампании Demand Gen и проверьте аккаунты, бюджеты и материалы перед созданием.",
    campaignSteps: ["Просмотрите план и результат проверки", "Подтвердите создание кампаний", "Проверьте статус «На паузе» и запись в журнале"],
    campaignAlt: "Результат демонстрационного прогона с кампаниями Demand Gen на паузе",
    contactTitle: "Посмотрим Axyro на примере вашей задачи",
    contactBody: "Расскажите, сколько аккаунтов вы ведёте и что проверяете чаще всего. Обсудим демонстрацию и условия подключения.",
    questionsTitle: "Частые вопросы",
    questions: [
      { question: "Кому подойдёт Axyro?", answer: "Тому, кто ведёт несколько аккаунтов Google Ads и хочет видеть аналитику, статусы и историю действий в одном кабинете." },
      { question: "Как посмотреть демонстрацию?", answer: "Нажмите «Запросить демо», чтобы написать владельцу проекта. Он обсудит с вами сценарий и условия подключения." }
    ]
  },
  en: {
    title: "Axyro Analytics | Google Ads Analytics & Control Center",
    nav: { label: "Page sections", language: "Language", product: "Features", workflow: "How it works", access: "Access", login: "Sign in" },
    audience: "For people managing multiple Google Ads accounts",
    hero: ["Stay on top of", "your Google Ads"],
    lead: "Compare spend and conversions, spot delivery issues, and review campaign changes from one workspace.",
    demo: "Request a demo",
    seeProduct: "See how it works",
    screen: "Control center",
    screenAlt: "Axyro control center with an overview of Google Ads accounts, spend and campaigns",
    sample: "Demo data",
    exampleStatus: "active issues",
    exampleAction: "Review statuses and issues",
    proof: ["Multiple accounts", "Spend and conversions", "Review before changes"],
    workflowTitle: "Start with an account review",
    workflowLead: "Follow a typical Axyro workflow. Select a step to see the relevant part of the workspace.",
    workflowLabel: "Workflow steps",
    steps: [
      { label: "Compare", title: "See where the budget goes", body: "Choose a date range and compare spend, clicks and conversions. Filter accounts by manager account, market, status or tag.", alt: "Account and spend summary cards in the control center" },
      { label: "Find issues", title: "Open the accounts that need attention", body: "Separate sync problems, account statuses and verification issues from routine changes in performance. Keep notes and history alongside the data.", alt: "Account table with Google Ads statuses highlighted" },
      { label: "Share", title: "Export the view you need", body: "Save your filters for the next review. Export account or campaign data as CSV or XLSX to share it with colleagues or continue your analysis.", alt: "Filters, saved views, and the CSV and XLSX export controls" }
    ],
    featuresTitle: "What you can do in Axyro",
    features: [
      { title: "Track performance", body: "Review spend, impressions, clicks, CTR, CPC and mapped conversions. Axyro indicates when a metric lacks the data it needs." },
      { title: "Organize account work", body: "Filters, notes, tags, issues and history make it easy to pick up where you left off." },
      { title: "Review changes", body: "See which campaigns a manual budget or status change will affect. Confirm the action and check the result in the audit log." }
    ],
    campaignLabel: "Additional module",
    campaignTitle: "Plan first. Then create campaigns",
    campaignBody: "Prepare Demand Gen campaigns and check the accounts, budgets and assets before creation.",
    campaignSteps: ["Review the plan and validation results", "Confirm campaign creation", "Check the paused status and audit entry"],
    campaignAlt: "Demo results showing paused Demand Gen campaigns",
    contactTitle: "See how Axyro could fit your work",
    contactBody: "Tell us how many accounts you manage and what you check most often. We can discuss a demo and access options.",
    questionsTitle: "Frequently asked questions",
    questions: [
      { question: "Who is Axyro for?", answer: "People who manage multiple Google Ads accounts and want analytics, statuses and change history in one workspace." },
      { question: "How do I see a demo?", answer: "Select Request a demo to email the project owner and discuss a walkthrough and access options." }
    ]
  }
};
