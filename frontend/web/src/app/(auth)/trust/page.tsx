"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type {
  ReviewSummaryResponse,
  HealthDiagnosticsResponse,
  ActiveDocumentResponse,
  InterviewPrepSessionListItem,
} from "@/lib/types";

export default function TrustPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [health, setHealth] = useState<HealthDiagnosticsResponse | null>(null);
  const [entityType, setEntityType] = useState<"document" | "interview_prep">("document");
  const [entityId, setEntityId] = useState("");
  const [summary, setSummary] = useState<ReviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [docs, setDocs] = useState<ActiveDocumentResponse[]>([]);
  const [sessions, setSessions] = useState<InterviewPrepSessionListItem[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.allSettled([
      api.getHealthDiagnostics(token).then((r) => r as HealthDiagnosticsResponse),
      api.getActiveDocument(token, "resume").then((r) => r as ActiveDocumentResponse),
      api.getActiveDocument(token, "cover_letter").then((r) => r as ActiveDocumentResponse),
      api.listInterviewPrepSessions(token).then((r) => r as InterviewPrepSessionListItem[]),
    ]).then(([h, d1, d2, s]) => {
      if (h.status === "fulfilled") setHealth(h.value);
      const collected: ActiveDocumentResponse[] = [];
      if (d1.status === "fulfilled" && d1.value?.id) collected.push(d1.value);
      if (d2.status === "fulfilled" && d2.value?.id) collected.push(d2.value);
      setDocs(collected);
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

  if (loading) return <div className="text-gray-500">Загрузка…</div>;

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-2">Панель доверия</h1>
      <DeterministicDisclaimer text="Сводка проверки документа или подготовки к интервью без вероятностных оценок." />

      {health && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold mb-3">Диагностика</h2>
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="px-3 py-1 rounded-full bg-green-100 text-green-800">
              Backend: {health.status ?? "ok"}
            </span>
            <span className="text-gray-600">
              Вакансий: {health.counts?.vacancies ?? 0} · Откликов: {health.counts?.applications ?? 0} · Документов: {health.counts?.documents ?? 0}
            </span>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Сводка проверки</h2>
        <div className="flex flex-wrap gap-2 mb-3">
          <button
            onClick={() => { setEntityType("document"); setEntityId(""); setSummary(null); }}
            className={`px-3 py-1 text-sm rounded-lg ${entityType === "document" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}
          >
            Документ
          </button>
          <button
            onClick={() => { setEntityType("interview_prep"); setEntityId(""); setSummary(null); }}
            className={`px-3 py-1 text-sm rounded-lg ${entityType === "interview_prep" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}
          >
            Подготовка к интервью
          </button>
        </div>

        <select
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2"
        >
          <option value="">— выберите —</option>
          {entityType === "document"
            ? docs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.document_kind} · {d.id.slice(0, 8)}…
                </option>
              ))
            : sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  Сессия {s.id.slice(0, 8)}…
                </option>
              ))}
        </select>
        <button
          onClick={handleFetch}
          disabled={fetching || !entityId}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {fetching ? "Загрузка…" : "Получить сводку"}
        </button>
      </div>

      {summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex flex-wrap gap-4 text-sm">
            {summary.ready != null && (
              <span className={`px-3 py-1 rounded-full ${summary.ready ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}`}>
                {summary.ready ? "Готово" : "Требует внимания"}
              </span>
            )}
            {summary.risk_level && (
              <span className="text-gray-600">Риск: {summary.risk_level}</span>
            )}
            {summary.requires_human_review && (
              <span className="text-orange-700">Требует ручной проверки</span>
            )}
          </div>

          {summary.blockers && summary.blockers.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-red-700 mb-1">Блокеры</h3>
              <ul className="space-y-1">
                {summary.blockers.map((b, i) => (
                  <li key={i} className="text-sm text-red-600">
                    • {String((b as Record<string, unknown>).message ?? b)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.warnings && summary.warnings.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-yellow-700 mb-1">Предупреждения</h3>
              <ul className="space-y-1">
                {summary.warnings.map((w, i) => (
                  <li key={i} className="text-sm text-yellow-600">
                    • {String((w as Record<string, unknown>).message ?? w)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.claims_requiring_confirmation && summary.claims_requiring_confirmation.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-yellow-700 mb-1">Утверждения, требующие подтверждения</h3>
              <ul className="space-y-1">
                {summary.claims_requiring_confirmation.map((c, i) => (
                  <li key={i} className="text-sm text-gray-700">
                    • {String((c as Record<string, unknown>).title ?? c)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.recommended_actions && summary.recommended_actions.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-1">Рекомендуемые действия</h3>
              <ul className="space-y-1">
                {summary.recommended_actions.map((a, i) => (
                  <li key={i} className="text-sm text-blue-700">
                    → {String((a as Record<string, unknown>).title ?? (a as Record<string, unknown>).action ?? a)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}