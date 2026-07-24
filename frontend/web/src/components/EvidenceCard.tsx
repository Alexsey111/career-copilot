"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToastCtx } from "@/contexts/ToastContext";
import type { EvidenceSnippetItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  confirmed: "bg-[color:var(--brand-lime-soft)] text-[color:var(--brand-teal)]",
  needs_confirmation: "bg-yellow-100 text-yellow-800",
  rejected: "bg-[color:var(--brand-ink-10)] text-[color:var(--brand-ink)]",
  unverified: "bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)]",
};

/**
 * Карточка evidence-сниппета с действиями confirm/reject.
 * Переиспользуется в evidence workspace (Этап E) и в interview-prep
 * для supporting evidence (там actions можно скрыть через showActions=false).
 */
export default function EvidenceCard({
  token,
  snippet,
  showActions = true,
  onChanged,
}: {
  token: string;
  snippet: EvidenceSnippetItem;
  showActions?: boolean;
  onChanged?: (updated: EvidenceSnippetItem) => void;
}) {
  const toast = useToastCtx();
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState(snippet.fact_status ?? "unverified");

  const act = async (kind: "confirm" | "reject") => {
    setBusy(true);
    try {
      const res = (kind === "confirm"
        ? await api.confirmEvidence(token, snippet.id)
        : await api.rejectEvidence(token, snippet.id)) as EvidenceSnippetItem;
      setStatus(res.fact_status ?? status);
      toast.success(kind === "confirm" ? "Доказательство подтверждено" : "Доказательство отклонено");
      onChanged?.(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Действие не удалось");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-[color:var(--brand-teal-20)] rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <button onClick={() => setExpanded((v) => !v)} className="text-left flex-1">
          <p className="font-medium text-[color:var(--brand-teal)] text-sm">{snippet.title}</p>
          <p className="text-xs text-[color:var(--brand-teal-40)]">
            {snippet.source_type ?? ""} {snippet.evidence_strength ? `· ${snippet.evidence_strength}` : ""}
          </p>
        </button>
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[status] ?? "bg-[color:var(--brand-teal-5)]"}`}>
          {status}
        </span>
      </div>

      {expanded && snippet.snippet_text && (
        <pre className="text-xs text-[color:var(--brand-teal-60)] whitespace-pre-wrap bg-[color:var(--brand-cream-soft)] p-2 rounded mt-2 max-h-40 overflow-y-auto">
          {snippet.snippet_text}
        </pre>
      )}

      {snippet.skills && snippet.skills.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {snippet.skills.map((s, i) => (
            <span key={i} className="text-xs bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)] px-1.5 py-0.5 rounded">
              {s}
            </span>
          ))}
        </div>
      )}

      {showActions && (
        <div className="flex gap-2 mt-2">
          <button
            onClick={() => act("confirm")}
            disabled={busy}
            className="text-xs px-2 py-1 bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded hover:bg-[#b8e85c] disabled:opacity-50"
          >
            Подтвердить
          </button>
          <button
            onClick={() => act("reject")}
            disabled={busy}
            className="text-xs px-2 py-1 bg-[color:var(--brand-ink)] text-white rounded hover:bg-[#142527] disabled:opacity-50"
          >
            Отклонить
          </button>
        </div>
      )}
    </div>
  );
}