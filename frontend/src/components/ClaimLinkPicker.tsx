import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createLink } from "@/api/state";
import type { ClaimLinkDTO, ClaimLinkRelation } from "@/types/state";

interface ClaimLinkPickerProps {
  open: boolean;
  onClose: () => void;
  srcViewpointId: string;
  srcTitle?: string;
  onCreated?: (link: ClaimLinkDTO) => void;
}

const RELATION_OPTIONS: { value: ClaimLinkRelation; label: string }[] = [
  { value: "agree", label: "agree" },
  { value: "conflict", label: "conflict" },
  { value: "refine", label: "refine" },
];

export default function ClaimLinkPicker({
  open,
  onClose,
  srcViewpointId,
  srcTitle,
  onCreated,
}: ClaimLinkPickerProps) {
  const [dstId, setDstId] = useState("");
  const [relation, setRelation] = useState<ClaimLinkRelation>("agree");
  const [note, setNote] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      createLink(srcViewpointId, dstId.trim(), relation, note || undefined),
    onSuccess: (link) => {
      onCreated?.(link);
      onClose();
      setDstId("");
      setNote("");
      setRelation("agree");
    },
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Claim Link</DialogTitle>
          <DialogDescription
            className="break-all text-xs"
            style={{ color: "var(--fg-muted)" }}
          >
            {srcTitle || srcViewpointId}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label
              className="text-sm mb-1 block"
              style={{ color: "var(--fg-soft)" }}
            >
              Target claim ID
            </label>
            <Input
              value={dstId}
              onChange={(e) => setDstId(e.target.value)}
              placeholder="Paste a claim_id"
            />
          </div>
          <div>
            <label
              className="text-sm mb-1 block"
              style={{ color: "var(--fg-soft)" }}
            >
              Relation
            </label>
            <select
              value={relation}
              onChange={(e) => setRelation(e.target.value as ClaimLinkRelation)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {RELATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              className="text-sm mb-1 block"
              style={{ color: "var(--fg-soft)" }}
            >
              Note
            </label>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note..."
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => createMut.mutate()}
            disabled={!dstId.trim() || createMut.isPending}
          >
            {createMut.isPending ? "Creating..." : "Create Link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
