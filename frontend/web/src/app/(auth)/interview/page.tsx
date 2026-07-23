"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import type { InterviewPrepSessionListItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Mic } from "lucide-react";
import EmptyState from "@/components/EmptyState";

export default function InterviewPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [sessions, setSessions] = useState<InterviewPrepSessionListItem[]>([]);
  const [applications, setApplications] = useState<any[]>([]);
  const [selectedApp, setSelectedApp] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    Promise.allSettled([
      api.listInterviewPrepSessions(token).then((r) => r as InterviewPrepSessionListItem[]),
      api.listApplications(token).then((r) => r as any[]),
    ]).then(([s, a]) => {
      if (s.status === "fulfilled") setSessions(s.value ?? []);
      if (a.status === "fulfilled") setApplications(a.value ?? []);
      setLoading(false);
    });
  }, [token]);

  const handleCreate = async () => {
    if (!token || !selectedApp) return;
    setCreating(true);
    try {
      const res = (await api.createInterviewPrep(token, selectedApp)) as any;
      toast.success("Сессия подготовки создана");
      window.location.href = `/interview/${res.id}`;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось создать сессию");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Подготовка к интервью</h1>

      <Card>
        <CardHeader>
          <CardTitle>Новая сессия</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground mb-2">
            Выберите отклик со статусом «Отправлено»/«Скрининг»/«Интервью» — для него станет доступна подготовка.
          </p>
          <div className="flex gap-2">
            <select
              value={selectedApp}
              onChange={(e) => setSelectedApp(e.target.value)}
              className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            >
              <option value="">— выберите отклик —</option>
              {applications.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.vacancy?.title ?? "Вакансия"} · {a.vacancy?.company ?? ""} · {a.status}
                </option>
              ))}
            </select>
            <Button
              onClick={handleCreate}
              disabled={creating || !selectedApp}
            >
              {creating ? "Создание…" : "Создать сессию"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Существующие сессии</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-12" />
          ) : sessions.length > 0 ? (
            <div className="space-y-2">
              {sessions.map((s) => (
                <Link
                  key={s.id}
                  href={`/interview/${s.id}`}
                  className="flex items-center justify-between bg-muted rounded-lg p-3 hover:shadow-sm"
                >
                  <div>
                    <p className="text-sm font-medium">
                      Сессия {s.id.slice(0, 8)}… · отклик {s.application_id?.slice(0, 8) ?? "—"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {s.prep_status ?? "—"} · {s.created_at ? new Date(s.created_at).toLocaleDateString("ru") : ""}
                    </p>
                  </div>
                  {s.readiness_score != null && (
                    <span className="text-sm font-bold text-blue-600">{s.readiness_score}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Mic}
              title="Сессий пока нет"
              description="Подготовьтесь к интервью: выберите вакансию и начните сессию."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
