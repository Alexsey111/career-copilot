"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import DeterministicDisclaimer from "@/components/DeterministicDisclaimer";
import type { CareerInsightsResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const PRIORITY_COLORS: Record<string, string> = {
  high: "border-l-red-400",
  medium: "border-l-yellow-400",
  low: "border-l-green-400",
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

  if (loading) {
    return (
      <div className="max-w-4xl space-y-4">
        <h1 className="text-2xl font-bold">Карьерная стратегия</h1>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-48" />
      </div>
    );
  }
  if (!insights) {
    return <div className="text-muted-foreground">Нет данных для аналитики.</div>;
  }

  const repeatedGaps = (insights.repeated_gaps ?? []) as Record<string, unknown>[];
  const patterns = (insights.application_patterns ?? {}) as Record<string, unknown>;
  const recommendations = (insights.strategic_recommendations ?? []) as Record<string, unknown>[];
  const coverageTrends = insights.evidence_coverage_trends as Record<string, unknown> | undefined;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">Карьерная стратегия</h1>
        <DeterministicDisclaimer text="Детерминированные операционные рекомендации, а не вероятности." />
      </div>

      {/* Метрики паттернов */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
        <Card>
          <CardHeader>
            <CardTitle>Повторяющиеся пробелы</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {repeatedGaps.map((g, i) => (
                <li key={i} className="text-sm border-l-4 border-l-red-400 pl-3">
                  <span className="font-medium">{String(g.keyword ?? g.name ?? "Пробел")}</span>
                  <span className="text-muted-foreground ml-2">
                    ×{Number(g.count ?? g.occurrences ?? 0)}
                  </span>
                  {g.severity ? (
                    <span className="text-xs text-muted-foreground ml-2">[{String(g.severity)}]</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Тренды покрытия */}
      {coverageTrends && Object.keys(coverageTrends).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Тренды покрытия доказательств</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {Object.entries(coverageTrends).map(([k, v]) => (
                <li key={k} className="flex justify-between">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-medium">{String(v)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Рекомендации */}
      {recommendations.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold">Стратегические рекомендации</h2>
          {recommendations.map((r, i) => (
            <Card
              key={i}
              className={`border-l-4 ${PRIORITY_COLORS[String(r.priority ?? "medium")] ?? "border-l-gray-300"}`}
            >
              <CardContent className="pt-4">
                <p className="font-medium">{String(r.title ?? r.code ?? `Рекомендация ${i + 1}`)}</p>
                {r.message ? <p className="text-sm text-muted-foreground mt-1">{String(r.message)}</p> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {repeatedGaps.length === 0 && recommendations.length === 0 && (
        <p className="text-muted-foreground text-sm">
          Недостаточно данных. Отправьте несколько откликов, чтобы появились рекомендации.
        </p>
      )}
    </div>
  );
}

function Metric({ value, label, color, text = false }: { value: unknown; label: string; color: string; text?: boolean }) {
  return (
    <Card>
      <CardContent className="text-center py-4">
        <div className={`${text ? "text-base" : "text-2xl"} font-bold ${color}`}>{String(value)}</div>
        <div className="text-xs text-muted-foreground mt-1">{label}</div>
      </CardContent>
    </Card>
  );
}
