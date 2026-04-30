// User settings → LLM 接口配置（api_base / api_key / models / budget）+ Test ping
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FieldSource,
  LLMSettingsDTO,
  LLMSettingsPatch,
  LLMTestResult,
  getLLMSettings,
  testLLMConnection,
  updateLLMSettings,
} from "@/api/settings";

interface DraftState {
  api_base: string;
  api_key: string;
  api_key_dirty: boolean; // true once user typed in the key field
  model_text: string;
  model_multimodal: string;
  model_vision_classifier: string;
  model_deep: string;
  daily_budget_cny: string; // string for input control
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

const SOURCE_LABEL: Record<FieldSource, string> = {
  user: "user_config.json",
  env: ".env",
  default: "默认",
};

function SourceBadge({ source }: { source: FieldSource }) {
  return (
    <span
      className="ml-2 text-[10px] uppercase tracking-wider px-1.5 py-px rounded-chip"
      style={{
        background: source === "user" ? "var(--accent-soft, #eef2ff)" : "var(--bg-soft)",
        color: source === "user" ? "var(--accent, #4f46e5)" : "var(--fg-muted)",
        border: "1px solid var(--rule)",
      }}
    >
      {SOURCE_LABEL[source]}
    </span>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const settingsQ = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: getLLMSettings,
  });

  const [draft, setDraft] = useState<DraftState>(() => emptyDraft(undefined));
  const [keyVisible, setKeyVisible] = useState(false);
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  // Sync draft from server data on first load / after save
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
      // Only send api_key if user touched the field (so we don't accidentally clear it)
      if (draft.api_key_dirty) patch.api_key = draft.api_key;
      // Budget: send numeric or omit
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

