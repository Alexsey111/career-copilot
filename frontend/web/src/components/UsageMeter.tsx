import type { PlanUsageItem } from "@/lib/types";

/**
 * Прогресс-бар использования квоты по действию: used / limit за window_days.
 * Если limit=null — безлимитный (paid), рисуем «∞».
 */
export default function UsageMeter({ usage }: { usage: PlanUsageItem }) {
  const limit = usage.limit;
  const ratio = limit != null && limit > 0 ? Math.min(1, usage.used / limit) : 0;
  const color =
    ratio >= 1 ? "bg-red-500" : ratio >= 0.8 ? "bg-yellow-500" : "bg-green-500";

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-gray-700">{usage.action}</span>
        <span className="text-gray-500">
          {usage.used}
          {limit != null ? ` / ${limit}` : " / ∞"}
          {usage.window_days ? ` · за ${usage.window_days} дн.` : ""}
        </span>
      </div>
      {limit != null ? (
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className={`${color} h-2 rounded-full transition-all`}
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      ) : (
        <div className="text-xs text-green-600">Безлимитно (платный план)</div>
      )}
    </div>
  );
}