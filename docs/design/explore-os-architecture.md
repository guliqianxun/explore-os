---
title: explore-os 架构图
type: architecture
version: 2.0
created_at: 2026-05-04
---

# explore-os 架构图

---

## 1. 软件框架图

```
                         ┌────────────────────────────┐
                         │     subscription.yaml       │
                         │  interests · sources ·      │
                         │  perspective · delivery     │
                         └────────────┬───────────────┘
                                      │
                         ┌────────────▼───────────────┐
                         │       SOURCE FETCH          │
                         │   arXiv API · HF Papers     │
                         │     → PDF download          │
                         └────────────┬───────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
    ┌─────────▼─────────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
    │    EXTRACT         │   │   INTERPRET     │   │     BRIEF         │
    │  (确定性 · 无LLM)   │   │  (L1+L2 LLM)    │   │  (skim+deep LLM)  │
    │                    │   │                 │   │                   │
    │  Docling → 5 类    │   │  catalog → L1   │   │  skim_interpret   │
    │  material:         │   │  claims 5-15条  │   │  → abstract_zh    │
    │  · Section         │   │  L2  counter-   │   │  → keywords       │
    │  · Figure          │   │  signals 0-8条  │   │                   │
    │  · Table           │   │                 │   │  deep_interpret    │
    │  · Equation        │   │  evidence must  │   │  → method_summary  │
    │  · Citation        │   │  cite material  │   │  → key_innovation  │
    └────────┬───────────┘   └────────┬────────┘   │  → for_you        │
             │                        │            └────────┬──────────┘
             │   extract_* tables     │   interpret_*       │  papers_brief
             │                        │   tables            │  table
             └────────────┬───────────┘                    │
                          │                                │
              ┌───────────▼────────────────────────────────▼───────────┐
              │                                                         │
              │              ┌──────────────────────┐                   │
              │              │   USER ACTIONS       │                   │
              │              │                      │                   │
              │              │  status: new → queue │                   │
              │              │    → reading → kept  │                   │
              │              │                      │                   │
              │              │  tag · comment       │                   │
              │              │  backlink · search   │                   │
              │              └──────────┬───────────┘                   │
              │                         │                               │
              │                         ▼                               │
              │    ┌──────────────────────────────────────────┐        │
              │    │         VIEWPOINT STATE MACHINE          │        │
              │    │                                          │        │
              │    │  unseen ──READ──▶ exposed ──EVIDENCE──▶  │        │
              │    │                               confirmed  │        │
              │    │                                  │       │        │
              │    │                            LINK  │       │        │
              │    │                                  ▼       │        │
              │    │                               linked ──▶│        │
              │    │                           THREAD_WRITE  │        │
              │    │                                  ▼       │        │
              │    │                            internalized │        │
              │    │                                          │        │
              │    │  Memory tables:                          │        │
              │    │  vip_state · vip_event  (per viewpoint)  │        │
              │    │  topic · topic_edge · activity           │        │
              │    └──────────────────┬───────────────────────┘        │
              │                       │                                │
              │                       ▼                                │
              │    ┌──────────────────────────────────────────┐        │
              │    │           DAILY CRUNCH                    │        │
              │    │                                          │        │
              │    │  compute_activity(t)       → A(t)        │        │
              │    │  compute_consolidation(t)  → C(t)        │        │
              │    │  detect_prereq_gaps(t)     → G(t)        │        │
              │    │  detect_decay_gaps(t)      → G(t)        │        │
              │    │                                          │        │
              │    │  write: hermes_activity snapshot         │        │
              │    └──────────────────┬───────────────────────┘        │
              │                       │                                │
              │                       ▼                                │
              │    ┌──────────────────────────────────────────┐        │
              │    │              FEED / API                   │        │
              │    │                                          │        │
              │    │  GET /api/papers/          paper list    │        │
              │    │  GET /api/hermes/profile/  A + C 面板    │        │
              │    │  GET /api/hermes/gaps/     gap 侧栏      │        │
              │    │  GET /api/hermes/activity/ 活跃度折线    │        │
              │    │  POST /api/hermes/events/  前端上报      │        │
              │    │                                          │        │
              │    │  React frontend:                         │        │
              │    │  PaperListPage · PaperDetailPage         │        │
              │    │  ReadingStation · SpeedReadView          │        │
              │    │  IngestPage · SubscriptionPage           │        │
              │    │  SettingsPage · ProfilePage              │        │
              │    └──────────────────────────────────────────┘        │
              │                                                         │
              └─────────────────────────────────────────────────────────┘

     ┌─ 确定性管道 (extract)     ──▶  论文→材料 (零 LLM)
     └─ LLM 管道 (interpret)   ──▶  材料→观点 (结构化 LLM)
     └─ LLM 管道 (brief)       ──▶  论文→摘要 (叙事 LLM)
     └─ 状态机 (viewpoint σ_v)  ──▶  用户×观点→态 (信号驱动)
     └─ Crunch 周期            ──▶  态→A,C,G (确定性计算)
```

