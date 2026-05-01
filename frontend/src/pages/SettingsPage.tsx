// ft-038: clean Settings — General (language) + LLM + Data directory.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  LLMSettingsDTO,
  LLMSettingsPatch,
  LLMTestResult,
  getLLMSettings,
  testLLMConnection,
  updateLLMSettings,
} from "@/api/settings";
import type { DataDirInfo } from "@/api/client";
import { SUPPORTED_LANGS, currentLang, setLang, type Lang } from "@/i18n";

interface DraftState {
  api_base: string;
  api_key: string;
  api_key_dirty: boolean;
  model_text: string;
  model_multimodal: string;
  model_vision_classifier: string;
  model_deep: string;
  daily_budget_cny: string;
}

function emptyDraft(d: LLMSettingsDTO | undefined): DraftState {
  return {
    api_base: d?.api_base || "",
    api_key: "",
    api_key_dirty: false,
    model_text: d?.model_text || "",
    model_multimodal: d?.model_multimodal || "",
    model_vision_classifier: d?.model_vision_classifier || "",
    model_deep: d?.model_deep || "",
    daily_budget_cny: d?.daily_budget_cny ? String(d.daily_budget_cny) : "",
  };
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const settingsQ = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: getLLMSettings,
  });

  const [draft, setDraft] = useState<DraftState>(() => emptyDraft(undefined));
  const [keyVisible, setKeyVisible] = useState(false);
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  useEffect(() => {
    if (settingsQ.data && !draft.api_key_dirty) {
      setDraft(emptyDraft(settingsQ.data));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsQ.data]);

  const saveMut = useMutation({
    mutationFn: async () => {
      const patch: LLMSettingsPatch = {
        api_base: draft.api_base,
        model_text: draft.model_text,
        model_multimodal: draft.model_multimodal,
        model_vision_classifier: draft.model_vision_classifier,
        model_deep: draft.model_deep,
      };
      if (draft.api_key_dirty) patch.api_key = draft.api_key;
      const b = draft.daily_budget_cny.trim();
      if (b) {
        const n = Number(b);
        if (Number.isFinite(n)) patch.daily_budget_cny = n;
      }
      return updateLLMSettings(patch);
    },
    onSuccess: (data) => {
      qc.setQueryData(["settings", "llm"], data);
      setDraft({ ...emptyDraft(data) });
      setKeyVisible(false);
      setTestResult(null);
    },
  });

  const testMut = useMutation({
    mutationFn: testLLMConnection,
    onSuccess: setTestResult,
  });

  const masked = settingsQ.data?.api_key_masked || "";
  const keySet = settingsQ.data?.api_key_set ?? false;

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg)" }}>
      <header
        className="px-6 py-4 border-b"
        style={{ borderColor: "var(--rule)" }}
      >
        <h1
          className="text-2xl"
          style={{
            fontFamily: "var(--font-serif)",
            color: "var(--fg)",
            letterSpacing: "-0.01em",
          }}
        >
          {t("settings.title")}
        </h1>
      </header>

      <ScrollArea className="flex-1">
        <div className="px-6 py-6 max-w-2xl mx-auto space-y-10">
          {/* General — language */}
          <SectionGroup title={t("settings.general")}>
            <LanguageRow />
          </SectionGroup>

          {/* LLM */}
          <SectionGroup title={t("settings.llm")}>
            {settingsQ.isLoading ? (
              <p className="text-sm" style={{ color: "var(--fg-muted)" }}>
                {t("common.loading")}
              </p>
            ) : (
              <>
                <Field label={t("settings.api_endpoint")}>
                  <Input
                    value={draft.api_base}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, api_base: e.target.value }))
                    }
                    placeholder="https://api.openai.com/v1"
                  />
                </Field>

                <Field
                  label={t("settings.api_key")}
                  hint={
                    keySet && !draft.api_key_dirty
                      ? t("settings.api_key_set", { masked })
                      : undefined
                  }
                >
                  <div className="flex gap-2">
                    <Input
                      type={keyVisible ? "text" : "password"}
                      autoComplete="off"
                      value={draft.api_key}
                      placeholder={
                        keySet ? masked : t("settings.api_key_placeholder")
                      }
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          api_key: e.target.value,
                          api_key_dirty: true,
                        }))
                      }
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setKeyVisible((v) => !v)}
                    >
                      {keyVisible ? t("common.hide") : t("common.show")}
                    </Button>
                  </div>
                </Field>

                <Field label={t("settings.text_model")}>
                  <Input
                    value={draft.model_text}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, model_text: e.target.value }))
                    }
                    placeholder="gpt-4o-mini"
                  />
                </Field>

                <Field
                  label={t("settings.deep_model")}
                  hint={t("settings.deep_model_hint")}
                >
                  <Input
                    value={draft.model_deep}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, model_deep: e.target.value }))
                    }
                  />
                </Field>

                <Field
                  label={t("settings.multimodal_model")}
                  hint={t("settings.multimodal_model_hint")}
                >
                  <Input
                    value={draft.model_multimodal}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        model_multimodal: e.target.value,
                      }))
                    }
                  />
                </Field>

                <Field
                  label={t("settings.vision_model")}
                  hint={t("settings.vision_model_hint")}
                >
                  <Input
                    value={draft.model_vision_classifier}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        model_vision_classifier: e.target.value,
                      }))
                    }
                  />
                </Field>

                <Field
                  label={t("settings.daily_budget")}
                  hint={t("settings.daily_budget_hint")}
                >
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={draft.daily_budget_cny}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        daily_budget_cny: e.target.value,
                      }))
                    }
                    placeholder="30"
                  />
                </Field>

                <div className="flex items-center gap-3 pt-1">
                  <Button
                    onClick={() => saveMut.mutate()}
                    disabled={saveMut.isPending}
                  >
                    {saveMut.isPending
                      ? t("common.saving")
                      : t("common.save")}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setTestResult(null);
                      testMut.mutate();
                    }}
                    disabled={testMut.isPending}
                  >
                    {testMut.isPending
                      ? t("settings.testing")
                      : t("settings.test_connection")}
                  </Button>
                  {saveMut.isSuccess && !saveMut.isPending ? (
                    <span
                      className="text-xs"
                      style={{ color: "var(--fg-muted)" }}
                    >
                      ✓ {t("common.saved")}
                    </span>
                  ) : null}
                </div>

                {testResult ? <TestResultCard result={testResult} /> : null}
              </>
            )}
          </SectionGroup>

          {/* Data directory */}
          <DataDirSection />
        </div>
      </ScrollArea>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Layout primitives
