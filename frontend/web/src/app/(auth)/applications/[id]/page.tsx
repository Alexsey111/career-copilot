"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import VacancyFitBlock from "@/components/VacancyFitBlock";
import type {
  ApplicationWorkflowResponse,
  ApplicationStatusHistoryItem,
  ApplicationEventItem,
} from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  ready: "Готов к отправке",
  applied: "Отправлено",
  screening: "Скрининг",
  interview: "Интервью",
  offer: "Оффер",
  rejected: "Отказ",
  withdrawn: "Отозвано",
};

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const toast = useToastCtx();
  const router = useRouter();

  const [app, setApp] = useState<any>(null);
  const [workflow, setWorkflow] = useState<ApplicationWorkflowResponse | null>(null);
  const [timeline, setTimeline] = useState<ApplicationStatusHistoryItem[]>([]);
  const [activityLog, setActivityLog] = useState<ApplicationEventItem[]>([]);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [externalLink, setExternalLink] = useState("");
  const [submitSource, setSubmitSource] = useState("manual");

  const reload = () => {
    if (!token || !id) return;
    Promise.allSettled([
      api.getApplication(token, id).then((r) => r as any),
      api.getApplicationWorkflow(token, id).then((r) => r as ApplicationWorkflowResponse),
      api.getApplicationTimeline(token, id).then((r) => r as ApplicationStatusHistoryItem[]),
      api.getApplicationActivityLog(token, id).then((r) => r as ApplicationEventItem[]),
    ]).then(([appRes, wfRes, tlRes, logRes]) => {
      if (appRes.status === "fulfilled") {
        setApp(appRes.value);
        const vacancyId = appRes.value?.vacancy_id;
        if (vacancyId) {
          api.getVacancyAnalysis(token, vacancyId).then((r: any) => {
            if (r?.analysis_id) setAnalysisId(r.analysis_id);
          }).catch(() => {});
        }
      }
      if (wfRes.status === "fulfilled") setWorkflow(wfRes.value);
      if (tlRes.status === "fulfilled") setTimeline(tlRes.value);
      if (logRes.status === "fulfilled") setActivityLog(logRes.value);
    });
  };

  useEffect(() => {
    reload();
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id]);

  const handleTransition = async (newStatus: string) => {
    if (!token || !id) return;
    try {
      await api.updateApplicationStatus(token, id, newStatus);
      toast.success(`Статус → ${STATUS_LABELS[newStatus] ?? newStatus}`);
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Переход недоступен");
    }
  };

  const handleSubmit = async () => {
    if (!token || !id) return;
    setSubmitting(true);
    try {
      await api.submitApplication(token, id, {
        source: submitSource,
        external_link: externalLink.trim() || undefined,
      });
      toast.success("Отклик отмечен как отправленный");
      setExternalLink("");
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Отправка не удалась");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-[color:var(--brand-teal-60)]">Загрузка…</div>;

  if (!app) {
    return (
      <div className="max-w-4xl">
        <p className="text-[color:var(--brand-teal-60)]">Отклик не найден.</p>
        <button onClick={() => router.push("/applications")} className="mt-3 text-[color:var(--brand-teal)] hover:underline">
          ← К списку откликов
        </button>
      </div>
    );
  }

  const allowed = workflow?.allowed_transitions ?? [];
  const canSubmit = workflow?.can_submit ?? false;

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.back()} className="text-[color:var(--brand-teal-60)] hover:text-[color:var(--brand-teal)] mb-4">
        &larr; Назад
      </button>

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">{app.vacancy?.title ?? "Отклик"}</h1>
        <span className="text-sm text-[color:var(--brand-teal-60)]">
          Статус: {STATUS_LABELS[app.status] ?? app.status}
        </span>
      </div>

      <p className="text-sm text-[color:var(--brand-teal-60)] mb-6">
        {app.vacancy?.company ?? ""} {app.applied_at ? `• отправлен ${new Date(app.applied_at).toLocaleDateString("ru")}` : ""}
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Workflow-переходы */}
          <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
            <h2 className="font-semibold mb-3">Действия по статусу</h2>
            {allowed.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {allowed.map((st) => (
                  <button
                    key={st}
                    onClick={() => handleTransition(st)}
                    className="px-3 py-1 text-sm bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)] rounded-lg hover:bg-[color:var(--brand-teal-5)]"
                  >
                    → {STATUS_LABELS[st] ?? st}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[color:var(--brand-teal-60)]">Доступных переходов нет (финальный статус).</p>
            )}

            {canSubmit && (
              <div className="mt-4 border-t border-[color:var(--brand-teal-10)] pt-4">
                <h3 className="text-sm font-medium mb-2">Отправка отклика</h3>
                <p className="text-xs text-[color:var(--brand-teal-60)] mb-2">
                  Система не отправляет отклик автоматически. Отметьте, что отправили вручную.
                </p>
                <select
                  value={submitSource}
                  onChange={(e) => setSubmitSource(e.target.value)}
                  className="w-full px-3 py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm mb-2"
                >
                  <option value="manual">Вручную</option>
                  <option value="hh">Через HH</option>
                  <option value="external">Внешний канал</option>
                </select>
                <input
                  value={externalLink}
                  onChange={(e) => setExternalLink(e.target.value)}
                  placeholder="Ссылка на внешний отклик (необязательно)"
                  className="w-full px-3 py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm mb-2"
                />
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="px-4 py-2 bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded-lg hover:bg-[#b8e85c] disabled:opacity-50 text-sm"
                >
                  {submitting ? "Сохранение…" : "Я отправил отклик"}
                </button>
              </div>
            )}
          </div>

          {/* Fit-блок вакансии */}
          {app.vacancy_id && token && (
            <VacancyFitBlock token={token} vacancyId={app.vacancy_id} analysisId={analysisId} />
          )}

          {/* Timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
            <h2 className="font-semibold mb-3">История статусов</h2>
            {timeline.length > 0 ? (
              <ul className="space-y-2">
                {timeline.map((t, i) => (
                  <li key={i} className="text-sm flex justify-between">
                    <span className="font-medium">{STATUS_LABELS[t.status] ?? t.status}</span>
                    <span className="text-[color:var(--brand-teal-40)]">
                      {t.changed_at ? new Date(t.changed_at).toLocaleString("ru") : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-[color:var(--brand-teal-60)]">Истории нет.</p>
            )}
          </div>
        </div>

        {/* Activity log */}
        <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
          <h2 className="font-semibold mb-3">Журнал действий</h2>
          {activityLog.length > 0 ? (
            <ul className="space-y-2">
              {activityLog.map((e, i) => (
                <li key={i} className="text-sm">
                  <p className="text-[color:var(--brand-teal)]">{e.event_label ?? e.event_type}</p>
                  {e.created_at && (
                    <p className="text-xs text-[color:var(--brand-teal-40)]">
                      {new Date(e.created_at).toLocaleString("ru")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[color:var(--brand-teal-60)]">Событий нет.</p>
          )}
        </div>
      </div>
    </div>
  );
}