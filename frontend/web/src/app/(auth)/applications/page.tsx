"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Send } from "lucide-react";
import EmptyState from "@/components/EmptyState";

interface Application {
  id: string;
  vacancy_id: string;
  status: string;
  outcome: string | null;
  applied_at: string | null;
  created_at: string;
  vacancy?: { title: string; company: string | null };
}

interface Reminder {
  application_id?: string;
  kind?: string;
  message?: string;
  severity?: string;
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  applied: "Отправлено",
  screening: "Скрининг",
  interview: "Интервью",
  offer: "Оффер",
  rejected: "Отказ",
  withdrawn: "Отозвано",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  applied: "default",
  screening: "secondary",
  interview: "secondary",
  offer: "default",
  rejected: "destructive",
  withdrawn: "outline",
};

export default function ApplicationsPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [applications, setApplications] = useState<Application[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    if (token) {
      api.listApplications(token).then((data) => setApplications(data as Application[])).catch(() => {});
      api.getApplicationAnalytics(token).then((data) => setAnalytics(data)).catch(() => {});
      api.getApplicationReminders(token).then((data) => setReminders(data as Reminder[])).catch(() => {});
    }
  }, [token]);

  const handleStatusChange = async (appId: string, newStatus: string) => {
    if (!token) return;
    try {
      await api.updateApplicationStatus(token, appId, newStatus);
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus } : a))
      );
      toast.success("Статус обновлён");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Мои отклики</h1>

      {reminders.length > 0 && (
        <Card className="mb-6 border-yellow-300 bg-yellow-50">
          <CardHeader>
            <CardTitle className="text-yellow-800">Требует внимания</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {reminders.map((r, i) => (
                <li key={r.application_id ?? i} className="text-sm text-yellow-700">
                  • {r.message ?? r.kind}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {analytics && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Аналитика</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-[color:var(--brand-teal)]">
                  {analytics.total_applications || 0}
                </div>
                <div className="text-xs text-[color:var(--brand-teal-60)]">Всего</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-[color:var(--brand-teal)]">
                  {analytics.count_by_status?.interview || 0}
                </div>
                <div className="text-xs text-[color:var(--brand-teal-60)]">Интервью</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-[color:var(--brand-teal)]">
                  {analytics.offers_count || 0}
                </div>
                <div className="text-xs text-[color:var(--brand-teal-60)]">Офферов</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-[color:var(--brand-ink)]">
                  {analytics.rejections_count || 0}
                </div>
                <div className="text-xs text-[color:var(--brand-teal-60)]">Отказов</div>
              </div>
            </div>

            {analytics.conversion_by_resume_version &&
              Object.keys(analytics.conversion_by_resume_version).length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-medium text-[color:var(--brand-teal-60)] mb-2">
                    Конверсия по версиям резюме
                  </h3>
                  <div className="space-y-1">
                    {Object.entries(analytics.conversion_by_resume_version).map(
                      ([ver, stats]: [string, any]) => (
                        <div key={ver} className="flex justify-between text-sm">
                          <span className="text-[color:var(--brand-teal-60)]">{ver}</span>
                          <span>
                            {stats.total} откликов •{" "}
                            {Math.round((stats.interview_rate || 0) * 100)}% интервью •{" "}
                            {Math.round((stats.offer_rate || 0) * 100)}% оффер
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {applications.map((app) => (
          <Card key={app.id}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <Link href={`/applications/${app.id}`} className="block">
                  <h3 className="font-semibold text-[color:var(--brand-teal)] hover:underline">
                    {app.vacancy?.title || "Вакансия"}
                  </h3>
                  <p className="text-sm text-[color:var(--brand-teal-60)]">
                    {app.vacancy?.company || ""} •{" "}
                    {new Date(app.created_at).toLocaleDateString("ru")}
                  </p>
                </Link>

                <div className="flex items-center gap-2">
                  <select
                    value={app.status}
                    onChange={(e) => handleStatusChange(app.id, e.target.value)}
                    className="text-sm px-3 py-1 rounded-full border bg-background"
                  >
                    {Object.entries(STATUS_LABELS).map(([val, label]) => (
                      <option key={val} value={val}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <Badge variant={STATUS_VARIANTS[app.status] || "secondary"}>
                    {STATUS_LABELS[app.status] || app.status}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {applications.length === 0 && (
          <EmptyState
            icon={Send}
            title="Нет откликов"
            description="Найдите подходящую вакансию и отправьте первое сопроводительное письмо."
            action={{ label: "Перейти к вакансиям →", href: "/vacancies" }}
          />
        )}
      </div>
    </div>
  );
}
