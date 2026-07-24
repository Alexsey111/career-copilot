"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import EvidenceCard from "@/components/EvidenceCard";
import type {
  InterviewPrepSessionRead,
  InterviewPrepReadinessRead,
  EvidenceSnippetItem,
} from "@/lib/types";

const SEVERITY_DOT: Record<string, string> = {
  high: "bg-[color:var(--brand-ink)]",
  medium: "bg-yellow-500",
  low: "bg-[color:var(--brand-teal-40)]",
};

export default function InterviewSessionPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const router = useRouter();

  const [session, setSession] = useState<InterviewPrepSessionRead | null>(null);
  const [readiness, setReadiness] = useState<InterviewPrepReadinessRead | null>(null);
  const [evidenceMap, setEvidenceMap] = useState<Record<string, EvidenceSnippetItem>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !id) return;
    Promise.allSettled([
      api.getInterviewPrep(token, id).then((r) => r as InterviewPrepSessionRead),
      api.getInterviewPrepReadiness(token, id).then((r) => r as InterviewPrepReadinessRead),
    ]).then(([sRes, rRes]) => {
      if (sRes.status === "fulfilled") {
        setSession(sRes.value);
        loadEvidence(sRes.value);
      }
      if (rRes.status === "fulfilled") setReadiness(rRes.value);
      setLoading(false);
    });
  }, [token, id]);

  const loadEvidence = (sess: InterviewPrepSessionRead) => {
    const ids = new Set<string>();
    sess.questions?.forEach((q) => q.recommended_evidence_ids?.forEach((eid) => ids.add(eid)));
    ids.forEach((eid) => {
      api
        .getEvidenceSnippet(token ?? "", eid)
        .then((r) => setEvidenceMap((prev) => ({ ...prev, [eid]: r as EvidenceSnippetItem })))
        .catch(() => {});
    });
  };

  if (loading) return <div className="text-[color:var(--brand-teal-60)]">Загрузка…</div>;
  if (!session) {
    return (
      <div className="max-w-4xl">
        <p className="text-[color:var(--brand-teal-60)]">Сессия не найдена.</p>
        <button onClick={() => router.push("/interview")} className="mt-3 text-[color:var(--brand-teal)] hover:underline">
          ← К списку сессий
        </button>
      </div>
    );
  }

  const blockers = (readiness?.blockers ?? session.readiness?.blockers ?? []) as Record<string, unknown>[];
  const warnings = (readiness?.warnings ?? session.readiness?.warnings ?? []) as Record<string, unknown>[];

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.back()} className="text-[color:var(--brand-teal-60)] hover:text-[color:var(--brand-teal)] mb-4">
        &larr; Назад
      </button>

      <h1 className="text-2xl font-bold mb-2">Сессия подготовки</h1>
      <DeterministicDisclaimer text="Детерминированный слой подготовки к интервью." />

      {/* Готовность */}
      <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6 mb-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="text-4xl font-bold text-[color:var(--brand-teal)]">
            {session.readiness_score ?? readiness?.readiness_score ?? "—"}
          </div>
          <div>
            <div className="font-semibold">Готовность к интервью</div>
            <div className="text-sm text-[color:var(--brand-teal-60)]">{session.prep_status ?? readiness?.prep_status ?? "—"}</div>
          </div>
        </div>

        {blockers.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-[color:var(--brand-ink)] mb-2">Блокеры</h3>
            <ul className="space-y-1">
              {blockers.map((b, i) => (
                <li key={i} className="text-sm text-[color:var(--brand-ink)]">
                  • {String(b.message ?? b.title ?? b)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {warnings.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-yellow-700 mb-2">Предупреждения</h3>
            <ul className="space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="text-sm text-yellow-600">
                  • {String(w.message ?? w.title ?? w)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Вопросы */}
      {session.questions && session.questions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6 mb-6">
          <h2 className="font-semibold mb-3">Ожидаемые вопросы ({session.questions.length})</h2>
          <div className="space-y-3">
            {session.questions.map((q, i) => (
              <div key={q.id ?? i} className="p-3 bg-[color:var(--brand-cream-soft)] rounded-lg">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {q.category && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)]">
                      {q.category}
                    </span>
                  )}
                  {q.competency_name && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal-60)]">
                      {q.competency_name}
                    </span>
                  )}
                  {q.requires_careful_answer && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--brand-lime-soft)] text-[color:var(--brand-teal)]">
                      требует осторожности
                    </span>
                  )}
                </div>
                <p className="text-sm text-[color:var(--brand-teal)]">{q.prompt}</p>

                {q.suggested_answer && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-[color:var(--brand-teal-60)]">Предлагаемый ответ:</p>
                    {typeof q.suggested_answer === "string" ? (
                      <pre className="text-xs text-[color:var(--brand-teal)] whitespace-pre-wrap bg-white p-2 rounded mt-1">
                        {q.suggested_answer}
                      </pre>
                    ) : (
                      <div className="text-xs text-[color:var(--brand-teal)] space-y-1 mt-1">
                        {q.suggested_answer.draft_text && (
                          <pre className="whitespace-pre-wrap bg-white p-2 rounded">
                            {q.suggested_answer.draft_text}
                          </pre>
                        )}
                        {q.suggested_answer.tech_stack && q.suggested_answer.tech_stack.length > 0 && (
                          <div>
                            <span className="font-medium">Стек:</span>{" "}
                            {q.suggested_answer.tech_stack.join(", ")}
                          </div>
                        )}
                        {q.suggested_answer.tradeoffs && q.suggested_answer.tradeoffs.length > 0 && (
                          <div>
                            <span className="font-medium">Компромиссы:</span>
                            <ul className="list-disc list-inside">
                              {q.suggested_answer.tradeoffs.map((t, i) => (
                                <li key={i}>{t}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {q.suggested_answer.talking_points && q.suggested_answer.talking_points.length > 0 && (
                          <div>
                            <span className="font-medium">Ключевые тезисы:</span>
                            <ul className="list-disc list-inside">
                              {q.suggested_answer.talking_points.map((tp, i) => (
                                <li key={i}>{tp}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {q.recommended_evidence_ids && q.recommended_evidence_ids.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <p className="text-xs font-medium text-[color:var(--brand-teal-60)]">Подкрепляющие доказательства:</p>
                    {q.recommended_evidence_ids.map((eid) =>
                      evidenceMap[eid] ? (
                        <EvidenceCard
                          key={eid}
                          token={token ?? ""}
                          snippet={evidenceMap[eid]}
                          showActions={false}
                        />
                      ) : null
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Слабые места */}
      {session.weak_areas && session.weak_areas.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
          <h2 className="font-semibold mb-3">Слабые места</h2>
          <div className="space-y-2">
            {session.weak_areas.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span
                  className={`inline-block w-2 h-2 rounded-full mt-1.5 ${SEVERITY_DOT[w.severity ?? "low"] ?? "bg-[color:var(--brand-teal-40)]"}`}
                />
                <div>
                  <span className="font-medium">{w.code}</span>
                  {w.message ? `: ${w.message}` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}