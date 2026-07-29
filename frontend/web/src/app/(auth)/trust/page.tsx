"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type {
  ReviewSummaryResponse,
  HealthDiagnosticsResponse,
  DocumentListItem,
  InterviewPrepSessionListItem,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export default function TrustPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [health, setHealth] = useState<HealthDiagnosticsResponse | null>(null);
  const [entityType, setEntityType] = useState<"document" | "interview_prep">("document");
  const [entityId, setEntityId] = useState("");
  const [summary, setSummary] = useState<ReviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [sessions, setSessions] = useState<InterviewPrepSessionListItem[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.allSettled([
      api.getHealthDiagnostics(token).then((r) => r as HealthDiagnosticsResponse),
      api.listDocuments(token).then((r) => r as { items: DocumentListItem[] } | DocumentListItem[]),
      api.listInterviewPrepSessions(token).then((r) => r as InterviewPrepSessionListItem[]),
    ]).then(([h, d, s]) => {
      if (h.status === "fulfilled") setHealth(h.value);
      if (d.status === "fulfilled") {
        const value = d.value;
        // Бэкенд отдаёт { items, total }; на случай иной формы — массив.
        const items = Array.isArray(value) ? value : (value?.items ?? []);
        setDocs(items);
      }
      if (s.status === "fulfilled") setSessions(s.value ?? []);
      setLoading(false);
    });
  }, [token]);

  const handleFetch = async () => {
    if (!token || !entityId.trim()) return;
    setFetching(true);
    try {
      const res = (await api.getReviewSummary(token, entityType, entityId.trim())) as ReviewSummaryResponse;
      setSummary(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Сводка недоступна");
      setSummary(null);
    } finally {
      setFetching(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl space-y-4">
        <h1 className="text-2xl font-bold">Панель доверия</h1>
        <Skeleton className="h-32" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">Панель доверия</h1>
        <DeterministicDisclaimer text="Сводка проверки документа или подготовки к интервью без вероятностных оценок." />
      </div>

      {health && (
        <Card>
          <CardHeader>
            <CardTitle>Диагностика</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <Badge variant="secondary">Backend: {health.status ?? "ok"}</Badge>
              <span className="text-[color:var(--brand-teal-60)]">
                Вакансий: {health.counts?.vacancies ?? 0} · Откликов: {health.counts?.applications ?? 0} · Документов: {health.counts?.documents ?? 0}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Сводка проверки</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant={entityType === "document" ? "default" : "outline"}
              size="sm"
              onClick={() => { setEntityType("document"); setEntityId(""); setSummary(null); }}
            >
              Документ
            </Button>
            <Button
              variant={entityType === "interview_prep" ? "default" : "outline"}
              size="sm"
              onClick={() => { setEntityType("interview_prep"); setEntityId(""); setSummary(null); }}
            >
              Подготовка к интервью
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="entity-select">Выберите сущность</Label>
            <Select value={entityId} onValueChange={(v) => setEntityId(v ?? "")}>
              <SelectTrigger id="entity-select" aria-label="Выберите сущность">
                <SelectValue placeholder="— выберите —" />
              </SelectTrigger>
              <SelectContent>
                {entityType === "document"
                  ? docs.map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.document_kind === "resume" ? "Резюме" : d.document_kind === "cover_letter" ? "Сопроводительное" : d.document_kind}
                        {d.version_label ? ` · ${d.version_label}` : ""} · {d.id.slice(0, 8)}…
                        {d.is_active ? " ✓" : ""}
                      </SelectItem>
                    ))
                  : sessions.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        Сессия {s.id.slice(0, 8)}…
                      </SelectItem>
                    ))}
              </SelectContent>
            </Select>
            {entityType === "document" && docs.length === 0 && (
              <p className="text-xs text-[color:var(--brand-teal-60)]">
                Нет документов. Создайте резюме или сопроводительное на странице вакансии.
              </p>
            )}
            {entityType === "interview_prep" && sessions.length === 0 && (
              <p className="text-xs text-[color:var(--brand-teal-60)]">
                Нет сессий подготовки. Запустите подготовку к интервью на странице вакансии.
              </p>
            )}
          </div>

          <Button onClick={handleFetch} disabled={fetching || !entityId}>
            {fetching ? "Загрузка…" : "Получить сводку"}
          </Button>
        </CardContent>
      </Card>

      {summary && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {summary.ready != null && (
                <Badge variant={summary.ready ? "default" : "secondary"}>
                  {summary.ready ? "Готово" : "Требует внимания"}
                </Badge>
              )}
              {summary.risk_level && (
                <span className="text-[color:var(--brand-teal-60)]">Риск: {summary.risk_level}</span>
              )}
              {summary.requires_human_review && (
                <Badge variant="destructive">Требует ручной проверки</Badge>
              )}
            </div>

            {summary.blockers && summary.blockers.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-destructive mb-1">Блокеры</h3>
                <ul className="space-y-1">
                  {summary.blockers.map((b, i) => (
                    <li key={i} className="text-sm text-destructive">
                      • {String((b as Record<string, unknown>).message ?? b)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.warnings && summary.warnings.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Предупреждения</h3>
                <ul className="space-y-1">
                  {summary.warnings.map((w, i) => (
                    <li key={i} className="text-sm text-[color:var(--brand-teal-60)]">
                      • {String((w as Record<string, unknown>).message ?? w)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.claims_requiring_confirmation && summary.claims_requiring_confirmation.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">
                  Утверждения, требующие подтверждения
                </h3>
                <ul className="space-y-1">
                  {summary.claims_requiring_confirmation.map((c, i) => (
                    <li key={i} className="text-sm text-[color:var(--brand-teal-60)]">
                      • {String((c as Record<string, unknown>).title ?? c)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.recommended_actions && summary.recommended_actions.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Рекомендуемые действия</h3>
                <ul className="space-y-1">
                  {summary.recommended_actions.map((a, i) => (
                    <li key={i} className="text-sm text-[color:var(--brand-teal)]">
                      → {String((a as Record<string, unknown>).title ?? (a as Record<string, unknown>).action ?? a)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
