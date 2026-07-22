"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type { CareerInsightsResponse } from "@/lib/types";

const PRIORITY_COLORS: Record<string, string> = {
  high: "border-red-400",
  medium: "border-yellow-400",
  low: "border-green-400",
};

export default function CareerPage() {
  const { token } = useAuth();
  const [insights, setInsights] = useState<CareerInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api
      .getCareerInsights(token)
      .then((r) => setInsights(r as CareerInsightsResponse))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="text-gray-500">Загрузка…</div>;
  if (!insights) return <div className="text-gray-500">Нет данных для аналитики.</div>;

  const repeatedGaps = (insights.repeated_gaps ?? []) as Record<string, unknown>[];
  const patterns = (insights.application_patterns ?? {}) as Record<string, unknown>;
  const recommendations = (insights.strategic_recommendations ?? []) as Record<string, unknown>[];
  const coverageTrends = insights.evidence_coverage_trends as Record<string, unknown> | undefined;

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-2">Карьерная стратегия</h1>
      <DeterministicDisclaimer text="Детерминированные операционные рекомендации, а не вероятности." />

      {/* Метрики паттернов */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Metric value={patterns.applications_sent ?? 0} label="Отправлено" color="text-blue-600" />
        <Metric value={patterns.interviews_reached ?? 0} label="Интервью" color="text-purple-600" />
        <Metric value={patterns.offers_count ?? 0} label="Офферов" color="text-green-600" />
        <Metric
          value={patterns.most_common_rejection_stage ? String(patterns.most_common_rejection_stage) : "—"}
          label="Частый отказ на"
          color="text-red-600"
          text
        />
      </div>

      {/* Повторяющиеся пробелы */}
      {repeatedGaps.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold mb-3">Повторяющиеся пробелы</h2>
          <ul className="space-y-2">
            {repeatedGaps.map((g, i) => (
              <li key={i} className="text-sm border-l-4 border-red-400 pl-3">
                <span className="font-medium">{String(g.keyword ?? g.name ?? "Пробел")}</span>
                <span className="text-gray-400 ml-2">
                  ×{Number(g.count ?? g.occurrences ?? 0)}
                </span>
                {g.severity ? (
                  <span className="text-xs text-gray-400 ml-2">[{String(g.severity)}]</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Тренды покрытия */}
      {coverageTrends && Object.keys(coverageTrends).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold mb-3">Тренды покрытия доказательств</h2>
          <ul className="space-y-1 text-sm">
            {Object.entries(coverageTrends).map(([k, v]) => (
              <li key={k} className="flex justify-between">
                <span className="text-gray-600">{k}</span>
                <span className="font-medium">{String(v)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Рекомендации */}
      {recommendations.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold">Стратегические рекомендации</h2>
          {recommendations.map((r, i) => (
            <div
              key={i}
              className={`bg-white rounded-xl border-l-4 ${PRIORITY_COLORS[String(r.priority ?? "medium")] ?? "border-gray-300"} border border-gray-200 p-4`}
            >
              <p className="font-medium text-gray-800">{String(r.title ?? r.code ?? `Рекомендация ${i + 1}`)}</p>
              {r.message ? <p className="text-sm text-gray-600 mt-1">{String(r.message)}</p> : null}
            </div>
          ))}
        </div>
      )}

      {repeatedGaps.length === 0 && recommendations.length === 0 && (
        <p className="text-gray-500 text-sm">
          Недостаточно данных. Отправьте несколько откликов, чтобы появились рекомендации.
        </p>
      )}
    </div>
  );
}

function Metric({ value, label, color, text = false }: { value: unknown; label: string; color: string; text?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
      <div className={`${text ? "text-base" : "text-2xl"} font-bold ${color}`}>{String(value)}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}