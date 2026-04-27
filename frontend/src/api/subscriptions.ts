// ft-027: Subscription CRUD + run-now wired to /api/subscriptions/.

import { getApi } from "./client";

export interface SourceSpec {
  key: string;
  params?: Record<string, unknown>;
}

export interface DeliverySpec {
  channel: string;
  to?: string;
  depth?: string;
  schedule?: string;
  max_items?: number;
}

export interface PerspectiveSpec {
  preset?: string;
  custom?: string;
}

export interface SubscriptionDTO {
  name: string;
  enabled?: boolean;
  interests: string[];
  exclude?: string[];
  sources: SourceSpec[];
  deliveries: DeliverySpec[];
  perspective?: PerspectiveSpec;
}

export async function listSubscriptions(): Promise<SubscriptionDTO[]> {
  try {
    const api = await getApi();
    const r = await api.get<SubscriptionDTO[]>("/subscriptions/");
    return r.data;
  } catch {
    return [];
  }
}

export async function getSubscription(name: string): Promise<SubscriptionDTO> {
  const api = await getApi();
  const r = await api.get<SubscriptionDTO>(
    `/subscriptions/${encodeURIComponent(name)}/`,
  );
  return r.data;
}

export async function createSubscription(
  sub: SubscriptionDTO,
): Promise<SubscriptionDTO> {
  const api = await getApi();
  const r = await api.post<SubscriptionDTO>("/subscriptions/", sub);
  return r.data;
}

export async function updateSubscription(
  originalName: string,
  sub: SubscriptionDTO,
): Promise<SubscriptionDTO> {
  const api = await getApi();
  const r = await api.put<SubscriptionDTO>(
    `/subscriptions/${encodeURIComponent(originalName)}/`,
    sub,
  );
  return r.data;
}

export async function deleteSubscription(name: string): Promise<void> {
  const api = await getApi();
  await api.delete(`/subscriptions/${encodeURIComponent(name)}/`);
}

export interface SubscriptionRunResponse {
  job_id: string;
  status: string;
}

export async function runSubscription(
  name: string,
): Promise<SubscriptionRunResponse> {
  const api = await getApi();
  const r = await api.post<SubscriptionRunResponse>(
    `/subscriptions/${encodeURIComponent(name)}/run/`,
    {},
  );
  return r.data;
}
