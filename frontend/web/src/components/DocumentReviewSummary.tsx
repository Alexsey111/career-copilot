import type { DocumentReviewSummary } from "@/lib/types";
import ClaimsNeedingConfirmation from "@/components/ClaimsNeedingConfirmation";

function Metric({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;
  return (
    <div className="text-sm">
      <span className="text-[color:var(--brand-teal-60)]">{label}: </span>
      <span className="font-medium text-[color:var(--brand-teal)]">{String(value)}</span>
    </div>
  );
}

/**
 * Сводка проверки документа (readiness + quality + provenance + claims +
 * selected achievements/evidence + matched/missing keywords + preview).
 * Зеркало многосекционного workspace из streamlit, но в компактном виде.
 */
export default function DocumentReviewSummaryView({
  summary,
}: {
  summary: DocumentReviewSummary;
}) {
  const readiness = summary.readiness as Record<string, unknown> | undefined;
  const quality = summary.quality as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <Metric label="Статус" value={summary.review_status} />
        <Metric label="Версия" value={summary.version_label} />
        <Metric label="Активный" value={summary.is_active ? "да" : "нет"} />
      </div>

      {readiness && (
        <div className="bg-[color:var(--brand-cream-soft)] rounded-lg p-3">
          <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Готовность</h3>
          <div className="flex flex-wrap gap-4">
            <Metric label="Score" value={readiness.score ?? readiness.readiness_score} />
            <Metric label="Статус" value={readiness.status ?? readiness.prep_status} />
          </div>
        </div>
      )}

      {quality && (
        <div className="bg-[color:var(--brand-cream-soft)] rounded-lg p-3">
          <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Качество</h3>
          <div className="flex flex-wrap gap-4">
            <Metric label="Оценка" value={quality.score ?? quality.grade} />
            <Metric label="Статус" value={quality.status} />
          </div>
        </div>
      )}

      {summary.claims_needing_confirmation && summary.claims_needing_confirmation.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-yellow-700 mb-1">
            Утверждения, требующие подтверждения
          </h3>
          <ClaimsNeedingConfirmation claims={summary.claims_needing_confirmation} />
        </div>
      )}

      {summary.selected_achievements && summary.selected_achievements.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Выбранные достижения</h3>
          <ul className="space-y-1">
            {summary.selected_achievements.map((a, i) => (
              <li key={i} className="text-sm text-[color:var(--brand-teal)]">
                • {(a.title as string) || JSON.stringify(a).slice(0, 80)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary.matched_keywords && summary.matched_keywords.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Совпавшие ключевые слова</h3>
          <div className="flex flex-wrap gap-1">
            {summary.matched_keywords.map((k, i) => (
              <span key={i} className="text-xs bg-[color:var(--brand-lime-soft)] text-[color:var(--brand-teal)] px-2 py-0.5 rounded">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.missing_keywords && summary.missing_keywords.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[color:var(--brand-ink)] mb-1">Пропущенные ключевые слова</h3>
          <div className="flex flex-wrap gap-1">
            {summary.missing_keywords.map((k, i) => (
              <span key={i} className="text-xs bg-[color:var(--brand-ink-10)] text-[color:var(--brand-ink)] px-2 py-0.5 rounded">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.rendered_text_preview && (
        <div>
          <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Предпросмотр</h3>
          <pre className="text-sm text-[color:var(--brand-teal)] whitespace-pre-wrap bg-[color:var(--brand-cream-soft)] p-3 rounded max-h-72 overflow-y-auto">
            {summary.rendered_text_preview}
          </pre>
        </div>
      )}
    </div>
  );
}