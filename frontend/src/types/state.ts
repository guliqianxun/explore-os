export interface TopicStateDTO {
  topic_id: string;
  name: string;
  activity: number;
  consolidation: number;
}

export interface ProfileDTO {
  user_id: number;
  topics: TopicStateDTO[];
  viewpoints: {
    total: number;
    confirmed: number;
    linked: number;
  };
  last_crunch_at: string | null;
}

export interface ActivityPointDTO {
  date: string;
  topic_id: string;
  activity: number;
  consolidation: number;
}

export interface PrereqGapDTO {
  topic_id: string;
  prerequisite_id: string;
  prerequisite_name: string;
  prerequisite_consolidation: number;
}

export interface DecayGapDTO {
  topic_id: string;
  days_since_last: number;
}

export interface GapsDTO {
  prereq: PrereqGapDTO[];
  decay: DecayGapDTO[];
  canonical: unknown[];
}

export type ViewpointState = "unseen" | "exposed" | "confirmed" | "linked" | "internalized";

export interface ViewpointStateDTO {
  viewpoint_id: string;
  state: ViewpointState;
  exposed_at: string | null;
  last_event_at: string | null;
  link_count: number;
  events: Array<{
    from_state: string;
    to_state: string;
    trigger: string;
    created_at: string;
  }>;
}

export type EventTrigger = "VIEW_EVIDENCE" | "THREAD_WRITE";

export interface EventReportPayload {
  viewpoint_id: string;
  trigger: EventTrigger;
  payload?: Record<string, unknown>;
}

export type ClaimLinkRelation = "agree" | "conflict" | "refine";

export interface ClaimLinkDTO {
  id: number;
  src_viewpoint_id: string;
  dst_viewpoint_id: string;
  relation: ClaimLinkRelation;
  note: string;
  created_at: string;
}

export interface ThreadNoteDTO {
  id: number;
  body: string;
  created_at: string;
}

export interface ThreadDTO {
  id: number;
  title: string;
  body: string;
  viewpoint_ids: string[];
  paper_keys: string[];
  notes: ThreadNoteDTO[];
  created_at: string;
  updated_at: string;
}

export interface QuestionDTO {
  id: number;
  question: string;
  topic_id: string;
  last_hit_at: string | null;
  created_at: string;
}
