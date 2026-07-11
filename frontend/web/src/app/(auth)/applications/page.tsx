"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

interface Application {
  id: string;
  vacancy_id: string;
  status: string;
  outcome: string | null;
  applied_at: string | null;
  created_at: string;
  vacancy?: { title: string; company: string | null };
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

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  applied: "bg-blue-100 text-blue-700",
  screening: "bg-yellow-100 text-yellow-700",
  interview: "bg-purple-100 text-purple-700",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  withdrawn: "bg-gray-100 text-gray-500",
};

export default function ApplicationsPage() {
  const { token } = useAuth();
  const [applications, setApplications] = useState<Application[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    if (token) {
      api.listApplications(token).then((data) => setApplications(data as Application[])).catch(() => {});
      api.getApplicationAnalytics(token).then((data) => setAnalytics(data)).catch(() => {});
    }
  }, [token]);

  const handleStatusChange = async (appId: string, newStatus: string) => {
    if (!token) return;
    try {
      await api.updateApplicationStatus(token, appId, newStatus);
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus } : a))
      );
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Мои отклики</h1>

      {analytics && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold mb-3">Аналитика</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {analytics.total_applications || 0}
              </div>
              <div className="text-xs text-gray-500">Всего</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {analytics.count_by_status?.interview || 0}
              </div>
              <div className="text-xs text-gray-500">Интервью</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {analytics.offers_count || 0}
              </div>
              <div className="text-xs text-gray-500">Офферов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {analytics.rejections_count || 0}
              </div>
              <div className="text-xs text-gray-500">Отказов</div>
            </div>
          </div>

          {analytics.conversion_by_resume_version &&
            Object.keys(analytics.conversion_by_resume_version).length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  Конверсия по версиям резюме
                </h3>
                <div className="space-y-1">
                  {Object.entries(analytics.conversion_by_resume_version).map(
                    ([ver, stats]: [string, any]) => (
                      <div key={ver} className="flex justify-between text-sm">
                        <span className="text-gray-600">{ver}</span>
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
        </div>
      )}

      <div className="space-y-3">
        {applications.map((app) => (
          <div
            key={app.id}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold">
                  {app.vacancy?.title || "Вакансия"}
                </h3>
                <p className="text-sm text-gray-500">
                  {app.vacancy?.company || ""} •{" "}
                  {new Date(app.created_at).toLocaleDateString("ru")}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={app.status}
                  onChange={(e) => handleStatusChange(app.id, e.target.value)}
                  className={`text-sm px-3 py-1 rounded-full border-0 ${
                    STATUS_COLORS[app.status] || "bg-gray-100"
                  }`}
                >
                  {Object.entries(STATUS_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        ))}

        {applications.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            Нет откликов. Начните с поиска вакансий.
          </div>
        )}
      </div>
    </div>
  );
}
