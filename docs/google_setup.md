# Настройка Google Ads

Актуальная пошаговая инструкция находится в разделах 7–10 полного [руководства оператора](user_guide.md#7-что-подготовить-до-подключения-google).

## Что требуется

- Google Ads Manager Account (MCC);
- Developer Token из API Center MCC;
- дочерние аккаунты, связанные с MCC;
- OAuth Web Application либо Service Account;
- пользователь или service account с достаточным доступом к MCC.

## OAuth Web

OAuth Web полностью реализован и используется по умолчанию.

1. Создайте Google Cloud project и включите Google Ads API.
2. Настройте OAuth consent screen.
3. Создайте OAuth Client типа `Web application`.
4. Добавьте точный redirect URI:

   `http://localhost/api/google-connections/oauth/callback`

5. В панели откройте **Подключения Google**.
6. Введите MCC Customer ID, Developer Token, OAuth Client ID и Client Secret.
7. Нажмите **Сохранить и войти через Google**.
8. После возврата нажмите **Проверить**, затем **Аккаунты**.

Для другого домена callback строится из `APP_PUBLIC_BASE_URL`; адрес в Google Cloud должен совпадать с ним точно.

## Service Account

1. Создайте service account в Google Cloud.
2. Скачайте JSON key.
3. Добавьте email service account как пользователя MCC с достаточным уровнем доступа.
4. В панели создайте подключение типа `SERVICE_ACCOUNT`.
5. Введите MCC Customer ID, Developer Token и полный JSON key.
6. Нажмите **Проверить**, затем **Аккаунты**.

## Ожидаемый результат

- подключение имеет статус `CONNECTED`;
- в разделе **Аккаунты MCC** видны нужные дочерние аккаунты;
- их Customer ID, валюта и часовой пояс корректны.

Для безопасной проверки Campaign Builder используйте `TEST / MOCK`: этот режим не обращается к Google и не создаёт реальные ресурсы.

Официальные материалы:

- [OAuth для Google Ads API](https://developers.google.com/google-ads/api/docs/oauth/overview)
- [Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token)
- [Service Account workflow](https://developers.google.com/google-ads/api/docs/oauth/service-accounts)