// ─────────────────────────────────────────────────────────────────────────

function SectionGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <h2
        className="text-[11px] uppercase tracking-[0.18em] pb-1 border-b"
        style={{
          color: "var(--fg-muted)",
          borderColor: "var(--rule)",
          fontFamily: "var(--font-mono, ui-monospace)",
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className="block text-sm mb-1"
        style={{ color: "var(--fg)" }}
      >
        {label}
      </label>
      {children}
      {hint ? (
        <p
          className="text-[11px] mt-1"
          style={{ color: "var(--fg-muted)" }}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Language switcher
// ─────────────────────────────────────────────────────────────────────────

function LanguageRow() {
  const { t } = useTranslation();
  const [lang, setLangState] = useState<Lang>(currentLang());
  const handleChange = (next: Lang) => {
    setLangState(next);
    setLang(next);
  };
  return (
    <Field label={t("settings.language")}>
      <div className="flex gap-2">
        {SUPPORTED_LANGS.map((l) => (
          <Button
            key={l}
            type="button"
            variant={l === lang ? "default" : "outline"}
            onClick={() => handleChange(l)}
          >
            {t(`settings.language_${l}`)}
          </Button>
        ))}
      </div>
    </Field>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Test result
// ─────────────────────────────────────────────────────────────────────────

function TestResultCard({ result }: { result: LLMTestResult }) {
  const { t } = useTranslation();
  if (result.ok) {
    const u = result.usage || {};
    return (
      <div
        className="text-sm rounded-md px-4 py-3"
        style={{
          background: "var(--bg-soft)",
          border: "1px solid var(--rule)",
          color: "var(--fg)",
        }}
      >
        <div className="font-medium text-emerald-700">
          ✓ {t("settings.test_ok")}
        </div>
        <div
          className="text-xs mt-1"
          style={{ color: "var(--fg-muted)" }}
        >
          {result.model} · {result.latency_ms}ms ·{" "}
          {u.total_tokens ?? "?"} tokens
        </div>
      </div>
    );
  }
  return (
    <div
      className="text-sm rounded-md px-4 py-3"
      style={{
        background: "#fef2f2",
        border: "1px solid #fecaca",
        color: "#991b1b",
      }}
    >
      <div className="font-medium">✗ {t("settings.test_failed")}</div>
      <div className="text-xs mt-1 font-mono">{result.error}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// ft-037: Data directory
// ─────────────────────────────────────────────────────────────────────────

function DataDirSection() {
  const { t } = useTranslation();
  const bridge =
    typeof window !== "undefined" ? window.explore : undefined;
  const [info, setInfo] = useState<DataDirInfo | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!bridge?.getDataDirInfo) return;
    bridge.getDataDirInfo().then((r) => {
      setInfo(r);
      setDraft(r?.user_override ?? "");
    });
  }, [bridge]);

  if (!bridge?.getDataDirInfo || !info) return null;

  const handlePick = async () => {
    const picked = await bridge.pickDirectory?.();
    if (picked) {
      setDraft(picked);
      setSaved(false);
    }
  };
  const handleSave = async () => {
    await bridge.setDataDirOverride?.(draft.trim() || null);
    setSaved(true);
    const fresh = await bridge.getDataDirInfo!();
    setInfo(fresh);
  };
  const handleReset = async () => {
    setDraft("");
    await bridge.setDataDirOverride?.(null);
    setSaved(true);
    const fresh = await bridge.getDataDirInfo!();
    setInfo(fresh);
  };
  const dirty = (draft.trim() || null) !== (info.user_override ?? null);
  const sourceLabel = t(`settings.data_dir_source.${info.source}`);

  return (
    <SectionGroup title={t("settings.data_dir")}>
      <p className="text-xs" style={{ color: "var(--fg-muted)" }}>
        {t("settings.data_dir_subtitle")}
      </p>

      <Field
        label={t("settings.data_dir_current")}
        hint={`${sourceLabel}${info.portable ? " · portable" : ""}`}
      >
        <Input value={info.effective} readOnly />
      </Field>

      <Field
        label={t("settings.data_dir_override")}
        hint={t("settings.data_dir_override_hint")}
      >
        <div className="flex gap-2">
          <Input
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setSaved(false);
            }}
          />
          <Button type="button" variant="outline" onClick={handlePick}>
            {t("common.browse")}
          </Button>
        </div>
      </Field>

      <div className="flex items-center gap-3 pt-1">
        <Button onClick={handleSave} disabled={!dirty}>
          {t("common.save")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={handleReset}
          disabled={!info.user_override && !draft.trim()}
        >
          {t("common.reset")}
        </Button>
        {saved ? (
          <span className="text-xs" style={{ color: "var(--fg-muted)" }}>
            ✓ {t("settings.data_dir_restart_hint")}
          </span>
        ) : null}
      </div>
    </SectionGroup>
  );
}
