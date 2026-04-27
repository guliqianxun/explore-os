import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { cn } from "@/lib/utils";

import PaperListPage from "@/pages/PaperListPage";
import PaperDetailPage from "@/pages/PaperDetailPage";
import SubscriptionPage from "@/pages/SubscriptionPage";
import IngestPage from "@/pages/IngestPage";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
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
    <div className="flex flex-col h-screen">
      <header className="flex items-center gap-4 px-4 py-2 border-b bg-white">
        <Link to="/" className="font-semibold text-slate-900">
          explore-os
        </Link>
        <nav className="flex gap-1">
          <NavItem to="/" label="Papers" />
          <NavItem to="/subscriptions" label="Subscriptions" />
          <NavItem to="/ingest" label="Ingest" />
        </nav>
      </header>
      <main className="flex-1 overflow-hidden bg-slate-50">
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
