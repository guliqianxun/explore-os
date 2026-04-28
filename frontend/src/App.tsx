import type { CSSProperties } from "react";
import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { cn } from "@/lib/utils";

import PaperListPage from "@/pages/PaperListPage";
import PaperDetailPage from "@/pages/PaperDetailPage";
import SubscriptionPage from "@/pages/SubscriptionPage";
import IngestPage from "@/pages/IngestPage";

// Drag region for the frameless Electron window. The whole header is
// draggable; nav links/buttons opt out via `noDrag`.
// `WebkitAppRegion` is Electron-only and not part of the standard CSSProperties.
const drag = { WebkitAppRegion: "drag" } as unknown as CSSProperties;
const noDrag = { WebkitAppRegion: "no-drag" } as unknown as CSSProperties;

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      style={noDrag}
      className={({ isActive }) =>
        cn(
          "px-3 py-1.5 rounded text-sm transition",
          isActive
            ? "bg-slate-900 text-white"
            : "text-slate-700 hover:bg-slate-200",
        )
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
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
          <NavItem to="/" label="Papers" />
          <NavItem to="/subscriptions" label="Subscriptions" />
          <NavItem to="/ingest" label="Ingest" />
        </nav>
      </header>
      <main className="flex-1 overflow-hidden bg-[var(--bg)]">
        <Routes>
          <Route path="/" element={<PaperListPage />} />
          <Route path="/papers/:arxivId" element={<PaperDetailPage />} />
          <Route path="/subscriptions" element={<SubscriptionPage />} />
          <Route path="/ingest" element={<IngestPage />} />
          {/* ft-027: keep old /run permalinks working. */}
          <Route path="/run" element={<Navigate to="/ingest" replace />} />
        </Routes>
      </main>
    </div>
  );
}
