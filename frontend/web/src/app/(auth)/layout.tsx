"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { ToastProvider } from "@/contexts/ToastContext";
import { SessionDocumentsProvider } from "@/contexts/SessionDocumentsContext";
import { Toaster } from "@/components/ui/sonner";
import Sidebar from "@/components/Sidebar";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Загрузка...</div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <ToastProvider>
      <SessionDocumentsProvider>
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
        {/* Один глобальный Toaster для всех toast'ов в (auth)-зоне */}
        <Toaster />
      </SessionDocumentsProvider>
    </ToastProvider>
  );
}
