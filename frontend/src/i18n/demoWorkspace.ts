export const DEMO_WORKSPACE_COPY = {
  ru: {
    demo: "Демо",
    title: "Демонстрационный кабинет",
    navigation: "Разделы кабинета",
    menu: "Открыть меню",
    home: "На главную",
    language: "Switch to English",
    sections: {
      "control-center": "Обзор аккаунтов",
      statistics: "Статистика",
      finance: "Финансы",
      alerts: "Уведомления",
      moderation: "Модерация",
      audit: "Журнал действий"
    },
    notice: "Вы изучаете пример с демонстрационными данными. Изменения сохраняются в этом браузере.",
    reset: "Начать заново",
    loading: "Загрузка кабинета",
    skip: "Перейти к содержимому",
    unknown: "Такого раздела в демо нет",
    unknownBody: "Откройте обзор аккаунтов или выберите раздел в меню.",
    back: "Открыть обзор аккаунтов"
  },
  en: {
    demo: "Demo",
    title: "Demo workspace",
    navigation: "Workspace sections",
    menu: "Open menu",
    home: "Back to home",
    language: "Переключить на русский",
    sections: {
      "control-center": "Account overview",
      statistics: "Statistics",
      finance: "Finance",
      alerts: "Notifications",
      moderation: "Moderation",
      audit: "Activity log"
    },
    notice: "You are exploring sample data. Changes are saved in this browser.",
    reset: "Start again",
    loading: "Loading workspace",
    skip: "Skip to content",
    unknown: "This demo section is unavailable",
    unknownBody: "Open the account overview or choose a section from the menu.",
    back: "Open account overview"
  }
} as const;
