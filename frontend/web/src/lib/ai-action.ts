"use client";

import type { ToastContextValue } from "@/contexts/ToastContext";

/**
 * Обёртка для AI-действий (generate/enhance/intake), которые на бэкенде gated
 * на `require_ai_consent` (403) и `require_quota` (402). Перехватывает ошибки,
 * показывает человекочитаемый тост (extractErrorMessage в api.ts уже парсит
 * QuotaErrorDetail) и возвращает null при неудаче — вызывающий код решает,
 * как отреагировать.
 *
 * Возвращает результат действия либо null. Сообщение об ошибке уже показано
 * тостом, дублировать не нужно.
 */
export async function runAiAction<T>(
  toast: ToastContextValue,
  action: string,
  fn: () => Promise<T>
): Promise<T | null> {
  try {
    return await fn();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    if (/consent/i.test(message)) {
      toast.error(`Требуется согласие на AI-обработку: ${message}. Раздел «Согласия».`);
    } else if (/квота|quota|402/i.test(message)) {
      toast.error(message);
    } else {
      toast.error(`${action} не выполнено: ${message}`);
    }
    return null;
  }
}