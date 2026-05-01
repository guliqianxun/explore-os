// ft-038: i18n bootstrap. UI chrome only — LLM-generated content
// (briefs, claims) stays in whatever language the LLM produced it in.
//
// Persistence: localStorage key `explore-os.lang`. Default = browser detect,
// fallback `zh`.
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import zh from "./locales/zh.json";

export const SUPPORTED_LANGS = ["zh", "en"] as const;
export type Lang = (typeof SUPPORTED_LANGS)[number];

const STORAGE_KEY = "explore-os.lang";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: "zh",
    supportedLngs: SUPPORTED_LANGS as unknown as string[],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: STORAGE_KEY,
      caches: ["localStorage"],
    },
  });

export function setLang(lang: Lang) {
  i18n.changeLanguage(lang);
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* storage unavailable */
  }
}

export function currentLang(): Lang {
  const v = i18n.language;
  return (SUPPORTED_LANGS as readonly string[]).includes(v) ? (v as Lang) : "zh";
}

export default i18n;
