"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function InterviewPage() {
  const { token } = useAuth();
  const [applicationId, setApplicationId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleCreateSession = async () => {
    if (!applicationId.trim() || !token) return;
    setLoading(true);
    try {
      const res = await api.createInterviewPrep(token, applicationId) as any;
      setSession(res);
      setSessionId(res.id);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSession = async () => {
    if (!sessionId.trim() || !token) return;
    setLoading(true);
    try {
      const res = await api.getInterviewPrep(token, sessionId) as any;
      setSession(res);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Подготовка к интервью</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Новая сессия</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            placeholder="ID отклика"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleCreateSession}
            disabled={loading || !applicationId.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Создание..." : "Создать сессию"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Загрузить существующую сессию</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="ID сессии"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleLoadSession}
            disabled={loading || !sessionId.trim()}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50"
          >
            Загрузить
          </button>
        </div>
      </div>

      {session && (
        <div className="space-y-4">
          {/* Readiness Score */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="text-4xl font-bold text-blue-600">
                {session.readiness_score ?? "-"}
              </div>
              <div>
                <div className="font-semibold">Готовность к интервью</div>
                <div className="text-sm text-gray-500">
                  {session.prep_status}
                </div>
              </div>
            </div>

            {session.readiness?.blockers?.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-medium text-red-700 mb-2">
                  Блокеры
                </h3>
                <ul className="space-y-1">
                  {session.readiness.blockers.map((b: string, i: number) => (
                    <li key={i} className="text-sm text-red-600">
                      • {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {session.readiness?.warnings?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-yellow-700 mb-2">
                  Предупреждения
                </h3>
                <ul className="space-y-1">
                  {session.readiness.warnings.map((w: string, i: number) => (
                    <li key={i} className="text-sm text-yellow-600">
                      • {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Questions */}
          {session.questions?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="font-semibold mb-3">
                Ожидаемые вопросы ({session.questions.length})
              </h2>
              <div className="space-y-3">
                {session.questions.map((q: any, i: number) => (
                  <div
                    key={q.question_id || i}
                    className="p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        {q.category}
                      </span>
                      {q.requires_career_answer && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">
                          требует осторожности
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-800">{q.prompt}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Формат ответа: {q.answer_format}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Weak Areas */}
          {session.weak_areas?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="font-semibold mb-3">Слабые места</h2>
              <div className="space-y-2">
                {session.weak_areas.map((w: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm"
                  >
                    <span
                      className={`inline-block w-2 h-2 rounded-full mt-1.5 ${
                        w.severity === "high"
                          ? "bg-red-500"
                          : w.severity === "medium"
                          ? "bg-yellow-500"
                          : "bg-gray-400"
                      }`}
                    />
                    <div>
                      <span className="font-medium">{w.code}</span>: {w.message}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!session && (
        <div className="text-center text-gray-500 py-8">
          Создайте сессию подготовки к интервью по отклику.
        </div>
      )}
    </div>
  );
}
