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
  // #1 UX «а что дальше?»: профиль кандидата, чтобы после анализа вакансии
  // подсказать загрузить резюме для точной fit-оценки, если его ещё нет.
  // resume_import есть только для file_kind=resume — его отсутствие = профиль
  // создан из GitHub/вручную без резюме.
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    if (token && id) {
      api.getVacancy(token, id).then(setVacancy).catch(() => {});
      api.getVacancyAnalysis(token, id)
        .then((res: any) => {
          setAnalysis(res);
          if (res?.analysis_id) sessionDocs.setSessionDoc(id, "analysisId", res.analysis_id);
        })
        .catch(() => {});
      api.getProfile(token).then(setProfile).catch(() => {});

      // Persist: восстанавливаем ранее сгенерированные резюме/письмо по их
      // ID из SessionDocumentsContext (localStorage). Без этого юзер, уйдя
      // со страницы и вернувшись (или не нажав «Отклик» сразу), терял
      // документы — state сбрасывался, генерировать приходилось заново.
      const sess = sessionDocs.getSession(id);
      if (sess?.resumeId) {
        api.getDocument(token, sess.resumeId).then((res: any) => setResume(res)).catch(() => {});
      }
      if (sess?.coverLetterId) {
        api.getDocument(token, sess.coverLetterId).then((res: any) => setCoverLetter(res)).catch(() => {});
      }
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
    return <div className="text-[color:var(--brand-teal-60)]">Загрузка...</div>;
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => router.back()} className="text-[color:var(--brand-teal-60)] hover:text-[color:var(--brand-teal)]">
          &larr; Назад
        </button>
        <h1 className="text-2xl font-bold">{vacancy.title}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Vacancy description */}
          <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
            <h2 className="font-semibold mb-3">Описание</h2>
            <div className="text-sm text-[color:var(--brand-teal)] whitespace-pre-wrap max-h-64 overflow-y-auto">
              {vacancy.description_raw}
            </div>
          </div>

          {/* Analysis */}
          {analysis && (
            <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
              <h2 className="font-semibold mb-3">Анализ</h2>
              <div className="text-3xl font-bold text-[color:var(--brand-teal)] mb-3">
                {analysis.match_score ?? "-"}%
              </div>

              {/* Bug#73: бэк записывает warning в match_logic, если description_raw
                  короче 200 символов. Без этого баннера юзер видел "Анализ готов",
                  match_score=0 и не понимал, что вакансия слишком короткая. */}
              {analysis.match_logic?.warning === "short_description" && (
                <div className="mb-4 p-3 bg-[color:var(--brand-lime-soft)] border border-amber-200 rounded-lg text-sm text-[color:var(--brand-teal)]">
                  <div className="font-medium mb-1">⚠ {analysis.match_logic.message}</div>
                  <div className="text-xs text-[color:var(--brand-teal)]">
                    Перейдите на страницу «Вакансии» и вставьте полный текст вручную —
                    анализ станет содержательным.
                  </div>
                </div>
              )}

              {analysis.must_have?.length > 0 && (
                <div className="mb-3">
                  <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Требования</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.must_have.slice(0, 5).map((r: any, i: number) => (
                      <li key={i} className="text-[color:var(--brand-teal-60)]">• {r.text || r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.gaps?.length > 0 && (
                <div className="mb-3">
                  <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Пробелы</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.gaps.slice(0, 3).map((g: any, i: number) => (
                      <li key={i} className="text-[color:var(--brand-teal)]">⚠ {g.keyword || g}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.strengths?.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-[color:var(--brand-teal)] mb-1">Сильные стороны</h3>
                  <ul className="text-sm space-y-1">
                    {analysis.strengths.slice(0, 5).map((s: any, i: number) => (
                      <li key={i} className="text-[color:var(--brand-teal)]">✓ {s.keyword || s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* #1 UX «а что дальше?»: анализ готов, но резюме не загружено —
              fit-оценка и генерация документов будут слабыми без резюме.
              Подсказываем загрузить резюме (profile.resume_import отсутствует
              для file_kind=resume → профиль GitHub-only/ручной). */}
          {analysis && profile && !profile.resume_import && (
            <div className="bg-[color:var(--brand-lime-soft)] border border-[color:var(--brand-lime)] rounded-xl p-5">
              <h3 className="font-semibold text-[color:var(--brand-teal)] mb-1">
                Что дальше?
              </h3>
              <p className="text-sm text-[color:var(--brand-teal)] mb-3">
                Для точной fit-оценки и сильного сопроводительного письма
                загрузите резюме — анализ сравнит ваши навыки с требованиями
                вакансии.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => router.push("/profile")}
                  className="px-4 py-2 bg-[color:var(--brand-teal)] text-white rounded-lg text-sm font-medium hover:opacity-90"
                >
                  Загрузить резюме в профиле
                </button>
                <button
                  onClick={handleGenerateLetter}
                  disabled={generating}
                  className="px-4 py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm font-medium text-[color:var(--brand-teal)] hover:bg-[color:var(--brand-cream-soft)] disabled:opacity-50"
                >
                  {generating ? "Генерация..." : "Сгенерировать письмо"}
                </button>
              </div>
            </div>
          )}

          {/* Fit-анализ (детерминированный) */}
          {token && id && (
            <VacancyFitBlock token={token} vacancyId={id} analysisId={analysis?.analysis_id} />
          )}

          {/* Generated Resume */}
          {resume && (
            <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
              <h2 className="font-semibold mb-3">Резюме</h2>
              <pre className="text-sm text-[color:var(--brand-teal)] whitespace-pre-wrap bg-[color:var(--brand-cream-soft)] p-4 rounded max-h-96 overflow-y-auto">
                {resume.rendered_text || JSON.stringify(resume.content_json, null, 2)}
              </pre>
            </div>
          )}

          {/* Generated Cover Letter */}
          {coverLetter && (
            <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
              <h2 className="font-semibold mb-3">Сопроводительное письмо</h2>
              <pre className="text-sm text-[color:var(--brand-teal)] whitespace-pre-wrap bg-[color:var(--brand-cream-soft)] p-4 rounded max-h-96 overflow-y-auto">
                {coverLetter.rendered_text || "Письмо сгенерировано"}
              </pre>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
            <h2 className="font-semibold mb-3">Детали</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-[color:var(--brand-teal-60)]">Компания</dt>
                <dd className="font-medium">{vacancy.company || "-"}</dd>
              </div>
              <div>
                <dt className="text-[color:var(--brand-teal-60)]">Локация</dt>
                <dd className="font-medium">{vacancy.location || "-"}</dd>
              </div>
              <div>
                <dt className="text-[color:var(--brand-teal-60)]">Зарплата</dt>
                <dd className="font-medium">
                  {vacancy.salary_from || vacancy.salary_to
                    ? `${vacancy.salary_from || "?"} - ${vacancy.salary_to || "?"}${vacancy.salary_currency ? " " + vacancy.salary_currency : ""}`
                    : "-"}
                </dd>
              </div>
              <div>
                <dt className="text-[color:var(--brand-teal-60)]">Занятость</dt>
                <dd className="font-medium">{vacancy.employment_type || "-"}</dd>
              </div>
              <div>
                <dt className="text-[color:var(--brand-teal-60)]">Опыт</dt>
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
                className="w-full py-3 bg-[color:var(--brand-teal)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
              >
                {analyzing ? "Анализ..." : "1. Анализировать вакансию"}
              </button>
            ) : (
              <>
                {!resume ? (
                  <button
                    onClick={handleGenerateResume}
                    disabled={generating}
                    className="w-full py-3 bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded-lg hover:bg-[#b8e85c] disabled:opacity-50 font-medium"
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
                          className="w-full px-3 py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm"
                        >
                          <option value="standard">Стандартное письмо</option>
                          <option value="short">Короткое письмо</option>
                          <option value="career_switch">Карьерный переход</option>
                        </select>
                        <button
                          onClick={handleGenerateLetter}
                          disabled={generating}
                          className="w-full py-3 bg-[color:var(--brand-teal)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
                        >
                          {generating ? "Генерация..." : "3. Сгенерировать письмо"}
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleCreateApplication}
                        className="w-full py-3 bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded-lg hover:bg-[#b8e85c] font-medium"
                      >
                        4. Создать отклик
                      </button>
                    )}
                  </>
                )}
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="w-full py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm hover:bg-[color:var(--brand-cream-soft)]"
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
