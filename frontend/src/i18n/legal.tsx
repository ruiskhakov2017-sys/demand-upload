import ArrowBack from "@mui/icons-material/ArrowBack";
import Login from "@mui/icons-material/Login";
import {
  AppBar,
  Box,
  Button,
  Container,
  Divider,
  Link,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Toolbar,
  Typography
} from "@mui/material";
import { useEffect } from "react";

import { Locale, useLocale } from ".";

type LegalSection = { title: string; paragraphs?: string[]; items?: string[] };
type LegalDocument = { title: string; updated: string; introduction: string; sections: LegalSection[] };

export const PRIVACY_COPY: Record<Locale, LegalDocument> = {
  en: {
    title: "Privacy Policy",
    updated: "Last updated: August 18, 2026",
    introduction:
      "This Privacy Policy explains how Axyro Analytics, an independent Google Ads analytics and operations software project operated by Iskhakov Ruslan, processes information on its public website and in its restricted workspace.",
    sections: [
      {
        title: "1. Controller and contact",
        paragraphs: [
          "The controller and sole operator is Iskhakov Ruslan, an individual. Axyro Analytics is a project name, not a registered company or separate legal entity. Privacy, Google Ads API, access, and deletion requests may be sent to support@axyro.tech."
        ]
      },
      {
        title: "2. Scope and intended users",
        paragraphs: [
          "The public website provides product and legal information. The workspace is not a public advertising service and is currently available only to Iskhakov Ruslan through the protected owner account. No employee, contractor, client, or member of the public has access."
        ]
      },
      {
        title: "3. Information processed",
        items: [
          "Authentication and security data: username, role, server-side session identifiers, CSRF records, login time, and security events.",
          "Google Ads account data: customer IDs, account names, MCC hierarchy, currency, time zone, account and campaign status, policy and advertiser verification status.",
          "Reporting data: cost, impressions, clicks, CTR, CPC, campaign performance, and explicitly mapped conversion metrics such as registrations and deposits.",
          "Operational data: saved views, filters, notes, tags, alerts, action previews, confirmations, results, audit entries, and Google Request IDs.",
          "Campaign deployment data: campaign plans, budgets, targeting, asset metadata, validation results, schedules, and readback results.",
          "Protected credentials: OAuth client credentials, refresh tokens, and the Google Ads Developer Token are encrypted at rest and never returned to frontend code.",
          "Public website technical data: normal web-server security logs such as timestamp, requested path, response status, IP address, and browser user agent."
        ]
      },
      {
        title: "4. Google user data and API use",
        paragraphs: [
          "Axyro Analytics requests the Google Ads OAuth scope only after an authorized user starts the connection flow. The application uses Google Ads API data primarily for reporting, analytics, monitoring, and account control, and secondarily for explicitly confirmed campaign management operations.",
          "The application reads accessible customers, MCC hierarchy, account and campaign configuration, supported performance and conversion metrics, policy and verification states, and supported budget or billing information. The owner may also initiate validated Demand Gen creation, campaign pause or enable actions, and budget updates. New campaigns are created PAUSED by default.",
          "Google user data is not sold, used for advertising, or made available as a third-party self-service product. Use and transfer of information received from Google APIs complies with the Google API Services User Data Policy, including the Limited Use requirements."
        ]
      },
      {
        title: "5. Purposes",
        items: [
          "Provide centralized reporting, performance comparison, and monitoring across connected Google Ads accounts.",
          "Detect account, campaign, policy, verification, synchronization, and operational issues.",
          "Support controlled internal workflows, explicit confirmations, post-change readback, and auditability.",
          "Protect the application, investigate errors, enforce roles, and maintain service continuity.",
          "Respond to product, privacy, access, and deletion requests."
        ]
      },
      {
        title: "6. Credential and data protection",
        items: [
          "HTTPS is required for the public production service.",
          "OAuth uses state, PKCE, an exact redirect URI, and short-lived authorization records.",
          "Refresh tokens and other protected credentials are encrypted at rest with a server-side key.",
          "Credentials and sensitive URL parameters are excluded from frontend responses and application logs.",
          "Server-side sessions, secure cookies, CSRF checks, role checks, and an AuditLog protect workspace actions.",
          "Production write operations remain disabled by a safety guard while Google Ads API Basic Access is pending."
        ]
      },
      {
        title: "7. Sharing and processors",
        paragraphs: [
          "Information is disclosed only as needed to operate the service: to Google when the owner makes an authorized API request, and to infrastructure providers that host or transmit the application and its encrypted data. It is not sold or shared for independent marketing. Application access is limited to Iskhakov Ruslan."
        ]
      },
      {
        title: "8. Retention and deletion",
        paragraphs: [
          "Connected account data, operational records, and audit evidence are retained only while needed for the internal analytics, security, and compliance purposes described above. An OAuth disconnect immediately clears the stored refresh token for that connection. The owner can remove connections and related operational data, subject to security or legal record requirements.",
          "Production backups follow a 14-day rotation. Data removed from the active system may remain in encrypted backups until that rotation expires. A deletion or access request can be sent to support@axyro.tech."
        ]
      },
      {
        title: "9. Revoking Google access",
        paragraphs: [
          "The owner can disconnect OAuth in Axyro Analytics. Google access may also be revoked from the Google Account security permissions page. Revocation prevents new API access but does not automatically erase audit records that must be retained for security or compliance."
        ]
      },
      {
        title: "10. Changes",
        paragraphs: [
          "Material changes are published on this page with an updated date. Continued internal use after a change is subject to the updated policy."
        ]
      }
    ]
  },
  ru: {
    title: "Политика конфиденциальности",
    updated: "Последнее обновление: 18 августа 2026 года",
    introduction:
      "Эта политика объясняет, как Axyro Analytics, независимый программный проект аналитики и управления Google Ads физического лица Iskhakov Ruslan, обрабатывает информацию на публичном сайте и в закрытом рабочем кабинете.",
    sections: [
      {
        title: "1. Оператор и контакт",
        paragraphs: [
          "Оператором и единственным пользователем является физическое лицо Iskhakov Ruslan. Axyro Analytics — название проекта, а не зарегистрированная компания или отдельное юридическое лицо. Запросы о конфиденциальности, Google Ads API, доступе и удалении данных можно направлять на support@axyro.tech."
        ]
      },
      {
        title: "2. Область действия и пользователи",
        paragraphs: [
          "Публичный сайт содержит информацию о продукте и юридические документы. Рабочий кабинет не является публичным рекламным сервисом и сейчас доступен только Iskhakov Ruslan через защищённую учётную запись владельца. Доступа нет у сотрудников, подрядчиков, клиентов или посторонних лиц."
        ]
      },
      {
        title: "3. Обрабатываемая информация",
        items: [
          "Данные входа и безопасности: имя пользователя, роль, серверные идентификаторы сессии, CSRF-записи, время входа и события безопасности.",
          "Данные Google Ads: Customer ID, названия аккаунтов, иерархия MCC, валюта, часовой пояс, статусы аккаунтов и кампаний, policy и advertiser verification statuses.",
          "Отчётные данные: расходы, показы, клики, CTR, CPC, статистика кампаний и явно сопоставленные конверсии, включая регистрации и депозиты.",
          "Операционные данные: сохранённые представления, фильтры, заметки, теги, уведомления, предпросмотры действий, подтверждения, результаты, AuditLog и Google Request ID.",
          "Данные развёртывания кампаний: планы, бюджеты, таргетинг, метаданные материалов, результаты проверок, расписания и повторного чтения.",
          "Защищённые реквизиты: OAuth client credentials, refresh tokens и Google Ads Developer Token шифруются при хранении и не возвращаются frontend-коду.",
          "Технические данные публичного сайта: обычные серверные журналы безопасности, например время, путь запроса, код ответа, IP-адрес и user agent браузера."
        ]
      },
      {
        title: "4. Данные Google и использование API",
        paragraphs: [
          "Axyro Analytics запрашивает OAuth scope Google Ads только после того, как авторизованный пользователь запускает подключение. Google Ads API используется в первую очередь для отчётности, аналитики, мониторинга и контроля аккаунтов, а во вторую — для явно подтверждённых операций управления кампаниями.",
          "Приложение читает доступных клиентов, иерархию MCC, настройки аккаунтов и кампаний, поддерживаемые метрики эффективности и конверсий, policy и verification states, а также поддерживаемые данные бюджетов или billing. Авторизованный пользователь также может запустить проверенное создание Demand Gen, приостановку или включение кампании и изменение бюджета. Новые кампании по умолчанию создаются в PAUSED.",
          "Данные Google не продаются, не используются для рекламы и не предоставляются как сторонний сервис самообслуживания. Использование и передача информации, полученной через Google API, соответствуют Google API Services User Data Policy, включая требования Limited Use."
        ]
      },
      {
        title: "5. Цели обработки",
        items: [
          "Централизованная отчётность, сравнение эффективности и мониторинг подключённых Google Ads аккаунтов.",
          "Обнаружение проблем аккаунтов, кампаний, policy, verification, синхронизации и операционных процессов.",
          "Контролируемые внутренние процессы, явные подтверждения, повторное чтение после изменений и аудит.",
          "Защита приложения, расследование ошибок, применение ролей и поддержание доступности сервиса.",
          "Ответы на запросы по продукту, конфиденциальности, доступу и удалению данных."
        ]
      },
      {
        title: "6. Защита реквизитов и данных",
        items: [
          "Публичная production-версия работает только по HTTPS.",
          "OAuth использует state, PKCE, точный redirect URI и короткоживущие записи авторизации.",
          "Refresh tokens и другие защищённые реквизиты шифруются серверным ключом.",
          "Реквизиты и чувствительные URL-параметры исключены из frontend-ответов и журналов приложения.",
          "Серверные сессии, secure cookies, CSRF, проверка ролей и AuditLog защищают действия в кабинете.",
          "Изменяющие операции в production остаются отключёнными предохранителем, пока ожидается Google Ads API Basic Access."
        ]
      },
      {
        title: "7. Передача и обработчики",
        paragraphs: [
          "Информация передаётся только для работы сервиса: Google при выполнении владельцем авторизованного API-запроса и инфраструктурным провайдерам, которые размещают или передают приложение и его зашифрованные данные. Информация не продаётся и не передаётся для независимого маркетинга. Доступ к приложению имеет только Iskhakov Ruslan."
        ]
      },
      {
        title: "8. Хранение и удаление",
        paragraphs: [
          "Данные подключённых аккаунтов, операционные записи и доказательства аудита хранятся только пока нужны для описанных целей аналитики, безопасности и соответствия требованиям. Отключение OAuth немедленно очищает сохранённый refresh token этого подключения. Владелец может удалить подключения и связанные операционные данные с учётом требований к журналам безопасности или юридическим записям.",
          "Production-резервные копии хранятся по 14-дневной ротации. Удалённые из активной системы данные могут оставаться в зашифрованных резервных копиях до завершения этой ротации. Запрос на удаление или доступ можно направить на support@axyro.tech."
        ]
      },
      {
        title: "9. Отзыв доступа Google",
        paragraphs: [
          "Владелец может отключить OAuth в Axyro Analytics. Доступ также можно отозвать на странице разрешений безопасности Google Account. Отзыв прекращает новый доступ к API, но не удаляет автоматически записи аудита, которые необходимо хранить для безопасности или соответствия требованиям."
        ]
      },
      {
        title: "10. Изменения",
        paragraphs: [
          "Существенные изменения публикуются на этой странице с новой датой. Дальнейшее внутреннее использование регулируется обновлённой политикой."
        ]
      }
    ]
  }
};

