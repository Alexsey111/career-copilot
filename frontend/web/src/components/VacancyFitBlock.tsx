"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useToastCtx } from "@/contexts/ToastContext";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type { VacancyFitResponse } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  ready: "text-[color:var(--brand-teal)] bg-[color:var(--brand-lime-soft)] border-green-300",
  apply: "text-yellow-700 bg-yellow-50 border-yellow-300",
  caution: "text-yellow-700 bg-yellow-50 border-yellow-300",
  work: "text-[color:var(--brand-ink)] bg-[color:var(--brand-ink-10)] border-[color:var(--brand-ink)]",
};

function readinessLabel(rec?: string): { label: string; cls: string } {
  if (!rec) return { label: "—", cls: "text-[color:var(--brand-teal-60)] bg-[color:var(--brand-cream-soft)] border-[color:var(--brand-teal-20)]" };
  const lower = rec.toLowerCase();
  if (lower.includes("ready")) return { label: "Готово к отклику", cls: STATUS_COLORS.ready };
  if (lower.includes("caution")) return { label: "Отклик с осторожностью", cls: STATUS_COLORS.caution };
  if (lower.includes("work")) return { label: "Требует доработки", cls: STATUS_COLORS.work };
  return { label: rec, cls: "text-[color:var(--brand-teal)] bg-[color:var(--brand-cream-soft)] border-[color:var(--brand-teal-20)]" };
}

function FitMetric({ label, score }: { label: string; score: number }) {
  const color = score >= 75 ? "text-[color:var(--brand-teal)]" : score >= 50 ? "text-yellow-600" : "text-[color:var(--brand-ink)]";
  return (
    <div className="bg-[color:var(--brand-cream-soft)] rounded-lg p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{score}</div>
      <div className="text-xs text-[color:var(--brand-teal-60)] mt-1">{label}</div>
    </div>
  );
}

function RequirementRow({ req }: { req: VacancyFitResponse["evidence_coverage"]["strong"][number] }) {
  const [expanded, setExpanded] = useState(false);
  const coverageColor =
    req.coverage_level === "strong"
      ? "text-[color:var(--brand-teal)]"
      : req.coverage_level === "medium"
        ? "text-yellow-600"
        : "text-[color:var(--brand-ink)]";
  return (
    <div className="border-b border-[color:var(--brand-teal-10)] last:border-0 py-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left flex items-start justify-between gap-2"
      >
        <span className="text-sm font-medium text-[color:var(--brand-teal)]">{req.requirement}</span>
        <span className={`text-xs ${coverageColor} capitalize whitespace-nowrap`}>
          {req.coverage_level}
        </span>
      </button>
      {req.reason && <p className="text-xs text-[color:var(--brand-teal-60)] mt-1">{req.reason}</p>}
      {expanded && req.supporting_evidence && req.supporting_evidence.length > 0 && (
        <ul className="mt-2 space-y-1 pl-3 border-l-2 border-[color:var(--brand-teal-20)]">
          {req.supporting_evidence.map((ev, i) => (
            <li key={i} className="text-xs text-[color:var(--brand-teal-60)]">
              <span className="font-medium">{ev.title}</span>
              {ev.fact_status && (
                <span className="ml-2 text-[color:var(--brand-teal-40)]">[{ev.fact_status}]</span>
              )}
              {ev.snippet_text && <p className="text-[color:var(--brand-teal-60)] mt-0.5">{ev.snippet_text}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Fit-блок вакансии: 5 метрик (overall/skills/evidence/experience/leadership),
 * readiness-рекомендация, gap_severity и coverage по требованиям (strong/medium/missing).
 * Переиспользуется на странице вакансии и в деталях отклика.
 *
 * Требует предварительного analysis (analysisId) — если его нет, показывает
 * подсказку «сначала проанализируйте вакансию».
 */
export default function VacancyFitBlock({
  token,
  vacancyId,
  analysisId,
}: {
  token: string;
  vacancyId: string;
  analysisId?: string | null;
}) {
  const toast = useToastCtx();
  const [fit, setFit] = useState<VacancyFitResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!analysisId) {
      setFit(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .getVacancyFit(token, vacancyId)
      .then((data) => {
        if (!cancelled) setFit(data as VacancyFitResponse);
      })
      .catch((err) => {
        if (!cancelled) {
          // 400/404 — анализ или профиль отсутствуют; тихо, без тревожного тоста
          setFit(null);
          toast.error(err instanceof Error ? err.message : "Fit недоступен");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, vacancyId, analysisId, toast]);

  if (!analysisId) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
        <h2 className="font-semibold mb-2">Соответствие (fit)</h2>
        <p className="text-sm text-[color:var(--brand-teal-60)]">
          Сначала проанализируйте вакансию — fit-разбор строится по результатам анализа.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
        <p className="text-[color:var(--brand-teal-60)]">Расчёт соответствия…</p>
      </div>
    );
  }

  if (!fit) return null;

  const rec = readinessLabel(fit.readiness_recommendation);
  const coverage = fit.evidence_coverage;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6 space-y-4">
      <div>
        <h2 className="font-semibold">Соответствие (fit)</h2>
        <DeterministicDisclaimer />
      </div>

      <div className={`inline-block px-3 py-1 rounded-full border text-sm font-medium ${rec.cls}`}>
        {rec.label}
      </div>

      <div className="grid grid-cols-5 gap-2">
        <FitMetric label="Общий" score={fit.overall_fit_score} />
        <FitMetric label="Навыки" score={fit.skills_fit} />
        <FitMetric label="Доказательства" score={fit.evidence_fit} />
        <FitMetric label="Опыт" score={fit.experience_fit} />
        <FitMetric label="Лидерство" score={fit.leadership_fit} />
      </div>

      {fit.gap_severity && (
        <p className="text-xs text-[color:var(--brand-teal-60)]">
          Основной риск: <span className="font-medium capitalize">{fit.gap_severity}</span>
        </p>
      )}

      {coverage && (
        <div className="space-y-3">
          {coverage.strong.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Хорошо подтверждено</h3>
              {coverage.strong.map((r, i) => (
                <RequirementRow key={i} req={r} />
              ))}
            </div>
          )}
          {coverage.medium.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-yellow-700 mb-1">Частично подтверждено</h3>
              {coverage.medium.map((r, i) => (
                <RequirementRow key={i} req={r} />
              ))}
            </div>
          )}
          {coverage.missing.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-[color:var(--brand-ink)] mb-1">Пока не подтверждено</h3>
              {coverage.missing.map((r, i) => (
                <RequirementRow key={i} req={r} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}