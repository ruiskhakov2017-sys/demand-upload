export const DEMO_URL = "/portfolio/login?open=1";

export const ENTERPRISE_COPY = {
  ru: {
    title: "Axyro Analytics | Аналитика Google Ads",
    nav: ["Отчёты", "Кампании", "Доступ"],
    navigation: "Разделы страницы", lang: "Switch to English", login: "Кабинет",
    hero: "Все аккаунты Google\u00a0Ads в\u00a0одном отчёте",
    lead: "Сравнивайте расходы по аккаунтам и смотрите, сколько конверсий принёс каждый из них. Сразу видно, где за конверсию вы платите больше.",
    demo: "Открыть кабинет", see: "Посмотреть отчёт",
    workflow: "Кампании", workflowTitle: "От показателей к решению",
    screens: [
      { label: "Проверка аккаунтов", title: "Разберитесь, что мешает показам", body: "Откройте аккаунт и проверьте статусы объявлений, ограничения и сроки подтверждения рекламодателя. Добавьте заметку, чтобы при следующей проверке видеть, на чём остановились.", alt: "Интерфейс Axyro с фильтрами, статусами и таблицей аккаунтов Google Ads", caption: "Кабинет Axyro · Обзор аккаунтов" },
      { label: "Создание кампании", title: "Проверьте кампанию до запуска", body: "Просмотрите план Demand Gen и результат проверки Google Ads. После вашего подтверждения кабинет создаст кампанию на паузе и сохранит результат в журнале операций.", alt: "Интерфейс Axyro для проверки и создания кампании Demand Gen на паузе", caption: "Кабинет Axyro · Подготовка кампании" }
    ],
    screenLabel: "Экраны кабинета", sample: "Демонстрационные данные", enlarge: "Открыть изображение",
    accessTitle: "Доступ и работа с данными", permissions: "Какие данные читает Axyro?", changes: "Как подтверждаются изменения?", users: "У кого есть доступ к кабинету?",
    contactTitle: "Посмотрите Axyro в работе", contact: "Сравните аккаунты, настройте таблицу, изучите кампании и сохраните заметку. Кабинет доступен сразу, без регистрации.",
    footer: "Документы и контакты"
  },
  en: {
    title: "Axyro Analytics | Google Ads Analytics",
    nav: ["Reports", "Campaigns", "Access"],
    navigation: "Page sections", lang: "Переключить на русский", login: "Workspace",
    hero: "Every Google\u00a0Ads account in one report",
    lead: "Compare spend and conversions across accounts. See how much each account delivers and where you pay more per conversion.",
    demo: "Open workspace", see: "Explore the report",
    workflow: "Campaigns", workflowTitle: "From metrics to decisions",
    screens: [
      { label: "Review accounts", title: "Find what is holding delivery back", body: "Open an account to review ad statuses, policy issues and advertiser verification deadlines. Leave a note so your next review starts where you left off.", alt: "Axyro workspace showing filters, statuses and a table of Google Ads accounts", caption: "Axyro workspace · Account overview" },
      { label: "Create a campaign", title: "Review a campaign before launch", body: "Inspect the Demand Gen plan and Google Ads validation results. Once you confirm, Axyro creates the campaign in a paused state and records the result in the audit log.", alt: "Axyro workspace for validating and creating a paused Demand Gen campaign", caption: "Axyro workspace · Campaign preparation" }
    ],
    screenLabel: "Workspace views", sample: "Demonstration data", enlarge: "Open full image",
    accessTitle: "Access and data handling", permissions: "What data does Axyro read?", changes: "How are changes confirmed?", users: "Who has access to the workspace?",
    contactTitle: "See Axyro in action", contact: "Open the workspace with sample data. Compare accounts, customize the table and explore campaigns. No registration required.",
    footer: "Documents and contact"
  }
} as const;

export const PORTFOLIO_INTRO = {
  ru: {
    hero: "Кампании Demand Gen для нескольких аккаунтов",
    lead: "Загрузите таблицу, добавьте объявления и проверьте план кампаний. В рабочем аккаунте Axyro создаёт их на паузе. В открытом кабинете можно пройти те же шаги в режиме симуляции.",
  },
  en: {
    hero: "Build Demand Gen campaigns across accounts",
    lead: "Import a spreadsheet, add your ads and review the campaign plan. Axyro creates paused campaigns in connected accounts. Try the workflow in simulation in the public workspace.",
  }
} as const;