---

## 2. 两层设计架构图

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                     MEMORY LAYER (记忆层)                        │
  │                                                                  │
  │  "Store minimal facts. All derived values computed on demand."   │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                      RAW MATERIALS                          │ │
  │  │                                                              │ │
  │  │  papers_paper          Paper 实体  (key, title, doi, kw)     │ │
  │  │  extract_sections      章节       (material_id, raw_text)    │ │
  │  │  extract_figures       图表       (material_id, caption)     │ │
  │  │  extract_tables        表格       (material_id, md)          │ │
  │  │  extract_equations     公式       (material_id, latex)       │ │
  │  │  extract_citations     引用       (material_id, bibkey)      │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                     INTERPRETED CLAIMS                      │ │
  │  │                                                              │ │
  │  │  interpret_claims           观点 (claim_id, text, type)      │ │
  │  │  interpret_claim_evidence   证据 (claim ↔ material_id)       │ │
  │  │  interpret_counter_signals  反向信号 (signal_id, text)       │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                      USER STATE                             │ │
  │  │                                                              │ │
  │  │  papers_user_status     paper 阅读状态 (new→kept)            │ │
  │  │  papers_user_comment    用户评论 (append-only)               │ │
  │  │  papers_user_tag        用户标签 (paper ↔ tag)               │ │
  │  │  papers_user_backlink   论文关联 (paper ↔ paper)             │ │
  │  │  papers_brief           解读缓存 (abstract_zh, for_you)      │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                  VIEWPOINT STATE (NEW)                      │ │
  │  │                                                              │ │
  │  │  vip_state        (user, viewpoint_id) → σ_v                │ │
  │  │                    状态: unseen|exposed|confirmed|           │ │
  │  │                          linked|internalized                │ │
  │  │  vip_event         from→to + trigger + τ (append-only)      │ │
  │  │  topic             主题节点 (topic_id, name, aliases)        │ │
  │  │  topic_edge        主题关系 (prereq|sub|app|rel)             │ │
  │  │  activity          每日快照 (A, C per topic)                 │ │
  │  │  claim_link        观点交联 (v_a ↔ v_b: agree|conflict|refine)│ │
  │  │  thread            用户线程 (title, body, viewpoint_ids)     │ │
  │  │  thread_note       线程笔记 (append-only)                    │ │
  │  │  open_question      未决问题 (question, last_hit_at)          │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  └─────────────────────────────────────────────────────────────────┘
                                    │
                   reads / writes   │  signals emit events
                                    │
  ┌─────────────────────────────────▼───────────────────────────────┐
  │                  ORCHESTRATION LAYER (编排层)                     │
  │                                                                  │
  │  "Every user action is an edge. Every crunch is a batch re-eval." │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                     SIGNAL BUS                              │ │
  │  │                                                              │ │
  │  │  UserPaperStatus.save  ──▶  ∀v∈Δ(p): unseen → exposed       │ │
  │  │  ClaimLink.create      ──▶  confirmed → linked              │ │
  │  │  ClaimLink.delete      ──▶  linked → confirmed              │ │
  │  │  POST /api/events/     ──▶  exposed → confirmed             │ │
  │  │  ThreadNote.create     ──▶  confirmed|linked → internalized │ │
  │  │                                                              │ │
  │  │  Side effect: mark_topic_dirty(t) for each affected topic   │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                     DAILY CRUNCH                             │ │
  │  │                     (APScheduler 03:00)                      │ │
  │  │                                                              │ │
  │  │  for each dirty topic t:                                     │ │
  │  │    A[t] = Σ w(σ_v) · exp(-Δτ / 14)  /  max                 │ │
  │  │    C[t] = |confirmed+| / (|exposed+| + 1)                   │ │
  │  │                                                              │ │
  │  │  for each t where A[t] > 0.3:                                │ │
  │  │    G[t] = prereq_gaps(t, C)                                  │ │
  │  │    G[t] += decay_gaps(t, C)                                  │ │
  │  │                                                              │ │
  │  │  write snapshot → hermes_activity                            │ │
  │  │  clear dirty_topics                                          │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                     API LAYER                                │ │
  │  │                                                              │ │
  │  │  GET  /hermes/profile/   ── topic list + A/C + vp stats     │ │
  │  │  GET  /hermes/activity/  ── time series A(τ) per topic      │ │
  │  │  GET  /hermes/gaps/      ── prereq gaps + decay gaps        │ │
  │  │  GET  /hermes/viewpoint/ ── σ_v state + event history       │ │
  │  │  POST /hermes/events/    ── frontend reports VIEW_EVIDENCE  │ │
  │  │  GET  /hermes/links/     ── claim-level cross-links         │ │
  │  │  GET  /hermes/threads/   ── user threads + notes            │ │
  │  │  GET  /hermes/questions/ ── open questions                  │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                              │                                    │
  │                              ▼                                    │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │                     FRONTEND                                 │ │
  │  │                                                              │ │
  │  │  brief feed: rank += α · A[topic]                            │ │
  │  │  gap panel:  "补 X 基础 / 复习 Y / 经典未读 Z"               │ │
  │  │  topic cloud: top-5 by A                                     │ │
  │  │  profile page: Γ_A(t)折线 + Γ_C(t)堆叠                       │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  └─────────────────────────────────────────────────────────────────┘


    ┌── Memory Layer (记忆层)
    │   Stores minimal facts.
    │   Viewpoint state is the atomic truth.
    │   All derived values (A, C, G) are computed on demand.
    │
    └── Orchestration Layer (编排层)
        Reacts to signals (edges in the event graph).
        Runs daily crunch (batch re-evaluation of A, C, G).
        Serves computed state through API.
        Never auto-generates threads, links, or answers.
