import { createContext, Fragment, ReactNode, useContext, useMemo, useState } from "react";

import { en } from "./en";
import { ru } from "./ru";

export type Locale = "ru" | "en";

const STORAGE_KEY = "dgu.locale";
const dictionaries: Record<Locale, Record<string, string>> = { ru, en };
let currentLocale: Locale = readInitialLocale();

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(currentLocale);
  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale: (next) => {
        currentLocale = next;
        if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, next);
        if (typeof document !== "undefined") document.documentElement.lang = next;
        setLocaleState(next);
      }
    }),
    [locale]
  );
  return (
    <LocaleContext.Provider value={value}>
      <Fragment key={locale}>{children}</Fragment>
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("LocaleProvider is missing");
  return value;
}

export function t(key: string, params: Record<string, string | number | null | undefined> = {}) {
  const template = dictionaries[currentLocale][key] ?? dictionaries.ru[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_match, name: string) => String(params[name] ?? `{${name}}`));
}

export function formatDate(
  value: string | number | Date | null | undefined,
  options: Intl.DateTimeFormatOptions = { dateStyle: "short", timeStyle: "short" }
) {
  if (value === null || value === undefined || value === "") return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(localeTag(), options).format(date);
}

export function formatNumber(
  value: number,
  options: Intl.NumberFormatOptions = {}
) {
  return new Intl.NumberFormat(localeTag(), options).format(value);
}

export function localeTag() {
  return currentLocale === "ru" ? "ru-RU" : "en-US";
}

export function getLocale() {
  return currentLocale;
}

function readInitialLocale(): Locale {
  if (typeof localStorage === "undefined") return "ru";
  return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "ru";
}
