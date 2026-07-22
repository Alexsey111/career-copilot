/**
 * Список утверждений, требующих подтверждения (claims_needing_confirmation).
 * Переиспользуется в review-workspace документа (Этап B) и trust panel (Этап H).
 * Бэкенд возвращает произвольные объекты — рендерим человекочитаемо по
 * типичным полям (title/claim/reason/evidence), деградируя к JSON.
 */
export default function ClaimsNeedingConfirmation({
  claims,
}: {
  claims: Record<string, unknown>[];
}) {
  if (!claims || claims.length === 0) {
    return (
      <p className="text-sm text-green-600">Нет утверждений, требующих подтверждения.</p>
    );
  }
  return (
    <ul className="space-y-2">
      {claims.map((c, i) => {
        const title = (c.title || c.claim || c.text || "") as string;
        const reason = (c.reason || c.evidence_note || "") as string;
        return (
          <li key={i} className="text-sm border-l-4 border-yellow-400 pl-3 py-1">
            <p className="font-medium text-gray-800">{title || `Утверждение #${i + 1}`}</p>
            {reason && <p className="text-gray-500 text-xs mt-0.5">{reason}</p>}
          </li>
        );
      })}
    </ul>
  );
}