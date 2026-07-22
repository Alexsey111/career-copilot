"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import type { InterviewPrepSessionListItem } from "@/lib/types";

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
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Подготовка к интервью</h1>

      {/* Создание */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Новая сессия</h2>
        <p className="text-xs text-gray-500 mb-2">
          Выберите отклик со статусом «Отправлено»/«Скрининг»/«Интервью» — для него станет доступна подготовка.
        </p>
        <div className="flex gap-2">
          <select
            value={selectedApp}
            onChange={(e) => setSelectedApp(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value="">— выберите отклик —</option>
            {applications.map((a) => (
              <option key={a.id} value={a.id}>
                {a.vacancy?.title ?? "Вакансия"} · {a.vacancy?.company ?? ""} · {a.status}
              </option>
            ))}
          </select>
          <button
            onClick={handleCreate}
            disabled={creating || !selectedApp}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {creating ? "Создание…" : "Создать сессию"}
          </button>
        </div>
      </div>

      {/* Список сессий */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="font-semibold mb-3">Существующие сессии</h2>
        {loading ? (
          <p className="text-gray-500 text-sm">Загрузка…</p>
        ) : sessions.length > 0 ? (
          <div className="space-y-2">
            {sessions.map((s) => (
              <Link
                key={s.id}
                href={`/interview/${s.id}`}
                className="flex items-center justify-between bg-gray-50 rounded-lg p-3 hover:shadow-sm"
              >
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    Сессия {s.id.slice(0, 8)}… · отклик {s.application_id?.slice(0, 8) ?? "—"}
                  </p>
                  <p className="text-xs text-gray-500">{s.prep_status ?? "—"} · {s.created_at ? new Date(s.created_at).toLocaleDateString("ru") : ""}</p>
                </div>
                {s.readiness_score != null && (
                  <span className="text-sm font-bold text-blue-600">{s.readiness_score}</span>
                )}
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Сессий пока нет.</p>
        )}
      </div>
    </div>
  );
}