import type { PlanUsageItem } from "@/lib/types";

/**
 * Прогресс-бар использования квоты по действию: used / limit за window.
 * Если limit=null — безлимитный (paid), рисуем «∞».
 *
 * При превышении (used >= limit) показываем причину: «Превышено» и формат
 * окна. Это лечит «квота непонятна» — пользователь видит, что лимит уже
 * исчерпан и что счётчик скользящий (дни/часы, не «за всё время»).
 */
export default function UsageMeter({ usage }: { usage: PlanUsageItem }) {
  const limit = usage.limit;
  const isUnlimited = limit == null;
  const ratio = !isUnlimited && limit > 0 ? Math.min(1, usage.used / limit) : 0;
  const overflow = !isUnlimited && usage.used >= limit;
  const color = overflow
    ? "bg-red-500"
    : ratio >= 0.8
      ? "bg-yellow-500"
      : "bg-green-500";

  // Окно: секунды (demo vacancy_import) или дни.
  const windowLabel = usage.window_seconds
    ? `за ${formatWindowSeconds(usage.window_seconds)}`
    : usage.window_days
      ? `за ${usage.window_days} ${pluralDays(usage.window_days)}`
      : "";

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-gray-700">{usage.action}</span>
        <span className={overflow ? "text-red-600 font-medium" : "text-gray-500"}>
          {usage.used}
          {isUnlimited ? " / ∞" : ` / ${limit}`}
          {windowLabel ? ` · ${windowLabel}` : ""}
          {overflow ? " · превышено" : ""}
        </span>
      </div>
      {isUnlimited ? (
        <div className="text-xs text-green-600">Безлимитно (платный план)</div>
      ) : (
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className={`${color} h-2 rounded-full transition-all`}
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

function pluralDays(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "день";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "дня";
  return "дней";
}

function formatWindowSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds} сек`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} мин`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} ч`;
  return `${Math.round(seconds / 86400)} дн`;
}
