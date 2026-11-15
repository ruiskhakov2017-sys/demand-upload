import { useEffect, useState } from "react";
import ArrowForward from "@mui/icons-material/ArrowForward";
import ArrowOutward from "@mui/icons-material/ArrowOutward";
import { useLocale } from "../i18n";
import { ENTERPRISE_COPY, DEMO_REQUEST_URL } from "../i18n/enterpriseLanding";
import { PUBLIC_COPY } from "../i18n/publicSite";
import { EnterpriseReport } from "./EnterpriseReport";
import { HeroAccountPanel } from "./HeroAccountPanel";
import "./EnterpriseLanding.css";

const screenUrls = ["/product/control-center-desktop.png", "/product/creation-paused-desktop.png"];
const sectionIds = ["report", "campaigns", "access"];

function Brand() {
  return <a className="ax3-brand" href="/" aria-label="Axyro Analytics">
    <span className="ax3-mark" aria-hidden="true"><i /><i /></span>
    <span>Axyro <span className="ax3-brand-secondary">Analytics</span></span>
  </a>;
}

export function PublicSitePage() {
  const { locale, setLocale } = useLocale();
  const copy = ENTERPRISE_COPY[locale];
  const legal = PUBLIC_COPY[locale];
  const [activeScreen, setActiveScreen] = useState(0);
  const screen = copy.screens[activeScreen];
  const nextLocale = locale === "ru" ? "en" : "ru";

  useEffect(() => { document.title = copy.title; }, [copy.title]);

  return <div className="ax3">
    <header className="ax3-header">
      <div className="ax3-wrap ax3-top">
        <Brand />
        <nav aria-label={copy.navigation}>
          {sectionIds.map((id, index) => <a key={id} href={`#${id}`}>{copy.nav[index]}</a>)}
        </nav>
        <div className="ax3-tools">
          <button type="button" aria-label={copy.lang} onClick={() => setLocale(nextLocale)}>{nextLocale.toUpperCase()}</button>
          <a href="/login">{copy.login}<ArrowOutward /></a>
        </div>
      </div>
    </header>
    <main>
      <section className="ax3-hero" aria-labelledby="ax3-hero-title">
        <div className="ax3-wrap ax3-hero-inner">
          <div className="ax3-intro">
            <h1 id="ax3-hero-title">{copy.hero}</h1>
            <p className="ax3-lead">{copy.lead}</p>
            <div className="ax3-actions">
              <a className="ax3-report-link" href="#report">{copy.see}<ArrowForward /></a>
              <a className="ax3-button" href={DEMO_REQUEST_URL}>{copy.demo}<ArrowOutward /></a>
            </div>
          </div>
          <HeroAccountPanel locale={locale} />
        </div>
      </section>

      <EnterpriseReport locale={locale} />

      <section id="campaigns" className="ax3-work ax3-block" aria-labelledby="ax3-work-title">
        <div className="ax3-wrap">
          <p className="ax3-label">{copy.workflow}</p>
          <h2 id="ax3-work-title">{copy.workflowTitle}</h2>
          <div className="ax3-work-layout">
            <div className="ax3-work-controls">
              <div className="ax3-selector" role="group" aria-label={copy.screenLabel}>
                {copy.screens.map((item, index) => <button key={index} type="button" aria-pressed={activeScreen === index} onClick={() => setActiveScreen(index)}>{item.label}<ArrowForward /></button>)}
              </div>
              <div className="ax3-work-description" aria-live="polite"><h3>{screen.title}</h3><p>{screen.body}</p></div>
            </div>
            <figure className="ax3-capture">
              <a href={screenUrls[activeScreen]} target="_blank" rel="noreferrer" aria-label={`${copy.enlarge} · ${screen.label}`}>
                <img src={screenUrls[activeScreen]} alt={screen.alt} loading="lazy" />
                <span><ArrowOutward /></span>
              </a>
              <figcaption><strong>{screen.caption}</strong><span>{copy.sample}</span></figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section id="access" className="ax3-access ax3-block" aria-labelledby="ax3-access-title">
        <div className="ax3-wrap ax3-access-inner">
          <h2 id="ax3-access-title">{copy.accessTitle}</h2>
          <div className="ax3-questions">
            <details><summary>{copy.permissions}</summary><p>{legal.apiBody}</p><ul>{legal.readItems.map(item => <li key={item}>{item}</li>)}</ul></details>
            <details><summary>{copy.changes}</summary><ul>{legal.writeItems.map(item => <li key={item}>{item}</li>)}</ul><p>{legal.productionNotice}</p><ol>{legal.deploymentSteps.map(item => <li key={item}>{item}</li>)}</ol></details>
            <details><summary>{copy.users}</summary><p>{legal.audienceBody}</p><p>{legal.architectureBody}</p><p>{legal.affiliation}</p></details>
          </div>
        </div>
      </section>
      <section className="ax3-contact" aria-labelledby="ax3-contact-title">
        <div className="ax3-wrap ax3-contact-inner">
          <div><h2 id="ax3-contact-title">{copy.contactTitle}</h2><p>{copy.contact}</p></div>
          <a className="ax3-button" href={DEMO_REQUEST_URL}>{copy.demo}<ArrowOutward /></a>
        </div>
      </section>
    </main>
    <footer className="ax3-footer">
      <div className="ax3-wrap ax3-foot-inner">
        <Brand /><nav aria-label={copy.footer}><a href="/privacy">{legal.nav.privacy}</a><a href="/terms">{legal.nav.terms}</a><a href="mailto:support@axyro.tech">support@axyro.tech</a></nav>
      </div>
    </footer>
  </div>;
}
