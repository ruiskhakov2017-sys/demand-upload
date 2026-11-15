export const DEMO_REQUEST_URL = "mailto:support@axyro.tech?subject=Axyro%20Analytics%20%E2%80%94%20Demo";

export const ENTERPRISE_COPY = {
  ru: {
    title: "Axyro Analytics | Аналитика Google Ads",
    nav: ["Отчёты", "Кампании", "Доступ"],
    navigation: "Разделы страницы", lang: "Switch to English", login: "Войти",
    category: "Аналитика Google Ads", hero: ["Экономика", "рекламы."],
    lead: "Сколько стоит конверсия? Какой аккаунт расходует бюджет быстрее остальных? Сравнивайте результаты Google Ads в одном кабинете.",
    demo: "Запросить демо", see: "Посмотреть отчёт",
    workflow: "Кампании", workflowTitle: "От показателей к решению",
    screens: [
      { label: "Проверка аккаунтов", title: "Разберитесь, что мешает показам", body: "Откройте аккаунт и проверьте статусы объявлений, ограничения и сроки подтверждения рекламодателя. Добавьте заметку, чтобы при следующей проверке видеть, на чём остановились.", alt: "Интерфейс Axyro с фильтрами, статусами и таблицей аккаунтов Google Ads", caption: "Кабинет Axyro · Обзор аккаунтов" },
      { label: "Создание кампании", title: "Проверьте кампанию до запуска", body: "Просмотрите план Demand Gen и результат проверки Google Ads. После вашего подтверждения кабинет создаст кампанию на паузе и сохранит результат в журнале операций.", alt: "Интерфейс Axyro для проверки и создания кампании Demand Gen на паузе", caption: "Кабинет Axyro · Подготовка кампании" }
    ],
    screenLabel: "Экраны кабинета", sample: "Демонстрационные данные", enlarge: "Открыть изображение",
    accessTitle: "Доступ и работа с данными", permissions: "Какие данные читает Axyro?", changes: "Как подтверждаются изменения?", users: "У кого есть доступ к кабинету?",
    contactTitle: "Посмотрите Axyro в работе", contact: "Напишите, что хотите разобрать на демо: сравнение аккаунтов, расходы или проверку кампаний.",
    footer: "Документы и контакты"
  },
  en: {
    title: "Axyro Analytics | Google Ads Analytics",
    nav: ["Reports", "Campaigns", "Access"],
    navigation: "Page sections", lang: "Переключить на русский", login: "Sign in",
    category: "Google Ads analytics", hero: ["The cost of", "performance."],
    lead: "Compare spend and conversions across Google Ads accounts. See what each acquisition costs and which accounts are spending the most.",
    demo: "Request a demo", see: "Explore the report",
    workflow: "Campaigns", workflowTitle: "From metrics to decisions",
    screens: [
      { label: "Review accounts", title: "Find what is holding delivery back", body: "Open an account to review ad statuses, policy issues and advertiser verification deadlines. Leave a note so your next review starts where you left off.", alt: "Axyro workspace showing filters, statuses and a table of Google Ads accounts", caption: "Axyro workspace · Account overview" },
      { label: "Create a campaign", title: "Review a campaign before launch", body: "Inspect the Demand Gen plan and Google Ads validation results. Once you confirm, Axyro creates the campaign in a paused state and records the result in the audit log.", alt: "Axyro workspace for validating and creating a paused Demand Gen campaign", caption: "Axyro workspace · Campaign preparation" }
    ],
    screenLabel: "Workspace views", sample: "Demonstration data", enlarge: "Open full image",
    accessTitle: "Access and data handling", permissions: "What data does Axyro read?", changes: "How are changes confirmed?", users: "Who has access to the workspace?",
    contactTitle: "See Axyro in action", contact: "Tell us what you would like to explore in a demo: account comparisons, advertising costs or campaign review.",
    footer: "Documents and contact"
  }
} as const;
