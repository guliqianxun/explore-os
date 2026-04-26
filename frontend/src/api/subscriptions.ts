import { getApi } from "./client";

// The subscription HTTP layer is a placeholder until ft-025-style endpoints
// land. The DRF API frozen for ft-024 does not expose subscriptions yet, so
// these helpers degrade gracefully to an empty list when the endpoint is 404.

export interface SubscriptionDTO {
  id: string;
  name: string;
  interests: string[];
  sources: string[];
  delivery: string[];
  schedule: string;
  raw_yaml?: string;
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

export async function saveSubscription(sub: SubscriptionDTO): Promise<void> {
  const api = await getApi();
  await api.post("/subscriptions/", sub);
}

export async function deleteSubscription(id: string): Promise<void> {
  const api = await getApi();
  await api.delete(`/subscriptions/${encodeURIComponent(id)}/`);
}
