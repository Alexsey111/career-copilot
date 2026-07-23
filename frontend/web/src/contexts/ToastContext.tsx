"use client";

import { createContext, useContext, type ReactNode } from "react";
import { toast as sonnerToast, type ExternalToast } from "sonner";

/**
 * Глобальный toast-провайдер для всей (auth)-зоны.
 *
 * Обёртка над Sonner, сохраняющая старый API (`useToastCtx().show/success/error/info`)
 * — это позволяет 17 файлам работать без изменений. Один `<Toaster/>` смонтирован
 * в `app/(auth)/layout.tsx`, здесь он НЕ рендерится (не дублируется).
 *
 * AUTO_DISMISS_MS = 4000 (3-5 сек, чтобы успеть прочитать) — настраивается в
 * `components/ui/sonner.tsx`.
 */

export type ToastType = "success" | "error" | "info";

export interface ToastContextValue {
  show: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const show = (message: string, type: ToastType = "info") => {
    const opts: ExternalToast = {};
    if (type === "success") sonnerToast.success(message, opts);
    else if (type === "error") sonnerToast.error(message, opts);
    else sonnerToast.info(message, opts);
  };

  const value: ToastContextValue = {
    show,
    success: (m: string) => show(m, "success"),
    error: (m: string) => show(m, "error"),
    info: (m: string) => show(m, "info"),
  };

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToastCtx(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToastCtx must be used within <ToastProvider>");
  }
  return ctx;
}
