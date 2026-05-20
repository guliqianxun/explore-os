import { useEffect, type CSSProperties } from "react";
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

import PaperListPage from "@/pages/PaperListPage";
import PaperDetailPage from "@/pages/PaperDetailPage";
import SubscriptionPage from "@/pages/SubscriptionPage";
import IngestPage from "@/pages/IngestPage";
import SettingsPage from "@/pages/SettingsPage";
import ProfilePage from "@/pages/ProfilePage";
import ThreadPage from "@/pages/ThreadPage";
import { listPapers } from "@/api/papers";
import { onNotificationClick } from "@/lib/notify";
import { useJobPolling } from "@/hooks/useJobPolling";

// Drag region for the frameless Electron window. The whole header is
// draggable; nav links/buttons opt out via `noDrag`.
// `WebkitAppRegion` is Electron-only and not part of the standard CSSProperties.
const drag = { WebkitAppRegion: "drag" } as unknown as CSSProperties;
const noDrag = { WebkitAppRegion: "no-drag" } as unknown as CSSProperties;

function NavItem({
  to,
  label,
  badge,
}: {
  to: string;
  label: string;
  badge?: number;
}) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      style={noDrag}
      className={({ isActive }) =>
        cn(
          "px-3 py-1.5 rounded text-sm transition inline-flex items-center gap-1.5",
          isActive
            ? "bg-slate-900 text-white"
            : "text-slate-700 hover:bg-slate-200",
        )
      }
    >
      {label}
      {badge && badge > 0 ? (
        <span
          className={cn(
            "inline-flex items-center justify-center min-w-[18px] h-[18px]",
            "px-1.5 rounded-full text-[10px] font-mono leading-none",
            "bg-[var(--accent,#c14a3b)] text-white",
          )}
        >
          {badge >= 100 ? "99+" : badge}
        </span>
      ) : null}
    </NavLink>
  );
}

// ft-031: 未决数 badge — count = status=new papers，60s 缓存。
// useJobPolling 在 run-sub:* 完成时 invalidateQueries(["papers", "undecided-count"])
// 让 badge 即时刷新。
function useUndecidedCount(): number {
  const q = useQuery({
    queryKey: ["papers", "undecided-count"],
    queryFn: () => listPapers({ status: "new" }).then((r) => r.length),
    staleTime: 60_000,
  });
  return q.data ?? 0;
}

export default function App() {
  const undecided = useUndecidedCount();
  const navigate = useNavigate();
  const { t } = useTranslation();
  // ft-031: 提到 App 顶层 — 离开 SubscriptionPage 时也要继续轮询，否则
  // run-sub:* 完成的桌面通知只能在 Subscriptions 页弹。
  useJobPolling(2000);

  // ft-031: 通知点击（Electron 主进程通过 IPC 回投 jobId）→ 跳未决区。
  useEffect(() => {
    return onNotificationClick(() => {
      navigate("/?status=new");
    });
  }, [navigate]);

  return (
    <div className="flex flex-col h-screen bg-[var(--bg)]">
      <header
        // h-10 (40px) matches main.ts titleBarOverlay.height so the
        // OS-rendered window controls sit flush with the header row.
        // The header is the OS drag region; interactive children opt out.
        style={drag}
        className="flex items-center gap-4 px-4 h-10 border-b border-slate-200 bg-white shrink-0"
      >
        <Link
          to="/"
          style={noDrag}
          className="font-semibold text-slate-900"
        >
          explore-os
        </Link>
        <nav className="flex gap-1">
          <NavItem to="/" label={t("nav.papers")} badge={undecided} />
          <NavItem to="/subscriptions" label={t("nav.subscriptions")} />
          <NavItem to="/ingest" label={t("nav.ingest")} />
          <NavItem to="/profile" label={t("nav.profile")} />
          <NavItem to="/settings" label={t("nav.settings")} />
        </nav>
      </header>
      <main className="flex-1 overflow-hidden bg-[var(--bg)]">
        <Routes>
          <Route path="/" element={<PaperListPage />} />
          <Route path="/papers/:arxivId" element={<PaperDetailPage />} />
          <Route path="/subscriptions" element={<SubscriptionPage />} />
          <Route path="/ingest" element={<IngestPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/threads/:id" element={<ThreadPage />} />
          <Route path="/threads/new" element={<ThreadPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          {/* ft-027: keep old /run permalinks working. */}
          <Route path="/run" element={<Navigate to="/ingest" replace />} />
        </Routes>
      </main>
    </div>
  );
}
