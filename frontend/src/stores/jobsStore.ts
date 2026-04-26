import { create } from "zustand";
import type { JobInfo } from "@/api/jobs";

interface JobsState {
  /** job_id → latest JobInfo. */
  jobs: Record<string, JobInfo>;
  upsert: (info: JobInfo) => void;
  remove: (jobId: string) => void;
  clear: () => void;
}

export const useJobsStore = create<JobsState>((set) => ({
  jobs: {},
  upsert: (info) =>
    set((state) => ({ jobs: { ...state.jobs, [info.job_id]: info } })),
  remove: (jobId) =>
    set((state) => {
      const next = { ...state.jobs };
      delete next[jobId];
      return { jobs: next };
    }),
  clear: () => set({ jobs: {} }),
}));
