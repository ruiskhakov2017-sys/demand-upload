import { useState } from "react";
import { demoAccounts } from "../domain/demoAccounts";
import type { Locale } from "../i18n";
import { REPORT_COPY } from "../i18n/enterpriseReport";
import "./EnterpriseReport.css";

type Period = 7 | 30;

export function EnterpriseReport({ locale }: { locale: Locale }) {
  const [period, setPeriod] = useState<Period>(30);
  const t = REPORT_COPY[locale];
  const numberLocale = locale === "ru" ? "ru-RU" : "en-US";
  const integer = new Intl.NumberFormat(numberLocale);
  const money = (amount: number, decimals = 0) =>
    new Intl.NumberFormat(numberLocale, {
      style: "currency", currency: "USD", currencyDisplay: "narrowSymbol",
      minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    }).format(amount);

  const rows = demoAccounts.map(({ name, values }) => {
    const [spend, conversions] = values[period];
    return { name, spend, conversions };
  });
  const totalSpend = rows.reduce((sum, row) => sum + row.spend, 0);
  const totalConversions = rows.reduce((sum, row) => sum + row.conversions, 0);
  const cpa = money(totalSpend / totalConversions, 2);

  return (
    <section id="report" className="enterprise-report" aria-labelledby="er-title">
      <div className="er-inner">
        <div className="er-intro">
          <h2 id="er-title">{t.title}</h2>
          <p>{t.intro}</p>
        </div>
        <div className="er-sheet">
          <div className="er-heading">
            <div>
              <p className="er-sample">{t.label}</p>
              <h3>{t.report}</h3>
            </div>
            <div className="er-controls" role="group" aria-label={t.period}>
              {([7, 30] as const).map((value) => (
                <button type="button" key={value} aria-pressed={period === value}
                  onClick={() => setPeriod(value)}>{t.days[value]}</button>
              ))}
            </div>
          </div>
          <div className="er-kpis" aria-live="polite" aria-atomic="true">
            <dl>
              <div><dt>{t.spend}</dt><dd>{money(totalSpend)}</dd></div>
              <div><dt>{t.conversions}</dt><dd>{integer.format(totalConversions)}</dd></div>
              <div><dt>{t.cpa}</dt><dd>{cpa}</dd></div>
            </dl>
          </div>
          <div className="er-table-wrap">
            <table>
              <caption>{t.caption}</caption>
              <thead><tr><th scope="col">{t.account}</th><th scope="col">{t.spend}</th>
                <th scope="col">{t.conversions}</th><th scope="col"><abbr title={t.cpa}>CPA</abbr></th></tr></thead>
              <tbody>
                {rows.map(({ name, spend, conversions }) => (
                  <tr key={name}>
                    <th scope="row">{name}</th>
                    <td><span className="er-amount">
                      <span aria-hidden="true" className="er-bar"><i style={{ width: `${spend / totalSpend * 100}%` }} /></span>
                      {money(spend)}
                    </span></td>
                    <td>{integer.format(conversions)}</td><td>{money(spend / conversions, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="er-foot"><span>{t.date[period]}</span><span>USD</span></div>
        </div>
      </div>
    </section>
  );
}