```

---

## 数据流：一篇论文的完整生命周期

```
  τ=0  paper p arrives
       │
       ├── EXTRACT  (Docling → 5 materials → extract_*)
       ├── INTERPRET (L1 claims → interpret_claims)
       ├── BRIEF    (skim+deep → papers_brief)
       │
       └── INIT     (INSERT vip_state: unseen for all v∈Δ(p))

  τ=1  user clicks "read"
       │
       └── SIGNAL   (UserPaperStatus.save → unseen→exposed ∀v∈p)
                     dirty{topics_of(p)}

  τ=2  user expands claim card for v₃
       │
       └── API      (POST /hermes/events/ VIEW_EVIDENCE v₃ → exposed→confirmed)

  τ=3  user creates link v₃ conflicts with v₇
       │
       └── SIGNAL   (ClaimLink.create → confirmed→linked for both v₃, v₇)

  τ=4  daily crunch (03:00)
       │
       ├── compute A[t] for dirty topics
       ├── compute C[t]
       ├── detect gaps G[t]
       ├── write activity snapshot
       └── clear dirty

  τ=5  user opens brief feed
       │
       ├── papers where A[topic] > 0.5 → rank +30%
       ├── gap panel: "补 X 基础 / 复习 Y"
       └── topic cloud: top-5 active
```
