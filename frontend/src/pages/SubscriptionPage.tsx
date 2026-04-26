import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  SubscriptionDTO,
  deleteSubscription,
  listSubscriptions,
  saveSubscription,
} from "@/api/subscriptions";

const EMPTY_DRAFT: SubscriptionDTO = {
  id: "",
  name: "",
  interests: [],
  sources: [],
  delivery: [],
  schedule: "",
  raw_yaml: "",
};

export default function SubscriptionPage() {
  const qc = useQueryClient();
  const subsQ = useQuery({ queryKey: ["subscriptions"], queryFn: listSubscriptions });

  const [editing, setEditing] = useState<SubscriptionDTO | null>(null);

  const saveMut = useMutation({
    mutationFn: saveSubscription,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setEditing(null);
    },
  });
  const deleteMut = useMutation({
    mutationFn: deleteSubscription,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b bg-white px-4 py-2">
        <h1 className="text-base font-semibold">Subscriptions</h1>
        <Button size="sm" onClick={() => setEditing({ ...EMPTY_DRAFT })}>
          New
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2 max-w-3xl mx-auto">
          {subsQ.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : subsQ.data && subsQ.data.length > 0 ? (
            subsQ.data.map((sub) => (
              <Card key={sub.id} className="p-3 flex justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-sm truncate">{sub.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    interests: {sub.interests.join(", ") || "—"}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    sources: {sub.sources.join(", ") || "—"} · delivery:{" "}
                    {sub.delivery.join(", ") || "—"} · schedule: {sub.schedule}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => setEditing({ ...sub })}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      if (window.confirm(`Delete subscription "${sub.name}"?`)) {
                        deleteMut.mutate(sub.id);
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </Card>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              No subscriptions yet (or the subscriptions API endpoint is not
              wired in this build — full CRUD lands in a follow-up; for now
              edit <code>subscriptions.yaml</code> directly).
            </p>
          )}
        </div>
      </ScrollArea>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing?.id ? "Edit subscription" : "New subscription"}
            </DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium">Name</label>
                <Input
                  value={editing.name}
                  onChange={(e) =>
                    setEditing({ ...editing, name: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">YAML body</label>
                <Textarea
                  rows={12}
                  className="font-mono text-xs"
                  value={editing.raw_yaml ?? ""}
                  onChange={(e) =>
                    setEditing({ ...editing, raw_yaml: e.target.value })
                  }
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => editing && saveMut.mutate(editing)}
              disabled={saveMut.isPending}
            >
              {saveMut.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
