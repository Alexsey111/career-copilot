"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Briefcase, User, Send, TrendingUp, CheckCircle2, XCircle, Clock, Activity } from "lucide-react";

export default function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    if (token) {
      api.getApplicationAnalytics(token).then(setStats).catch(() => {});
    }
  }, [token]);

  // Тёмно-teal + лаймовый accent (#81). Карточки белые, фон страницы — кремовый.
  const cardStyle = {
    backgroundColor: "white",
    borderColor: "var(--brand-teal-20)",
  } as const;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1
          className="text-3xl font-bold tracking-tight"
          style={{ color: "var(--brand-teal)" }}
        >
          Добро пожаловать!
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-teal-60)" }}>
          С чего хотите начать сегодня?
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/vacancies"
          className="p-6 rounded-xl shadow-sm border hover:shadow-md transition-all"
          style={cardStyle}
        >
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg mb-3"
            style={{ backgroundColor: "var(--brand-lime)", color: "var(--brand-teal)" }}
          >
            <Briefcase className="size-5" />
          </div>
          <h3 className="font-semibold" style={{ color: "var(--brand-teal)" }}>
            Найти вакансию
          </h3>
          <p className="text-sm mt-1" style={{ color: "var(--brand-teal-60)" }}>
            Импорт, поиск, анализ требований
          </p>
        </Link>

        <Link
          href="/profile"
          className="p-6 rounded-xl shadow-sm border hover:shadow-md transition-all"
          style={cardStyle}
        >
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg mb-3"
            style={{ backgroundColor: "var(--brand-teal)", color: "var(--brand-lime)" }}
          >
            <User className="size-5" />
          </div>
          <h3 className="font-semibold" style={{ color: "var(--brand-teal)" }}>
            Заполнить профиль
          </h3>
          <p className="text-sm mt-1" style={{ color: "var(--brand-teal-60)" }}>
            Резюме, достижения, навыки
          </p>
        </Link>

        <Link
          href="/applications"
          className="p-6 rounded-xl shadow-sm border hover:shadow-md transition-all"
          style={cardStyle}
        >
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg mb-3"
            style={{
              background: "linear-gradient(135deg, var(--brand-lime) 0%, var(--brand-teal) 100%)",
              color: "var(--brand-lime)",
            }}
          >
            <Send className="size-5" />
          </div>
          <h3 className="font-semibold" style={{ color: "var(--brand-teal)" }}>
            Мои отклики
          </h3>
          <p className="text-sm mt-1" style={{ color: "var(--brand-teal-60)" }}>
            История и аналитика
          </p>
        </Link>
      </div>

      {stats && (
        <div
          className="rounded-xl shadow-sm border p-6"
          style={cardStyle}
        >
          <div className="flex items-center gap-2 mb-4">
            <Activity className="size-4" style={{ color: "var(--brand-teal)" }} />
            <h2 className="text-lg font-semibold" style={{ color: "var(--brand-teal)" }}>
              Аналитика поиска
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div
                className="text-2xl font-bold"
                style={{ color: "var(--brand-teal)" }}
              >
                {stats.total_applications || 0}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-teal-60)" }}>
                Всего откликов
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-2xl font-bold flex items-center justify-center gap-1"
                style={{ color: "var(--brand-teal)" }}
              >
                <CheckCircle2 className="size-4" style={{ color: "var(--brand-lime)" }} />
                {stats.offers_count || 0}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-teal-60)" }}>
                Офферов
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-2xl font-bold flex items-center justify-center gap-1"
                style={{ color: "var(--brand-teal)" }}
              >
                <XCircle className="size-4" style={{ color: "var(--brand-ink)" }} />
                {stats.rejections_count || 0}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-teal-60)" }}>
                Отказов
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-2xl font-bold flex items-center justify-center gap-1"
                style={{ color: "var(--brand-teal)" }}
              >
                <Clock className="size-4" style={{ color: "var(--brand-teal-60)" }} />
                {stats.average_time_to_apply_hours
                  ? `${Math.round(stats.average_time_to_apply_hours)}h`
                  : "—"}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-teal-60)" }}>
                Ср. время отклика
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
