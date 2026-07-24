import type { DocumentDiffResponse } from "@/lib/types";

const CHANGE_COLORS: Record<string, string> = {
  added: "text-[color:var(--brand-teal)]",
  removed: "text-[color:var(--brand-ink)]",
  changed: "text-yellow-700",
  unchanged: "text-[color:var(--brand-teal-60)]",
};

/**
 * Структурный diff между двумя версиями документа (GET /documents/{base}/diff/{target}).
 * Рендерит секции построчно с подсветкой типа изменения.
 */
export default function DocumentDiffView({ diff }: { diff: DocumentDiffResponse | null }) {
  if (!diff || !diff.sections || diff.sections.length === 0) {
    return <p className="text-sm text-[color:var(--brand-teal-60)]">Нет различий для отображения.</p>;
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-[color:var(--brand-teal-60)]">
        Сравнение {diff.base_document_id.slice(0, 8)}… → {diff.target_document_id.slice(0, 8)}…
        ({diff.document_kind})
      </p>
      {diff.sections.map((s, i) => (
        <div key={i} className="border border-[color:var(--brand-teal-20)] rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-sm font-medium text-[color:var(--brand-teal)]">{s.section}</h4>
            {s.change && (
              <span className={`text-xs capitalize ${CHANGE_COLORS[s.change] ?? "text-[color:var(--brand-teal-60)]"}`}>
                {s.change}
              </span>
            )}
          </div>
          {s.base && (
            <pre className="text-xs text-[color:var(--brand-ink)] whitespace-pre-wrap bg-[color:var(--brand-ink-10)] p-2 rounded mb-1">
              {s.base}
            </pre>
          )}
          {s.target && (
            <pre className="text-xs text-[color:var(--brand-teal)] whitespace-pre-wrap bg-[color:var(--brand-lime-soft)] p-2 rounded">
              {s.target}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}