// User settings — LLM 接口配置（覆盖 .env / settings.py 默认）

import { getApi } from "./client";

export type FieldSource = "user" | "env" | "default";

export interface LLMSettingsDTO {
  api_base: string;
  api_key_masked: string;
  api_key_set: boolean;
  model_text: string;
  model_multimodal: string;
  model_vision_classifier: string;
  model_deep: string;
  daily_budget_cny: number;
  sources: Record<string, FieldSource>;
  config_path: string;
}

/** 部分更新；undefined = 不动；空字符串 = 清空（回落 env / default）。 */
export interface LLMSettingsPatch {
  api_base?: string;
  api_key?: string;
  model_text?: string;
  model_multimodal?: string;
  model_vision_classifier?: string;
  model_deep?: string;
  daily_budget_cny?: number;
}

export interface LLMTestOk {
  ok: true;
  model: string;
  content: string;
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  latency_ms: number;
}

export interface LLMTestErr {
  ok: false;
  error: string;
  kind: "config" | "network";
}

export type LLMTestResult = LLMTestOk | LLMTestErr;

export async function getLLMSettings(): Promise<LLMSettingsDTO> {
  const api = await getApi();
  const r = await api.get<LLMSettingsDTO>("/settings/llm/");
  return r.data;
}

export async function updateLLMSettings(
  patch: LLMSettingsPatch,
): Promise<LLMSettingsDTO> {
  const api = await getApi();
  const r = await api.put<LLMSettingsDTO>("/settings/llm/", patch);
  return r.data;
}

export async function testLLMConnection(): Promise<LLMTestResult> {
  const api = await getApi();
  try {
    const r = await api.post<LLMTestOk>("/settings/llm/test/");
    return r.data;
  } catch (e: unknown) {
    // axios error → unwrap response body if available
    const ax = e as { response?: { data?: LLMTestErr } };
    if (ax.response?.data) return ax.response.data;
    return { ok: false, error: String(e), kind: "network" };
  }
}
