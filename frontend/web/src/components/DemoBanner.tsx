"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MySubscriptionResponse } from "@/lib/types";

/**
 * Баннер demo-режима: показывает остаток лимита импорта вакансий (3 в час).
 * Дёргает GET /me/billing/subscription → usage.vacancy_import (used/limit,
 * секундное окно). Если эндпоинт недоступен — показывает статичный баннер.
 *
 * `onUsageChange` — колбэк после успешного импорта, чтобы перечитать usage.
 */
export default function DemoBanner({
  token,
  refreshKey = 0,
}: {
  token: string;
  refreshKey?: number;
}) {
  const [usage, setUsage] = useState<{
    used: number;
    limit: number | null;
    windowSeconds: number | null;
  } | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .getSubscription(token)
      .then((r) => {
        const sub = r as MySubscriptionResponse;
        const item = sub.usage?.find((u) => u.action === "vacancy_import");
        if (item) {
          setUsage({
            used: item.used,
            limit: item.limit,
            windowSeconds: item.window_seconds ?? null,
          });
        }
      })
      .catch(() => {});
  }, [token, refreshKey]);

  const limit = usage?.limit ?? 3;
  const used = usage?.used ?? 0;
  const remaining = Math.max(0, limit - used);
  const windowHours = usage?.windowSeconds
    ? Math.round(usage.windowSeconds / 3600)
    : 1;

  return (
    <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
      <div className="flex items-start gap-3">
        <span className="text-xl">🧪</span>
        <div className="text-sm text-amber-900">
          <p className="font-semibold mb-1">Демо-режим</p>
          <p>
            Сервис работает в демонстрационном режиме. Импорт вакансий ограничен:
            {limit !== null ? (
              <>
                {" "}
                осталось <strong>{remaining}</strong> из {limit} в течение{" "}
                {windowHours} ч. По истечении окна лимит обновится.
              </>
            ) : (
              " без ограничений (платный план)."
            )}
          </p>
        </div>
      </div>
    </div>
  );
}