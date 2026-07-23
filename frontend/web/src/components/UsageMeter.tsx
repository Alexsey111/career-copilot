"use client";

import { useSyncExternalStore } from "react";
import type { PlanUsageItem } from "@/lib/types";

/**
 * Прогресс-бар использования квоты по действию: used / limit за window.
 * Если limit=null — безлимитный (paid), рисуем «∞».
 *
 * При превышении (used >= limit) показываем причину: «Превышено» и формат
 * окна. Это лечит «квота непонятна» — пользователь видит, что лимит уже
 * исчерпан и что счётчик скользящий (дни/часы, не «за всё время»).
 *
 * Bug#3.2: при used>0 рисуем обратный отсчёт «сброс через X» —
 * вычисляем из oldest_in_window + window (days/seconds). Тикает раз в секунду
 * (для секундных окон) и раз в минуту (для дневных) — пересчитываем
 * лениво через ``tick`` state, чтобы не было заметной нагрузки.
 */
export default function UsageMeter({ usage }: { usage: PlanUsageItem }) {
  const limit = usage.limit;
  const isUnlimited = limit == null;
  const ratio = !isUnlimited && limit > 0 ? Math.min(1, usage.used / limit) : 0;
  const overflow = !isUnlimited && usage.used >= limit;
  const color = overflow
    ? "bg-destructive"
    : ratio >= 0.8
      ? "bg-yellow-500"
      : "bg-green-500";

  // Окно: секунды (demo vacancy_import) или дни.
  const windowLabel = usage.window_seconds
    ? `за ${formatWindowSeconds(usage.window_seconds)}`
    : usage.window_days
      ? `за ${usage.window_days} ${pluralDays(usage.window_days)}`
      : "";

  const resetLabel = useResetLabel(usage);

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-foreground">{usage.action}</span>
        <span
          className={overflow ? "text-destructive font-medium" : "text-muted-foreground"}
        >
          {usage.used}
          {isUnlimited ? " / ∞" : ` / ${limit}`}
          {windowLabel ? ` · ${windowLabel}` : ""}
          {overflow ? " · превышено" : ""}
        </span>
      </div>
      {isUnlimited ? (
        <div className="text-xs text-green-600">Безлимитно (платный план)</div>
      ) : (
        <>
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className={`${color} h-2 rounded-full transition-all`}
              style={{ width: `${ratio * 100}%` }}
            />
          </div>
          {resetLabel ? (
            <div className="mt-1 text-xs text-muted-foreground">
              {overflow ? "Следующий сброс " : "Сброс "}
              <span className="font-medium text-foreground">{resetLabel}</span>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

/** Возвращает «через 12 мин» / «через 3 ч 15 мин» / null (если used=0).
 *
 * React 19 считает вызов ``Date.now()`` в теле хука нечистой функцией и
 * запрещает ``setState`` напрямую внутри ``useEffect``. Используем
 * ``useSyncExternalStore`` с тикающим «store»-таймером — это идиоматический
 * способ подписаться на изменяющийся извне источник времени.
 */
function useResetLabel(usage: PlanUsageItem): string | null {
  const oldest = usage.oldest_in_window;
  const windowSeconds = usage.window_seconds ?? null;
  const windowDays = usage.window_days ?? null;
  const windowTotalSec =
    windowSeconds != null ? windowSeconds : windowDays != null ? windowDays * 86400 : null;
  const active = oldest != null && windowTotalSec != null;
  // Секундное окно тикает чаще — пользователь видит точный «сброс через X сек».
  const tickMs = windowSeconds != null ? 1000 : 60000;
  const now = useTickingNow(active, tickMs);

  if (!active || oldest == null || windowTotalSec == null) return null;
  const oldestMs = Date.parse(oldest);
  if (Number.isNaN(oldestMs)) return null;

  // Когда «самая старая запись + window» — это и есть момент выхода из окна.
  // После этого used гарантированно уменьшится на 1.
  const resetAtMs = oldestMs + windowTotalSec * 1000;
  const remainingMs = resetAtMs - now;
  if (remainingMs <= 0) return "в ближайшую минуту";
  return `через ${formatRemaining(remainingMs)}`;
}

/** Тикающий «now» через ``useSyncExternalStore`` — без ``setState`` в effect. */
function useTickingNow(active: boolean, tickMs: number): number {
  return useSyncExternalStore(
    (notify) => {
      if (!active) return () => {};
      const id = setInterval(notify, tickMs);
      return () => clearInterval(id);
    },
    () => Date.now(),
    () => 0,
  );
}

function formatRemaining(ms: number): string {
  const totalSec = Math.ceil(ms / 1000);
  if (totalSec < 60) return `${totalSec} сек`;
  if (totalSec < 3600) {
    const m = Math.ceil(totalSec / 60);
    return `${m} мин`;
  }
  if (totalSec < 86400) {
    const h = Math.floor(totalSec / 3600);
    const m = Math.ceil((totalSec - h * 3600) / 60);
    return m > 0 ? `${h} ч ${m} мин` : `${h} ч`;
  }
  const d = Math.floor(totalSec / 86400);
  const h = Math.ceil((totalSec - d * 86400) / 3600);
  return h > 0 ? `${d} ${pluralDays(d)} ${h} ч` : `${d} ${pluralDays(d)}`;
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
