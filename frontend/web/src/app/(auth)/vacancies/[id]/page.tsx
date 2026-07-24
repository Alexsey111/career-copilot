"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { useSessionDocs } from "@/contexts/SessionDocumentsContext";
import { api } from "@/lib/api";
import VacancyFitBlock from "@/components/VacancyFitBlock";

export default function VacancyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const toast = useToastCtx();
  const sessionDocs = useSessionDocs();
  const router = useRouter();
  const [vacancy, setVacancy] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [resume, setResume] = useState<any>(null);
  const [coverLetter, setCoverLetter] = useState<any>(null);
  const [letterVariant, setLetterVariant] = useState("standard");

  useEffect(() => {
    if (token && id) {
      api.getVacancy(token, id).then(setVacancy).catch(() => {});
      api.getVacancyAnalysis(token, id)
        .then((res: any) => {
          setAnalysis(res);
          if (res?.analysis_id) sessionDocs.setSessionDoc(id, "analysisId", res.analysis_id);
        })
        .catch(() => {});
    }
  }, [token, id, sessionDocs]);

  const handleAnalyze = async () => {
    if (!token || !id) return;
    setAnalyzing(true);
    try {
      const res: any = await api.analyzeVacancy(token, id);
      setAnalysis(res);
      if (res?.analysis_id) sessionDocs.setSessionDoc(id, "analysisId", res.analysis_id);
      toast.success("Анализ готов");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerateResume = async () => {
    if (!token || !id) return;
    setGenerating(true);
    try {
      const res = await api.generateResume(token, id) as any;
      setResume(res);
      if (res?.document_id) sessionDocs.setSessionDoc(id, "resumeId", res.document_id);
      toast.success("Резюме сгенерировано");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateLetter = async () => {
    if (!token || !id) return;
    setGenerating(true);
    try {
      const res = await api.generateCoverLetter(token, id, letterVariant) as any;
      setCoverLetter(res);
      if (res?.document_id) sessionDocs.setSessionDoc(id, "coverLetterId", res.document_id);
      toast.success("Письмо сгенерировано");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCreateApplication = async () => {
    if (!token || !id) return;
    try {
      const res = await api.createApplication(token, id, resume?.document_id, coverLetter?.document_id) as any;
      if (res?.id) sessionDocs.setSessionDoc(id, "applicationId", res.id);
      toast.success("Отклик создан. Открыть раздел «Отклики».");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  if (!vacancy) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => router.back()} className="text-gray-500 hover:text-gray-700">
          &larr; Назад
        </button>
        <h1 className="text-2xl font-bold">{vacancy.title}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Vacancy description */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="font-semibold mb-3">Описание</h2>
            <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-y-auto">
              {vacancy.description_raw}
            </div>
          </div>

          {/* Analysis */}
          {analysis && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="font-semibold mb-3">Анализ</h2>
              <div className="text-3xl font-bold text-blue-600 mb-3">
                {analysis.match_score ?? "-"}%
              </div>

              {/* Bug#73: бэк записывает warning в match_logic, если description_raw
                  короче 200 символов. Без этого баннера юзер видел "Анализ готов",
                  match_score=0 и не понимал, что вакансия слишком короткая. */}
              {analysis.match_logic?.warning === "short_description" && (
                <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-900">
                  <div className="font-medium mb-1">⚠ {analysis.match_logic.message}</div>
                  <div className="text-xs text-amber-800">
                    Перейдите на страницу «Вакансии» и вставьте полный текст вручную —
                    анализ станет содержательным.
                  </div>
                </div>
              )}

              {analysis.must_have?.length > 0 && (
                <div className="mb-3">
                  <h3 className="text-sm font-medium text-gray-700 mb-1">Требования</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.must_have.slice(0, 5).map((r: any, i: number) => (
                      <li key={i} className="text-gray-600">• {r.text || r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.gaps?.length > 0 && (
                <div className="mb-3">
                  <h3 className="text-sm font-medium text-orange-700 mb-1">Пробелы</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.gaps.slice(0, 3).map((g: any, i: number) => (
                      <li key={i} className="text-orange-600">⚠ {g.keyword || g}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.strengths?.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-green-700 mb-1">Сильные стороны</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.strengths.slice(0, 5).map((s: any, i: number) => (
                      <li key={i} className="text-green-600">✓ {s.keyword || s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Fit-анализ (детерминированный) */}
          {token && id && (
            <VacancyFitBlock token={token} vacancyId={id} analysisId={analysis?.analysis_id} />
          )}

          {/* Generated Resume */}
          {resume && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="font-semibold mb-3">Резюме</h2>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-4 rounded max-h-96 overflow-y-auto">
                {resume.rendered_text || JSON.stringify(resume.content_json, null, 2)}
              </pre>
            </div>
          )}

          {/* Generated Cover Letter */}
          {coverLetter && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="font-semibold mb-3">Сопроводительное письмо</h2>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-4 rounded max-h-96 overflow-y-auto">
                {coverLetter.rendered_text || "Письмо сгенерировано"}
              </pre>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="font-semibold mb-3">Детали</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-gray-500">Компания</dt>
                <dd className="font-medium">{vacancy.company || "-"}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Локация</dt>
                <dd className="font-medium">{vacancy.location || "-"}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Зарплата</dt>
                <dd className="font-medium">
                  {vacancy.salary_from || vacancy.salary_to
                    ? `${vacancy.salary_from || "?"} - ${vacancy.salary_to || "?"}${vacancy.salary_currency ? " " + vacancy.salary_currency : ""}`
                    : "-"}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Занятость</dt>
                <dd className="font-medium">{vacancy.employment_type || "-"}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Опыт</dt>
                <dd className="font-medium">{vacancy.experience_level || "-"}</dd>
              </div>
            </dl>
          </div>

          {/* Action buttons */}
          <div className="space-y-3">
            {!analysis ? (
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {analyzing ? "Анализ..." : "1. Анализировать вакансию"}
              </button>
            ) : (
              <>
                {!resume ? (
                  <button
                    onClick={handleGenerateResume}
                    disabled={generating}
                    className="w-full py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium"
                  >
                    {generating ? "Генерация..." : "2. Сгенерировать резюме"}
                  </button>
                ) : (
                  <>
                    {!coverLetter ? (
                      <div className="space-y-2">
                        <select
                          value={letterVariant}
                          onChange={(e) => setLetterVariant(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        >
                          <option value="standard">Стандартное письмо</option>
                          <option value="short">Короткое письмо</option>
                          <option value="career_switch">Карьерный переход</option>
                        </select>
                        <button
                          onClick={handleGenerateLetter}
                          disabled={generating}
                          className="w-full py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 font-medium"
                        >
                          {generating ? "Генерация..." : "3. Сгенерировать письмо"}
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleCreateApplication}
                        className="w-full py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-medium"
                      >
                        4. Создать отклик
                      </button>
                    )}
                  </>
                )}
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="w-full py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
                >
                  Обновить анализ
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