export const TERMS_COPY: Record<Locale, LegalDocument> = {
  en: {
    title: "Terms of Use",
    updated: "Last updated: August 18, 2026",
    introduction:
      "These Terms govern authorized internal use of Axyro Analytics and its protected Google Ads analytics and operations workspace.",
    sections: [
      {
        title: "1. Product and operator",
        paragraphs: [
          "Axyro Analytics is an independent software project operated by Iskhakov Ruslan, an individual. It is not a registered company or separate legal entity and is not affiliated with, endorsed by, or sponsored by Google. Google Ads and related marks belong to Google LLC."
        ]
      },
      {
        title: "2. Restricted audience",
        paragraphs: [
          "The workspace is currently intended and available only for Iskhakov Ruslan. No employee, contractor, external client, or member of the public has access. It is not a public self-service advertising platform, agency marketplace, API resale product, or service for unrelated third parties."
        ]
      },
      {
        title: "3. Authorized use",
        items: [
          "Analyze and compare Google Ads account and campaign performance.",
          "Monitor MCC hierarchy, account state, policy issues, advertiser verification, alerts, and change history.",
          "Maintain internal notes, tags, saved views, and reports.",
          "Initiate permitted campaign actions only for accounts that Iskhakov Ruslan is authorized to manage and that are connected through his manager account."
        ]
      },
      {
        title: "4. Campaign operations",
        paragraphs: [
          "The platform includes secondary write functions for validated Demand Gen creation, pausing or enabling selected campaigns, and updating selected budgets. Every write action must be initiated by an authorized user, reviewed in a preview, validated, explicitly confirmed, recorded in AuditLog, and checked by readback when supported. New campaigns are created PAUSED and are not enabled automatically.",
          "Production write operations are currently blocked until Google Ads API Basic Access is granted and the application safety controls are deliberately enabled. Users must not attempt to bypass those controls."
        ]
      },
      {
        title: "5. Account responsibilities",
        items: [
          "Keep credentials and sessions private and use only the assigned account.",
          "Confirm that every connected Google Ads account is authorized for internal management.",
          "Review previews, validation results, target accounts, budgets, and statuses before confirming an action.",
          "Follow Google Ads policies, Google Ads API Terms, applicable law, and internal approval requirements.",
          "Report suspected unauthorized access or incorrect data to support@axyro.tech."
        ]
      },
      {
        title: "6. Prohibited use",
        items: [
          "No credential sharing, unauthorized account access, security bypass, automated abuse, or quota circumvention.",
          "No resale, sublicensing, or public access to Google Ads API functionality.",
          "No use to misrepresent identity, evade policy enforcement, or publish unlawful or deceptive advertising.",
          "No extraction of secrets, tokens, private keys, or data belonging to another user or account."
        ]
      },
      {
        title: "7. Availability and data",
        paragraphs: [
          "Reporting depends on Google Ads API availability, permissions, mapping configuration, synchronization time, and source-account state. Missing data is not represented as zero when its meaning is unknown. The operator may pause workflows to protect data integrity, quota, security, or compliance."
        ]
      },
      {
        title: "8. Suspension and termination",
        paragraphs: [
          "The owner may suspend or revoke workspace access when authorization ends, security is at risk, these Terms are violated, or continued access could affect Google Ads accounts or other users. OAuth access can be disconnected separately."
        ]
      },
      {
        title: "9. Privacy and contact",
        paragraphs: [
          "Processing of information is described in the Axyro Analytics Privacy Policy. Questions about these Terms may be sent to support@axyro.tech."
        ]
      }
    ]
  },
  ru: {
    title: "Условия использования",
    updated: "Последнее обновление: 18 августа 2026 года",
    introduction:
      "Эти условия регулируют авторизованное внутреннее использование Axyro Analytics и защищённого кабинета аналитики и операций Google Ads.",
    sections: [
      {
        title: "1. Продукт и оператор",
        paragraphs: [
          "Axyro Analytics — независимый программный проект физического лица Iskhakov Ruslan. Это не зарегистрированная компания и не отдельное юридическое лицо; проект не связан с Google и не одобрен или спонсируется Google. Google Ads и связанные обозначения принадлежат Google LLC."
        ]
      },
      {
        title: "2. Ограниченная аудитория",
        paragraphs: [
          "Рабочий кабинет сейчас предназначен и доступен только Iskhakov Ruslan. Доступа нет у сотрудников, подрядчиков, внешних клиентов или посторонних лиц. Это не публичная рекламная платформа самообслуживания, не маркетплейс агентств, не продукт перепродажи API и не сервис для несвязанных третьих лиц."
        ]
      },
      {
        title: "3. Разрешённое использование",
        items: [
          "Анализ и сравнение эффективности аккаунтов и кампаний Google Ads.",
          "Мониторинг иерархии MCC, состояния аккаунтов, policy issues, advertiser verification, уведомлений и истории изменений.",
          "Ведение внутренних заметок, тегов, сохранённых представлений и отчётов.",
          "Запуск разрешённых действий с кампаниями только в аккаунтах, которыми Iskhakov Ruslan вправе управлять и которые подключены через его MCC."
        ]
      },
      {
        title: "4. Операции с кампаниями",
        paragraphs: [
          "Платформа включает вторичные write-функции: проверенное создание Demand Gen, приостановка или включение выбранных кампаний и изменение выбранных бюджетов. Каждое изменяющее действие запускается авторизованным пользователем, просматривается в preview, проверяется, явно подтверждается, записывается в AuditLog и, где возможно, проверяется повторным чтением. Новые кампании создаются в PAUSED и не включаются автоматически.",
          "Изменяющие операции в production сейчас заблокированы до получения Google Ads API Basic Access и осознанного включения предохранителей приложения. Пользователь не должен пытаться обходить эти ограничения."
        ]
      },
      {
        title: "5. Обязанности пользователя",
        items: [
          "Хранить реквизиты и сессии в тайне и использовать только назначенную учётную запись.",
          "Убедиться, что каждый подключённый Google Ads аккаунт разрешён для внутреннего управления.",
          "Проверять preview, результаты валидации, целевые аккаунты, бюджеты и статусы до подтверждения.",
          "Соблюдать правила Google Ads, Google Ads API Terms, применимое право и внутренние согласования.",
          "Сообщать о подозрительном доступе или некорректных данных на support@axyro.tech."
        ]
      },
      {
        title: "6. Запрещённое использование",
        items: [
          "Запрещены передача реквизитов, несанкционированный доступ, обход защиты, автоматизированные злоупотребления и обход квот.",
          "Запрещены перепродажа, сублицензирование и публичный доступ к функциям Google Ads API.",
          "Запрещено использовать продукт для искажения личности, обхода правил или публикации незаконной либо вводящей в заблуждение рекламы.",
          "Запрещено извлекать секреты, токены, приватные ключи или данные другого пользователя или аккаунта."
        ]
      },
      {
        title: "7. Доступность и данные",
        paragraphs: [
          "Отчётность зависит от доступности Google Ads API, разрешений, настройки сопоставлений, времени синхронизации и состояния исходного аккаунта. Отсутствующие данные не показываются как ноль, если их смысл неизвестен. Оператор может приостановить процессы для защиты целостности данных, квот, безопасности или соответствия требованиям."
        ]
      },
      {
        title: "8. Приостановка и прекращение доступа",
        paragraphs: [
          "Владелец может приостановить или отозвать доступ, если авторизация закончилась, возник риск безопасности, нарушены эти условия или продолжение доступа может повлиять на Google Ads аккаунты или других пользователей. OAuth можно отключить отдельно."
        ]
      },
      {
        title: "9. Конфиденциальность и контакт",
        paragraphs: [
          "Обработка информации описана в Политике конфиденциальности Axyro Analytics. Вопросы об условиях можно направлять на support@axyro.tech."
        ]
      }
    ]
  }
};

