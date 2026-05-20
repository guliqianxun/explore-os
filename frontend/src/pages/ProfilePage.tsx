import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  useMutation,
} from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import TopicBar from "@/components/TopicBar";
import GapPanel from "@/components/GapPanel";
import ActivityChart from "@/components/ActivityChart";
import ThreadCard from "@/components/ThreadCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { QuestionDTO } from "@/types/state";
import {
  getProfile,
  getGaps,
  getActivity,
  listThreads,
  listQuestions,
  createQuestion,
} from "@/api/state";

export default function ProfilePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const profileQ = useQuery({
    queryKey: ["profile"],
    queryFn: getProfile,
  });

  const gapsQ = useQuery({
    queryKey: ["gaps"],
    queryFn: getGaps,
  });

  const activityQ = useQuery({
    queryKey: ["activity"],
    queryFn: () => getActivity(),
  });

  const threadsQ = useQuery({
    queryKey: ["threads"],
    queryFn: listThreads,
  });

  const questionsQ = useQuery({
    queryKey: ["questions"],
    queryFn: listQuestions,
  });

  const sortedTopics = useMemo(() => {
    const t = profileQ.data?.topics ?? [];
    return [...t].sort((a, b) => b.activity - a.activity);
  }, [profileQ.data]);

  const [newQuestion, setNewQuestion] = useState("");

  const createMut = useMutation({
    mutationFn: (text: string) => createQuestion(text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["questions"] });
      setNewQuestion("");
    },
  });

  const handleSubmitQuestion = () => {
    const trimmed = newQuestion.trim();
    if (!trimmed || createMut.isPending) return;
    createMut.mutate(trimmed);
  };

  return (
    <div className="h-full overflow-y-auto" style={{ background: "var(--bg)" }}>
      <div className="max-w-[920px] mx-auto px-8 md:px-12 py-12">
        <header
          className="flex items-end justify-between border-b-2 pb-4 mb-8"
          style={{ borderColor: "var(--rule)" }}
        >
          <div>
            <div
              className="font-mono text-[10px] tracking-[0.2em] uppercase mb-2"
              style={{ color: "var(--fg-muted)" }}
            >
              explore-os
            </div>
            <h1
              className="font-serif text-4xl md:text-5xl font-semibold leading-none"
              style={{ color: "var(--fg)" }}
            >
              {t("profile.title")}
            </h1>
          </div>
        </header>

        {/* Active Topics */}
        <Section heading={t("profile.active_topics")}>
          {profileQ.isLoading ? (
            <Loading />
          ) : profileQ.error ? (
            <ErrorMsg error={profileQ.error} />
          ) : sortedTopics.length === 0 ? (
            <Empty text={t("profile.no_topics")} />
          ) : (
            sortedTopics.map((topic) => (
              <TopicBar key={topic.name} topic={topic} />
            ))
          )}
        </Section>

        {/* Knowledge Gaps */}
        <Section heading={t("profile.knowledge_gaps")}>
          {gapsQ.isLoading ? (
            <Loading />
          ) : gapsQ.error ? (
            <ErrorMsg error={gapsQ.error} />
          ) : gapsQ.data ? (
            <GapPanel gaps={gapsQ.data} />
          ) : null}
        </Section>

        {/* Activity Timeline */}
        <Section heading={t("profile.activity_timeline")}>
          {activityQ.isLoading ? (
            <Loading />
          ) : activityQ.error ? (
            <ErrorMsg error={activityQ.error} />
          ) : activityQ.data ? (
            <ActivityChart data={activityQ.data} />
          ) : null}
        </Section>

        {/* Threads */}
        <Section heading={t("profile.threads")}>
          <div className="mb-2">
            <Button size="sm" variant="outline">
              {t("profile.new_thread")}
            </Button>
          </div>
          {threadsQ.isLoading ? (
            <Loading />
          ) : threadsQ.error ? (
            <ErrorMsg error={threadsQ.error} />
          ) : threadsQ.data && threadsQ.data.length > 0 ? (
            threadsQ.data.map((th) => (
              <ThreadCard key={th.id} thread={th} />
            ))
          ) : (
            <Empty text={t("profile.no_threads")} />
          )}
        </Section>

        {/* Open Questions */}
        <Section heading={t("profile.open_questions")}>
          {questionsQ.isLoading ? (
            <Loading />
          ) : questionsQ.error ? (
            <ErrorMsg error={questionsQ.error} />
          ) : (
            <>
              {questionsQ.data && questionsQ.data.length > 0 ? (
                <div className="space-y-1.5 mb-4">
                  {questionsQ.data.map((q) => (
                    <QuestionItem key={q.id} question={q} />
                  ))}
                </div>
              ) : (
                <Empty text={t("profile.no_questions")} />
              )}
              <div className="flex gap-2 mt-3">
                <Input
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSubmitQuestion();
                  }}
                  placeholder={t("profile.question_placeholder")}
                  disabled={createMut.isPending}
                />
                <Button
                  onClick={handleSubmitQuestion}
                  disabled={createMut.isPending || !newQuestion.trim()}
                >
                  {createMut.isPending
                    ? t("common.saving")
                    : t("profile.ask")}
                </Button>
              </div>
            </>
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-10">
      <h2
        className="font-mono text-[11px] uppercase tracking-[0.18em] pb-2 mb-4 border-b"
        style={{
          color: "var(--fg-muted)",
          borderColor: "var(--rule)",
        }}
      >
        {heading}
      </h2>
      {children}
    </section>
  );
}

function Loading() {
  return (
    <p className="font-serif text-sm" style={{ color: "var(--fg-muted)" }}>
      Loading...
    </p>
  );
}

function ErrorMsg({ error }: { error: unknown }) {
  return (
    <p className="font-serif text-sm" style={{ color: "var(--counter-fg)" }}>
      {(error as Error).message}
    </p>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <p
      className="font-serif text-sm italic py-3"
      style={{ color: "var(--fg-muted)" }}
    >
      {text}
    </p>
  );
}

function QuestionItem({ question }: { question: QuestionDTO }) {
  const created = new Date(question.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div
      className="flex items-start justify-between gap-3 px-3 py-2.5 rounded-card"
      style={{
        background: "var(--bg)",
        border: "1px solid var(--rule)",
      }}
    >
      <span
        className="font-serif text-sm flex-1 min-w-0"
        style={{ color: "var(--fg)" }}
      >
        {question.question}
      </span>
      <span
        className="font-mono text-[10px] shrink-0 mt-0.5"
        style={{ color: "var(--fg-muted)" }}
      >
        {created}
      </span>
    </div>
  );
}
