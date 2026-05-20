import { getApi } from "./client";
import type {
  ActivityPointDTO,
  ClaimLinkDTO,
  ClaimLinkRelation,
  EventReportPayload,
  GapsDTO,
  ProfileDTO,
  QuestionDTO,
  ThreadDTO,
  ThreadNoteDTO,
  ViewpointStateDTO,
} from "@/types/state";

export async function getProfile(): Promise<ProfileDTO> {
  const api = await getApi();
  const r = await api.get<ProfileDTO>("/state/profile/");
  return r.data;
}

export async function getActivity(
  topic?: string,
  days?: number,
): Promise<ActivityPointDTO[]> {
  const api = await getApi();
  const params: Record<string, string> = {};
  if (topic) params.topic = topic;
  if (days !== undefined) params.days = String(days);
  const r = await api.get<ActivityPointDTO[]>("/state/activity/", { params });
  return r.data;
}

export async function getGaps(): Promise<GapsDTO> {
  const api = await getApi();
  const r = await api.get<GapsDTO>("/state/gaps/");
  return r.data;
}

export async function getViewpointState(
  viewpointId: string,
): Promise<ViewpointStateDTO> {
  const api = await getApi();
  const r = await api.get<ViewpointStateDTO>(
    `/state/viewpoint/${encodeURIComponent(viewpointId)}/`,
  );
  return r.data;
}

export async function postEvent(
  payload: EventReportPayload,
): Promise<{ status: string }> {
  const api = await getApi();
  const r = await api.post<{ status: string }>("/state/events/", payload);
  return r.data;
}

export async function listLinks(
  viewpointId?: string,
): Promise<ClaimLinkDTO[]> {
  const api = await getApi();
  const params: Record<string, string> = {};
  if (viewpointId) params.viewpoint = viewpointId;
  const r = await api.get<ClaimLinkDTO[]>("/state/links/", { params });
  return r.data;
}

export async function createLink(
  src: string,
  dst: string,
  relation: ClaimLinkRelation,
  note?: string,
): Promise<ClaimLinkDTO> {
  const api = await getApi();
  const body: {
    src_viewpoint_id: string;
    dst_viewpoint_id: string;
    relation: ClaimLinkRelation;
    note?: string;
  } = {
    src_viewpoint_id: src,
    dst_viewpoint_id: dst,
    relation,
  };
  if (note !== undefined) body.note = note;
  const r = await api.post<ClaimLinkDTO>("/state/links/", body);
  return r.data;
}

export async function deleteLink(linkId: number): Promise<void> {
  const api = await getApi();
  await api.delete(`/state/links/${linkId}/`);
}

export async function listThreads(): Promise<ThreadDTO[]> {
  const api = await getApi();
  const r = await api.get<ThreadDTO[]>("/state/threads/");
  return r.data;
}

export async function createThread(
  title: string,
  body?: string,
  viewpointIds?: string[],
  paperKeys?: string[],
): Promise<ThreadDTO> {
  const api = await getApi();
  const payload: {
    title: string;
    body?: string;
    viewpoint_ids?: string[];
    paper_keys?: string[];
  } = { title };
  if (body !== undefined) payload.body = body;
  if (viewpointIds !== undefined) payload.viewpoint_ids = viewpointIds;
  if (paperKeys !== undefined) payload.paper_keys = paperKeys;
  const r = await api.post<ThreadDTO>("/state/threads/", payload);
  return r.data;
}

export async function addThreadNote(
  threadId: number,
  body: string,
  viewpointIds?: string[],
): Promise<ThreadNoteDTO> {
  const api = await getApi();
  const payload: { body: string; viewpoint_ids?: string[] } = { body };
  if (viewpointIds !== undefined) payload.viewpoint_ids = viewpointIds;
  const r = await api.post<ThreadNoteDTO>(
    `/state/threads/${threadId}/notes/`,
    payload,
  );
  return r.data;
}

export async function deleteThread(threadId: number): Promise<void> {
  const api = await getApi();
  await api.delete(`/state/threads/${threadId}/`);
}

export async function listQuestions(): Promise<QuestionDTO[]> {
  const api = await getApi();
  const r = await api.get<QuestionDTO[]>("/state/questions/");
  return r.data;
}

export async function createQuestion(
  question: string,
  topicId?: string,
): Promise<QuestionDTO> {
  const api = await getApi();
  const body: { question: string; topic_id?: string } = { question };
  if (topicId !== undefined) body.topic_id = topicId;
  const r = await api.post<QuestionDTO>("/state/questions/", body);
  return r.data;
}