export function LegalPage({ kind }: { kind: "privacy" | "terms" }) {
  const { locale, setLocale } = useLocale();
  const documentCopy = (kind === "privacy" ? PRIVACY_COPY : TERMS_COPY)[locale];

  useEffect(() => {
    document.title = `${documentCopy.title} | Axyro Analytics`;
  }, [documentCopy.title]);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Container maxWidth="md">
          <Toolbar disableGutters sx={{ minHeight: 68, gap: 2 }}>
            <Link href="/" color="inherit" underline="none" sx={{ fontWeight: 900, fontSize: 20 }}>Axyro Analytics</Link>
            <ToggleButtonGroup exclusive size="small" value={locale} onChange={(_event, value: Locale | null) => value && setLocale(value)} aria-label="Language" sx={{ ml: "auto" }}>
              <ToggleButton value="en">EN</ToggleButton>
              <ToggleButton value="ru">RU</ToggleButton>
            </ToggleButtonGroup>
            <Button component="a" href="/login" variant="outlined" startIcon={<Login />} sx={{ display: { xs: "none", sm: "inline-flex" } }}>
              {locale === "en" ? "Workspace" : "Кабинет"}
            </Button>
          </Toolbar>
        </Container>
      </AppBar>

      <Container component="main" maxWidth="md" sx={{ py: { xs: 7, md: 10 } }}>
        <Button component="a" href="/" startIcon={<ArrowBack />} sx={{ mb: 4 }}>
          {locale === "en" ? "Product page" : "Страница продукта"}
        </Button>
        <Typography component="h1" sx={{ fontSize: { xs: 38, md: 52 }, lineHeight: 1.08, fontWeight: 850 }}>{documentCopy.title}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1.5 }}>{documentCopy.updated}</Typography>
        <Typography sx={{ mt: 4, fontSize: 19, lineHeight: 1.75 }}>{documentCopy.introduction}</Typography>
        <Divider sx={{ my: 6 }} />
        <Stack spacing={6}>
          {documentCopy.sections.map((section) => (
            <Box component="section" key={section.title}>
              <Typography component="h2" variant="h4" sx={{ fontSize: 26 }}>{section.title}</Typography>
              {section.paragraphs?.map((paragraph) => (
                <Typography key={paragraph} sx={{ mt: 2, lineHeight: 1.8 }}>{renderEmail(paragraph)}</Typography>
              ))}
              {section.items && (
                <Box component="ul" sx={{ mt: 2, pl: 3, mb: 0 }}>
                  {section.items.map((item) => (
                    <Typography component="li" key={item} sx={{ pl: 0.5, mb: 1.5, lineHeight: 1.7 }}>{item}</Typography>
                  ))}
                </Box>
              )}
            </Box>
          ))}
        </Stack>
        <Divider sx={{ my: 7 }} />
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
          <Link href="/privacy">{locale === "en" ? "Privacy Policy" : "Политика конфиденциальности"}</Link>
          <Link href="/terms">{locale === "en" ? "Terms of Use" : "Условия использования"}</Link>
          <Link href="mailto:support@axyro.tech">support@axyro.tech</Link>
        </Stack>
      </Container>
    </Box>
  );
}

function renderEmail(text: string) {
  const parts = text.split("support@axyro.tech");
  if (parts.length === 1) return text;
  return (
    <>
      {parts[0]}
      <Link href="mailto:support@axyro.tech">support@axyro.tech</Link>
      {parts.slice(1).join("support@axyro.tech")}
    </>
  );
}
