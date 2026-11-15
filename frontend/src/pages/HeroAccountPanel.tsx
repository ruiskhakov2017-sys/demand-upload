import { useState } from "react";
import { demoAccounts } from "../domain/demoAccounts";
import type { Locale } from "../i18n";
import { REPORT_COPY } from "../i18n/enterpriseReport";
import { HERO_PANEL_COPY } from "../i18n/heroAccountPanel";
import "./HeroAccountPanel.css";

const metrics = ["spend", "cpa"] as const;
type Metric = typeof metrics[number];

export function HeroAccountPanel({ locale }: { locale: Locale }) {
  const [metric, setMetric] = useState<Metric>("spend");
  const copy = HERO_PANEL_COPY[locale];
  const currency = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", {
    style: "currency", currency: "USD", currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0, maximumFractionDigits: 2,
  });
  const rows = demoAccounts.map(({ name, values }) => {
    const [spend, conversions] = values[30];
    return { name, spend, conversions, cpa: spend / conversions };
  });
  const spend = rows.reduce((sum, row) => sum + row.spend, 0);
  const conversions = rows.reduce((sum, row) => sum + row.conversions, 0);
  const total = metric === "spend" ? spend : spend / conversions;
  const chartMax = Math.max(...rows.map(row => row[metric]));

  return <section className="ahp" aria-labelledby="ahp-title">
    <div className="ahp-meta">
      <span className="ahp-sample">{copy.demo}</span>
      <span>{REPORT_COPY[locale].date[30]}</span>
    </div>
    <div className="ahp-body">
      <h2 id="ahp-title">{copy.titles[metric]}</h2>
      <div className="ahp-switch" role="group" aria-label={copy.metric}>
        {metrics.map(key => <button key={key} type="button" aria-pressed={metric === key}
          onClick={() => setMetric(key)}>{copy.buttons[key]}</button>)}
      </div>
      <div className="ahp-chart" aria-live="polite" aria-atomic="true">
        <dl className="ahp-rows">
          {rows.map(row => <div className="ahp-row" key={row.name}>
            <dt>{row.name}</dt>
            <dd>{currency.format(row[metric])}</dd>
            <div aria-hidden="true" className="ahp-track"><span style={{width: `${100 * row[metric] / chartMax}%`}} /></div>
          </div>)}
        </dl>
        <dl className="ahp-total"><dt>{copy.totalLabels[metric]}</dt><dd>{currency.format(total)}</dd></dl>
      </div>
    </div>
  </section>;
}
