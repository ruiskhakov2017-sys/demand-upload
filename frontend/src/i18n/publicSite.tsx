export const PUBLIC_COPY = {
  en: {
    nav: {
      privacy: "Privacy",
      terms: "Terms"
    },
    apiTitle: "How Google Ads API is used",
    apiBody: "Primary use: reporting, analytics and monitoring. Secondary use: explicitly confirmed campaign management operations.",
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
    productionNotice: "Google Ads API Explorer access permits supported production operations with preview, explicit confirmation, idempotency safeguards, audit logging, and readback. Test-account operations remain isolated from production accounts.",
    deploymentSteps: [
      "Build a preliminary plan",
      "Run local schema, asset, URL, and domain checks",
      "Run Google Ads validate_only",
      "Require explicit user confirmation",
      "Create new campaigns in PAUSED",
      "Read created resources back and write the result to AuditLog",
      "Never enable a newly created campaign automatically"
    ],
    architectureBody: "The browser communicates only with the protected application API. OAuth refresh tokens and Google Ads credentials stay encrypted on the backend and are never returned to frontend code.",
    audienceTitle: "Sole-operator access",
    audienceBody: "The workspace is currently used only by Iskhakov Ruslan through the protected owner account. No employee, contractor, client, or member of the public has access.",
    affiliation: "Axyro Analytics is the name of an independent software project operated by Iskhakov Ruslan, an individual. It is not a registered company or separate legal entity and is not affiliated with, endorsed by, or sponsored by Google.",
    footerProduct: "Axyro Analytics · Operated by Iskhakov Ruslan (individual)"
  },
  ru: {
    nav: {
      privacy: "Конфиденциальность",
      terms: "Условия"
    },
    apiTitle: "Как используется Google Ads API",
    apiBody: "Основное использование: отчётность, аналитика и мониторинг. Вторичное использование: явно подтверждённые операции управления кампаниями.",
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
    productionNotice: "Google Ads API Explorer разрешает поддерживаемые production-операции с preview, явным подтверждением, idempotency-защитой, аудитом и readback. Операции тестовых аккаунтов изолированы от рабочих аккаунтов.",
    deploymentSteps: [
      "Сформировать предварительный план",
      "Выполнить локальную проверку схемы, материалов, URL и домена",
      "Выполнить Google Ads validate_only",
      "Получить явное подтверждение пользователя",
      "Создать новые кампании в PAUSED",
      "Повторно прочитать созданные ресурсы и записать результат в AuditLog",
      "Никогда не включать новую кампанию автоматически"
    ],
    architectureBody: "Браузер обращается только к защищённому API приложения. OAuth refresh tokens и реквизиты Google Ads остаются зашифрованными на backend и никогда не возвращаются frontend-коду.",
    audienceTitle: "Доступ только владельца",
    audienceBody: "Рабочим кабинетом сейчас пользуется только Iskhakov Ruslan через защищённую учётную запись владельца. Доступа нет ни у сотрудников, ни у подрядчиков, ни у клиентов, ни у посторонних лиц.",
    affiliation: "Axyro Analytics — название независимого программного проекта физического лица Iskhakov Ruslan. Это не зарегистрированная компания и не отдельное юридическое лицо; проект не связан с Google и не одобрен или спонсируется Google.",
    footerProduct: "Axyro Analytics · Оператор: Iskhakov Ruslan (физическое лицо)"
  }
};
