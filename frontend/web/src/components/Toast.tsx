"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastType = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

export interface ToastApi {
  toasts: ToastItem[];
  show: (message: string, type?: ToastType) => void;
  dismiss: (id: number) => void;
}

const AUTO_DISMISS_MS = 4000;

/**
 * Лёгкий toast-хук: уведомление держится AUTO_DISMISS_MS (4 сек — в диапазоне
 * 3-5 сек, как просил пользователь, чтобы успеть прочитать), затем исчезает.
 * Возвращает toasts + методы show/dismiss. Не требует провайдера — вставляется
 * локально на страницу рядом с <ToastContainer />.
 */
export function useToast(): ToastApi {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (message: string, type: ToastType = "info") => {
      seq.current += 1;
      const id = seq.current;
      setToasts((prev) => [...prev, { id, message, type }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss]
  );

  return { toasts, show, dismiss };
}

const STYLES: Record<ToastType, { bg: string; border: string; text: string }> = {
  success: { bg: "bg-green-50", border: "border-green-500", text: "text-green-800" },
  error: { bg: "bg-red-50", border: "border-red-500", text: "text-red-800" },
  info: { bg: "bg-blue-50", border: "border-blue-500", text: "text-blue-800" },
};

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    // guarantees hook usage so this file stays a client component
  }, []);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => {
        const s = STYLES[t.type];
        return (
          <div
            key={t.id}
            role="alert"
            className={`flex items-start justify-between gap-3 px-4 py-3 rounded-lg border-l-4 shadow-md ${s.bg} ${s.border} ${s.text}`}
          >
            <span className="text-sm font-medium">{t.message}</span>
            <button
              type="button"
              onClick={() => onDismiss(t.id)}
              className="text-current opacity-60 hover:opacity-100 text-lg leading-none"
              aria-label="Закрыть уведомление"
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}