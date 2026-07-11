"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    if (token) {
      api.getApplicationAnalytics(token).then(setStats).catch(() => {});
    }
  }, [token]);

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Добро пожаловать!</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Link
          href="/vacancies"
          className="p-6 bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="text-2xl mb-2">💼</div>
          <h3 className="font-semibold">Найти вакансию</h3>
          <p className="text-sm text-gray-500 mt-1">
            Импорт, поиск, анализ требований
          </p>
        </Link>

        <Link
          href="/profile"
          className="p-6 bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="text-2xl mb-2">👤</div>
          <h3 className="font-semibold">Заполнить профиль</h3>
          <p className="text-sm text-gray-500 mt-1">
            Резюме, достижения, навыки
          </p>
        </Link>

        <Link
          href="/applications"
          className="p-6 bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="text-2xl mb-2">📋</div>
          <h3 className="font-semibold">Мои отклики</h3>
          <p className="text-sm text-gray-500 mt-1">
            История и аналитика
          </p>
        </Link>
      </div>

      {stats && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Аналитика поиска</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {stats.total_applications || 0}
              </div>
              <div className="text-xs text-gray-500">Всего откликов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {stats.offers_count || 0}
              </div>
              <div className="text-xs text-gray-500">Офферов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {stats.rejections_count || 0}
              </div>
              <div className="text-xs text-gray-500">Отказов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {stats.average_time_to_apply_hours
                  ? `${Math.round(stats.average_time_to_apply_hours)}h`
                  : "-"}
              </div>
              <div className="text-xs text-gray-500">Ср. время отклика</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
