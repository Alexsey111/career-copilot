"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { ToastProvider } from "@/contexts/ToastContext";
import { SessionDocumentsProvider } from "@/contexts/SessionDocumentsContext";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import AppSidebar from "@/components/Sidebar";
import { api } from "@/lib/api";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentOk, setConsentOk] = useState(false);

  // Гард: новый пользователь без обязательных согласий (data_processing)
  // отправляется на /onboarding/consent ДО любых действий с приложением.
  // Если согласие уже было выдано ранее (granted=true) или явно отозвано
  // (revoked_at != null) — пропускаем. Бэк сам гейтит API через 403.
  useEffect(() => {
    if (isLoading || !user) return;
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    let cancelled = false;
    api
      .listConsents(token)
      .then((data) => {
        if (cancelled) return;
        const list = (data ?? []) as Array<{
          consent_type: string;
          granted: boolean;
          revoked_at: string | null;
        }>;
        const dp = list.find((c) => c.consent_type === "data_processing");
        // "Свежий" пользователь: ни разу не выдавал и ни разу не отзывал.
        const isFresh = !dp || (!dp.granted && !dp.revoked_at);
        setConsentOk(!isFresh);
        setConsentChecked(true);
        if (isFresh) {
          router.replace("/onboarding/consent");
        }
      })
      .catch(() => {
        // Не блокируем UI на ошибке consents — бэк сам вернёт 403.
        if (!cancelled) setConsentChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [user, isLoading, router]);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading || !consentChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Загрузка...</div>
      </div>
    );
  }

  if (!user) return null;

  // Ждём редиректа на /onboarding/consent — не рендерим (auth) до этого.
  if (!consentOk) return null;

  return (
    <ToastProvider>
      <SessionDocumentsProvider>
        <TooltipProvider>
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
              {/* Это НЕ landmark-banner (как в layout — он идёт в <main>,
                  что нарушает landmark-banner-is-top-level). Просто
                  контейнер-«шапка» с триггером sidebar и логотипом. */}
              <div
                aria-label="Шапка приложения"
                className="flex h-14 items-center gap-2 border-b px-4"
              >
                <SidebarTrigger />
                {/* Bug#36: добавили логотип в шапку. Раньше здесь был только
                    текст «AI Career Copilot» — пользователь жаловался, что
                    «логотипа в шапке нет». Теперь header консистентен с
                    Sidebar и login-страницей. */}
                <img src="/logo.svg" alt="" className="size-6" aria-hidden="true" />
                <span className="text-sm font-semibold text-foreground">
                  AI Career Copilot
                </span>
              </div>
              <div className="flex-1 p-6">{children}</div>
            </SidebarInset>
          </SidebarProvider>
        </TooltipProvider>
        {/* Один глобальный Toaster для всех toast'ов в (auth)-зоне */}
        <Toaster />
      </SessionDocumentsProvider>
    </ToastProvider>
  );
}
