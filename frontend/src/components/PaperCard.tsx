import { Link } from "react-router-dom";
import { FileText, Layers, Image as ImageIcon, MessageSquareWarning } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { PaperListItem } from "@/api/papers";

export function PaperCard({ paper }: { paper: PaperListItem }) {
  return (
    <Link to={`/papers/${encodeURIComponent(paper.arxiv_id)}`} className="block">
      <Card className="p-4 hover:border-blue-400 hover:shadow-md transition">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h3 className="font-mono text-sm font-medium text-slate-900 truncate">
              {paper.arxiv_id}
            </h3>
            <div className="flex flex-wrap gap-3 mt-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Layers className="h-3 w-3" /> {paper.n_sections} sections
              </span>
              <span className="inline-flex items-center gap-1">
                <ImageIcon className="h-3 w-3" /> {paper.n_figures} figures
              </span>
              <span className="inline-flex items-center gap-1">
                <FileText className="h-3 w-3" /> {paper.n_tables} tables
              </span>
              <span className="inline-flex items-center gap-1">
                <MessageSquareWarning className="h-3 w-3" /> {paper.n_claims} claims
              </span>
            </div>
          </div>
          <div className="flex gap-1">
            <Dot active={paper.n_sections > 0} title="extracted" />
            <Dot active={paper.n_claims > 0} title="interpreted" />
            <Dot active={false} title="rendered (TBD)" />
          </div>
        </div>
      </Card>
    </Link>
  );
}

function Dot({ active, title }: { active: boolean; title: string }) {
  return (
    <span
      title={title}
      className={
        "h-2 w-2 rounded-full " + (active ? "bg-emerald-500" : "bg-slate-300")
      }
    />
  );
}
