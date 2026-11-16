import { getLocale } from ".";
const copy = {
  ru: {
    unsupported: "Эта операция недоступна в демонстрационном кабинете. Здесь можно изучить отчёты и попробовать работу с примером данных.",
    missing: "Объект примера не найден. Обновите страницу или сбросьте демо.",
    invalid: "Проверьте заполненные значения.",
    connection: "Демонстрационное подключение", note: "Проверить результаты после обновления объявлений.",
    issue: "Объявление требует проверки", issueBody: "В примере одно объявление ожидает исправления текста перед повторной проверкой.",
    verification: "Подтвердить рекламодателя", verificationBody: "В примере аккаунту требуется подтверждение данных рекламодателя.",
    sample: "Демонстрационные данные", refreshed: "Демонстрационные данные обновлены", tag: "Приоритет",
    rule: "Проверить кампании с расходами выше 500 USD", view: "Аккаунты в работе",
    sync: "Обновление примера", action: "Изменение в демо", saved: "Данные сохранены в этом браузере",
    export: ["Аккаунт", "Customer ID", "Валюта", "Расходы", "Конверсии", "Цена конверсии", "Статус"],
    finance: "Рекламный бюджет", draft: "Demand Gen · Осенняя коллекция", headline: "Новая коллекция",
  },
  en: {
    unsupported: "This operation is unavailable in the demo workspace. Explore reports and try the sample-data controls.",
    missing: "Sample object not found. Refresh the page or reset the demo.",
    invalid: "Check the entered values.",
    connection: "Demo connection", note: "Review results after the ad update.",
    issue: "Ad review required", issueBody: "One sample ad needs a text correction before it can be reviewed again.",
    verification: "Verify advertiser", verificationBody: "The sample account requires advertiser verification.",
    sample: "Sample data", refreshed: "Sample data refreshed", tag: "Priority",
    rule: "Review campaigns spending over 500 USD", view: "Working accounts",
    sync: "Sample refresh", action: "Demo change", saved: "Saved in this browser",
    export: ["Account", "Customer ID", "Currency", "Spend", "Conversions", "Cost per conversion", "Status"],
    finance: "Advertising budget", draft: "Demand Gen · Autumn collection", headline: "New collection",
  }
};
export function demoCopy() { return copy[getLocale()]; }