  const sources = settingsQ.data?.sources || {};
  const masked = settingsQ.data?.api_key_masked || "";
  const keySet = settingsQ.data?.api_key_set ?? false;

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg)" }}>
      <header
        className="px-6 py-4 border-b"
        style={{ borderColor: "var(--rule)", background: "var(--bg)" }}
      >
        <h1
          className="text-2xl"
          style={{
            fontFamily: "var(--font-serif)",
            color: "var(--fg)",
            letterSpacing: "-0.01em",
          }}
        >
          Settings
        </h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--fg-muted)" }}>
          LLM 接口配置 — 覆盖 <code>.env</code> 默认；保存后立即对所有 LLM 调用生效
        </p>
      </header>

      <ScrollArea className="flex-1">
        <div className="px-6 py-5 max-w-2xl mx-auto space-y-6">
          {settingsQ.isLoading ? (
            <p className="text-sm" style={{ color: "var(--fg-muted)" }}>
              Loading…
            </p>
          ) : (
            <>
              <Section
                label="API endpoint"
                source={sources.api_base}
                hint="OpenAI-compatible /chat/completions 根路径，如 https://api.openai.com/v1 或阿里云 https://dashscope.aliyuncs.com/compatible-mode/v1"
              >
                <Input
                  value={draft.api_base}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, api_base: e.target.value }))
                  }
                  placeholder="https://api.openai.com/v1"
                />
              </Section>

              <Section
                label="API key"
                source={sources.api_key}
                hint={
                  keySet && !draft.api_key_dirty
                    ? `当前已配置：${masked}（输入新值会替换；保留为空 = 不动）`
                    : "Bearer token（OpenAI: sk-…；DashScope: sk-…）"
                }
              >
                <div className="flex gap-2">
                  <Input
                    type={keyVisible ? "text" : "password"}
                    autoComplete="off"
                    value={draft.api_key}
                    placeholder={keySet ? masked : "sk-…"}
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
                    {keyVisible ? "Hide" : "Show"}
                  </Button>
                  {draft.api_key_dirty ? (
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() =>
                        setDraft((d) => ({ ...d, api_key: "", api_key_dirty: false }))
                      }
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              </Section>

              <Section
                label="Text model"
                source={sources.model_text}
                hint="用于 skim / narrative / rewriter / extract_claims；默认 gpt-4o-mini"
              >
                <Input
                  value={draft.model_text}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, model_text: e.target.value }))
                  }
                  placeholder="gpt-4o-mini"
                />
              </Section>

              <Section
                label="Deep model"
                source={sources.model_deep}
                hint="精读用更强模型；空 = 与 text model 相同"
              >
                <Input
                  value={draft.model_deep}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, model_deep: e.target.value }))
                  }
                  placeholder="(empty = use text model)"
                />
              </Section>

              <Section
                label="Multimodal model"
                source={sources.model_multimodal}
                hint="图文理解（caption / figure 解读）；空 = 跳过多模态步骤"
              >
                <Input
                  value={draft.model_multimodal}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, model_multimodal: e.target.value }))
                  }
                  placeholder="(empty = none)"
                />
              </Section>

              <Section
                label="Vision classifier model"
                source={sources.model_vision_classifier}
                hint="figure 分类（chart / table / equation 区分）；空 = 用 multimodal"
              >
                <Input
                  value={draft.model_vision_classifier}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      model_vision_classifier: e.target.value,
                    }))
                  }
                  placeholder="(empty = use multimodal)"
                />
              </Section>

              <Section
                label="Daily budget (CNY)"
                source={sources.daily_budget_cny}
                hint="每天 LLM 花销上限（人民币元，按 token 估算）；超额报警，0 = 不限"
              >
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={draft.daily_budget_cny}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, daily_budget_cny: e.target.value }))
                  }
                  placeholder="30"
                />
              </Section>

              {/* Action row */}
              <div className="flex items-center gap-3 pt-2">
                <Button
                  onClick={() => saveMut.mutate()}
                  disabled={saveMut.isPending}
                >
                  {saveMut.isPending ? "Saving…" : "Save"}
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
                  {testMut.isPending ? "Testing…" : "Test connection"}
                </Button>
                {saveMut.isSuccess && !saveMut.isPending ? (
                  <span className="text-xs" style={{ color: "var(--fg-muted)" }}>
                    ✓ Saved
                  </span>
                ) : null}
                {saveMut.isError ? (
                  <span className="text-xs text-red-600">
                    Save failed: {(saveMut.error as Error).message}
                  </span>
                ) : null}
              </div>

              {/* Test result */}
              {testResult ? (
                <TestResultCard result={testResult} />
              ) : null}

              {/* Config path footer */}
              <div
                className="text-[11px] pt-6 border-t"
                style={{ color: "var(--fg-muted)", borderColor: "var(--rule)" }}
              >
                配置文件：<code>{settingsQ.data?.config_path}</code>
                <br />
                字段未填 → 回落 <code>.env</code> → 内建默认。安全起见 api_key
                只本机存储；分发安装包不会带走它。
              </div>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function Section({
  label,
  source,
  hint,
  children,
}: {
  label: string;
  source?: FieldSource;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className="flex items-center text-sm mb-1"
        style={{ color: "var(--fg)", fontFamily: "var(--font-sans)" }}
      >
        {label}
        {source ? <SourceBadge source={source} /> : null}
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

function TestResultCard({ result }: { result: LLMTestResult }) {
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
          ✓ Connection OK
        </div>
        <div className="text-xs mt-1" style={{ color: "var(--fg-muted)" }}>
          model <code>{result.model}</code> · {result.latency_ms}ms ·{" "}
          {u.total_tokens ?? "?"} tokens
        </div>
        <div
          className="text-xs mt-1 font-mono"
          style={{ color: "var(--fg-soft)" }}
        >
          → {result.content || "(empty)"}
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
      <div className="font-medium">
        ✗ Test failed ({result.kind === "config" ? "config" : "network / vendor"})
      </div>
      <div className="text-xs mt-1 font-mono">{result.error}</div>
    </div>
  );
}
