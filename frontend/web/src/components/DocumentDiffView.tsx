import type { DocumentDiffResponse } from "@/lib/types";

const CHANGE_COLORS: Record<string, string> = {
  added: "text-green-700",
  removed: "text-red-700",
  changed: "text-yellow-700",
  unchanged: "text-gray-500",
};

/**
 * Структурный diff между двумя версиями документа (GET /documents/{base}/diff/{target}).
 * Рендерит секции построчно с подсветкой типа изменения.
 */
export default function DocumentDiffView({ diff }: { diff: DocumentDiffResponse | null }) {
  if (!diff || !diff.sections || diff.sections.length === 0) {
    return <p className="text-sm text-gray-500">Нет различий для отображения.</p>;
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Сравнение {diff.base_document_id.slice(0, 8)}… → {diff.target_document_id.slice(0, 8)}…
        ({diff.document_kind})
      </p>
      {diff.sections.map((s, i) => (
        <div key={i} className="border border-gray-200 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-sm font-medium text-gray-800">{s.section}</h4>
            {s.change && (
              <span className={`text-xs capitalize ${CHANGE_COLORS[s.change] ?? "text-gray-500"}`}>
                {s.change}
              </span>
            )}
          </div>
          {s.base && (
            <pre className="text-xs text-red-600 whitespace-pre-wrap bg-red-50 p-2 rounded mb-1">
              {s.base}
            </pre>
          )}
          {s.target && (
            <pre className="text-xs text-green-600 whitespace-pre-wrap bg-green-50 p-2 rounded">
              {s.target}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}