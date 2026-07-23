"use client";

import { ToastProvider } from "@/contexts/ToastContext";
import { Toaster } from "@/components/ui/sonner";

export default function OnboardingClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Лёгкий layout без sidebar — пользователь ещё не в продукте, навигация
  // по защищённым страницам недоступна, поэтому минимализм.
  // ToastProvider нужен, т.к. onboarding/consent использует useToastCtx.
  return (
    <ToastProvider>
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 p-4">
        {children}
      </div>
      <Toaster />
    </ToastProvider>
  );
}
