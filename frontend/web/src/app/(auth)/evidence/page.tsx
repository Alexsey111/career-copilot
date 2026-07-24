"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import EvidenceCard from "@/components/EvidenceCard";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type { EvidenceSnippetItem, EvidenceUsageItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function EvidencePage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [snippets, setSnippets] = useState<EvidenceSnippetItem[]>([]);
  const [insights, setInsights] = useState<any>(null);
  const [usages, setUsages] = useState<EvidenceUsageItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    Promise.allSettled([
      api.getEvidenceSnippets(token).then((r) => r as EvidenceSnippetItem[]),
      api.getEvidenceInsights(token).then((r) => r as any),
      api.getEvidenceUsages(token).then((r) => r as EvidenceUsageItem[]),
    ]).then(([sn, ins, usg]) => {
      if (sn.status === "fulfilled") setSnippets(sn.value ?? []);
      if (ins.status === "fulfilled") setInsights(ins.value);
      if (usg.status === "fulfilled") setUsages(usg.value ?? []);
      setLoading(false);
    });
  }, [token]);

  if (loading) return <Skeleton className="h-32 w-full max-w-4xl" />;

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-2">Источники доказательств</h1>
      <DeterministicDisclaimer text="Каталог подтверждающего опыта. Действия confirm/reject влияют на отбор evidence в документы." />

      {/* Инсайты */}
      {insights && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
          <Card>
            <CardContent className="text-center py-4">
              <div className="text-2xl font-bold text-[color:var(--brand-ink)]">{insights.weak_evidence_count ?? 0}</div>
              <div className="text-xs text-[color:var(--brand-teal-60)] mt-1">Слабых доказательств</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="text-center py-4">
              <div className="text-2xl font-bold text-yellow-600">{insights.missing_metrics_count ?? 0}</div>
              <div className="text-xs text-[color:var(--brand-teal-60)] mt-1">Без метрик</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="text-center py-4">
              <div className="text-2xl font-bold text-[color:var(--brand-teal)]">{snippets.length}</div>
              <div className="text-xs text-[color:var(--brand-teal-60)] mt-1">Всего сниппетов</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Сниппеты */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {snippets.map((s) => (
          <EvidenceCard
            key={s.id}
            token={token ?? ""}
            snippet={s}
            onChanged={(updated) =>
              setSnippets((prev) => prev.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)))
            }
          />
        ))}
        {snippets.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-[color:var(--brand-teal-60)] col-span-2">
              Доказательства не найдены. Загрузите резюме или импортируйте GitHub.
            </CardContent>
          </Card>
        )}
      </div>

      {/* Использования */}
      {usages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Использования</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {usages.map((u, i) => (
                <li key={i} className="text-[color:var(--brand-teal-60)]">
                  {u.target_type ?? ""} {u.target_id ? `· ${u.target_id.slice(0, 8)}…` : ""} {u.note ? `— ${u.note}` : ""}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
