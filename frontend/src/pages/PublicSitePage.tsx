import ArrowForward from "@mui/icons-material/ArrowForward";
import BarChartRounded from "@mui/icons-material/BarChartRounded";
import Check from "@mui/icons-material/Check";
import ChevronRight from "@mui/icons-material/ChevronRight";
import MonitorHeartOutlined from "@mui/icons-material/MonitorHeartOutlined";
import OpenInNew from "@mui/icons-material/OpenInNew";
import TuneRounded from "@mui/icons-material/TuneRounded";
import { useEffect, useState } from "react";

import { useLocale, type Locale } from "../i18n";
import { PUBLIC_COPY } from "../i18n/publicSite";
import { DEMO_REQUEST_URL, SALES_COPY } from "../i18n/salesLanding";
import "./PublicSitePage.css";

const controlCenterImage = "/product/control-center-desktop.png";
const campaignImage = "/product/creation-paused-desktop.png";
const featureIcons = [BarChartRounded, MonitorHeartOutlined, TuneRounded];
const panels = ["overview", "issues", "export"] as const;

export function PublicSitePage() {
  const { locale, setLocale } = useLocale();
  const copy = SALES_COPY[locale];
  const disclosure = PUBLIC_COPY[locale];
  const [step, setStep] = useState(0);
  const selectedStep = copy.steps[step];

  useEffect(() => {
    document.title = copy.title;
  }, [copy.title]);

  return (
    <div className="axyro-landing">
      <header className="axyro-header">
        <div className="axyro-container axyro-header-content">
          <a className="axyro-brand" href="/" aria-label="Axyro Analytics">
            <span className="axyro-brand-mark"><BarChartRounded fontSize="small" aria-hidden="true" /></span>
            <span>Axyro<span className="axyro-brand-light"> Analytics</span></span>
          </a>
          <nav className="axyro-nav" aria-label={copy.nav.label}>
            <a href="#features">{copy.nav.product}</a>
            <a href="#product">{copy.nav.workflow}</a>
            <a href="#access">{copy.nav.access}</a>
          </nav>
          <div className="axyro-header-actions">
            <div className="axyro-locales" role="group" aria-label={copy.nav.language}>
              {(["ru", "en"] as Locale[]).map((language) => (
                <button key={language} type="button" aria-pressed={locale === language} onClick={() => setLocale(language)}>
                  {language.toUpperCase()}
                </button>
              ))}
            </div>
            <a className="axyro-login" href="/login">{copy.nav.login}<OpenInNew aria-hidden="true" /></a>
          </div>
        </div>
      </header>

      <main>
        <section className="axyro-hero" aria-labelledby="axyro-hero-title">
          <div className="axyro-container axyro-hero-grid">
            <div className="axyro-hero-text">
              <p className="axyro-audience">{copy.audience}</p>
              <h1 id="axyro-hero-title">{copy.hero[0]} <span>{copy.hero[1]}</span></h1>
              <p className="axyro-intro">{copy.lead}</p>
              <div className="axyro-actions">
                <a className="axyro-button axyro-primary" href={DEMO_REQUEST_URL}>{copy.demo}<ArrowForward aria-hidden="true" /></a>
                <a className="axyro-button axyro-secondary" href="#product">{copy.seeProduct}<ChevronRight aria-hidden="true" /></a>
              </div>
            </div>

            <figure className="axyro-hero-visual">
              <div className="axyro-screen">
                <div className="axyro-screen-bar">
                  <span className="axyro-screen-label"><BarChartRounded aria-hidden="true" />{copy.screen}</span>
                  <span className="axyro-sample">{copy.sample}</span>
                </div>
                <div className="axyro-hero-crop">
                  <img src={controlCenterImage} alt={copy.screenAlt} width="1425" height="891" fetchPriority="high" />
                </div>
              </div>
              <div className="axyro-insight">
                <span className="axyro-insight-icon"><MonitorHeartOutlined aria-hidden="true" /></span>
                <div><strong>12 {copy.exampleStatus}</strong><span>{copy.exampleAction}</span></div>
              </div>
            </figure>
          </div>
          <ul className="axyro-container axyro-proof">
            {copy.proof.map((item) => <li key={item}><Check aria-hidden="true" />{item}</li>)}
          </ul>
        </section>

        <section id="product" className="axyro-section" aria-labelledby="axyro-workflow-title">
          <div className="axyro-container">
            <h2 id="axyro-workflow-title">{copy.workflowTitle}</h2>
            <p className="axyro-section-lead">{copy.workflowLead}</p>
            <div className="axyro-workflow">
              <div className="axyro-step-content">
                <div className="axyro-steps" role="group" aria-label={copy.workflowLabel}>
                  {copy.steps.map((item, index) => (
                    <button key={index} type="button" aria-pressed={index === step} onClick={() => setStep(index)}>{item.label}</button>
                  ))}
                </div>
                <div className="axyro-step-description" aria-live="polite">
                  <h3>{selectedStep.title}</h3>
                  <p>{selectedStep.body}</p>
                </div>
              </div>
              <figure className="axyro-workflow-figure">
                <div className={`axyro-workflow-image axyro-panel-${panels[step]}`}>
                  <img src={controlCenterImage} alt={selectedStep.alt} width="1425" height="891" loading="lazy" />
                </div>
                <figcaption>{copy.screen} · {copy.sample}</figcaption>
              </figure>
            </div>
          </div>
        </section>

        <section id="features" className="axyro-section axyro-features" aria-labelledby="axyro-features-title">
          <div className="axyro-container">
            <h2 id="axyro-features-title">{copy.featuresTitle}</h2>
            <div className="axyro-feature-grid">
              {copy.features.map((item, index) => {
                const Icon = featureIcons[index];
                return (
                  <article className="axyro-feature" key={item.title}>
                    <span className="axyro-feature-icon"><Icon aria-hidden="true" /></span>
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="axyro-section axyro-campaign" aria-labelledby="axyro-campaign-title">
          <div className="axyro-container axyro-campaign-grid">
            <div>
              <p className="axyro-campaign-label">{copy.campaignLabel}</p>
              <h2 id="axyro-campaign-title">{copy.campaignTitle}</h2>
              <p>{copy.campaignBody}</p>
              <ul>
                {copy.campaignSteps.map((item) => <li key={item}><Check aria-hidden="true" />{item}</li>)}
              </ul>
            </div>
            <figure>
              <img className="axyro-campaign-image" src={campaignImage} alt={copy.campaignAlt} loading="lazy" />
              <figcaption>{copy.sample}</figcaption>
            </figure>
          </div>
        </section>

        <section id="access" className="axyro-section" aria-labelledby="axyro-contact-title">
          <div className="axyro-container">
            <div className="axyro-contact">
              <div><h2 id="axyro-contact-title">{copy.contactTitle}</h2><p>{copy.contactBody}</p></div>
              <a className="axyro-button axyro-primary" href={DEMO_REQUEST_URL}>{copy.demo}<ArrowForward aria-hidden="true" /></a>
            </div>
            <div className="axyro-faq">
              <h2>{copy.questionsTitle}</h2>
              <div>
                {copy.questions.map((item) => (
                  <details key={item.question}><summary>{item.question}</summary><p>{item.answer}</p></details>
                ))}
                <details id="google-ads-api">
                  <summary>{disclosure.apiTitle}</summary>
                  <p>{disclosure.apiBody}</p>
                  <strong>{disclosure.readTitle}</strong>
                  <ul>{disclosure.readItems.map((item) => <li key={item}>{item}</li>)}</ul>
                  <strong>{disclosure.writeTitle}</strong>
                  <ul>{disclosure.writeItems.map((item) => <li key={item}>{item}</li>)}</ul>
                  <p>{disclosure.productionNotice}</p>
                  <ol>{disclosure.deploymentSteps.map((item) => <li key={item}>{item}</li>)}</ol>
                </details>
                <details id="security">
                  <summary>{disclosure.audienceTitle}</summary>
                  <p>{disclosure.audienceBody}</p>
                  <p>{disclosure.architectureBody}</p>
                  <p>{disclosure.affiliation}</p>
                </details>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="axyro-footer">
        <div className="axyro-container axyro-footer-content">
          <span>{disclosure.footerProduct}</span>
          <div>
            <a href="/privacy">{disclosure.nav.privacy}</a>
            <a href="/terms">{disclosure.nav.terms}</a>
            <a href="mailto:support@axyro.tech">support@axyro.tech</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
