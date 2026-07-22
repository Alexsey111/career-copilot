"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { runAiAction } from "@/lib/ai-action";
import AchievementReviewCard from "@/components/AchievementReviewCard";

export default function ProfilePage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [profile, setProfile] = useState<any>(null);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);

  // Intake-формы
  const [githubUrl, setGithubUrl] = useState("");
  const [githubRole, setGithubRole] = useState("");
  const [repoCount, setRepoCount] = useState(12);
  const [intaking, setIntaking] = useState(false);
  // Ручной intake (упрощённый): headline, location, technologies
  const [manualHeadline, setManualHeadline] = useState("");
  const [manualLocation, setManualLocation] = useState("");
  const [manualTech, setManualTech] = useState("");

  const reloadProfile = () => {
    if (!token) return;
    api.getProfile(token).then(setProfile).catch(() => {});
  };

  useEffect(() => {
    if (token) {
      api.getProfile(token).then(setProfile).catch((err) => {
        console.error("getProfile failed", err.message);
      });
    }
  }, [token]);

  const handleUploadResume = async () => {
    if (!resumeText.trim() || !token) return;
    setUploading(true);
    try {
      const importResult: any = await api.importResume(token, resumeText);
      if (importResult?.extraction_id) {
        await api.extractStructured(token, importResult.extraction_id);
      }
      reloadProfile();
      setResumeText("");
      toast.success("Резюме загружено");
    } catch (err: any) {
      toast.error("Ошибка загрузки: " + (err?.message || "неизвестная"));
    } finally {
      setUploading(false);
    }
  };

  const handleExtractAchievements = async () => {
    if (!token) return;
    const extractionId = profile?.structured_profile?.extraction_id;
    if (!extractionId) {
      toast.error("Сначала загрузите резюме");
      return;
    }
    setExtracting(true);
    try {
      const result: any = await api.extractAchievements(token, extractionId);
      const count = result?.achievement_count ?? result?.achievements?.length ?? 0;
      reloadProfile();
      if (count > 0) toast.success(`Извлечено достижений: ${count}`);
      else toast.info("Достижения не найдены");
    } catch (err: any) {
      toast.error("Ошибка извлечения: " + (err?.message || "неизвестная"));
    } finally {
      setExtracting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setUploading(true);
    try {
      const uploadResult = (await api.uploadFile(token, file, "resume")) as any;
      let extractionId: string | undefined = uploadResult?.id;
      if (uploadResult?.id) {
        const importResult: any = await api.extractResume(token, uploadResult.id);
        extractionId = importResult?.extraction_id ?? extractionId;
      }
      if (extractionId) {
        await api.extractStructured(token, extractionId);
      }
      reloadProfile();
      toast.success("Резюме загружено");
    } catch (err: any) {
      toast.error("Ошибка загрузки: " + (err?.message || "неизвестная"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleGithubIntake = async () => {
    if (!token || !githubUrl.trim()) return;
    setIntaking(true);
    const result = await runAiAction(toast, "Импорт GitHub-профиля", () =>
      api.intakeGithubPublic(token, {
        github_url: githubUrl.trim(),
        target_role: githubRole.trim() || undefined,
        repository_count: repoCount,
        include_readme_snippets: true,
      })
    );
    setIntaking(false);
    if (result) {
      toast.success(
        `GitHub импортирован: ${(result as any).project_count ?? 0} проектов, ${(result as any).evidence_snippet_count ?? 0} доказательств`
      );
      setGithubUrl("");
      reloadProfile();
    }
  };

  const handleManualIntake = async () => {
    if (!token) return;
    if (!manualHeadline.trim()) {
      toast.error("Укажите целевую роль");
      return;
    }
    setIntaking(true);
    const result = await runAiAction(toast, "Ручное создание профиля", () =>
      api.intakeManual(token, {
        headline: manualHeadline.trim(),
        location: manualLocation.trim() || undefined,
        technologies: manualTech
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      })
    );
    setIntaking(false);
    if (result) {
      toast.success("Профиль создан вручную");
      setManualHeadline("");
      setManualLocation("");
      setManualTech("");
      reloadProfile();
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Профиль кандидата</h1>

      {/* Upload Resume */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Загрузить резюме</h2>
        <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors mb-4">
          <div className="flex flex-col items-center justify-center pt-5 pb-6">
            <svg className="w-8 h-8 mb-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-gray-500">
              <span className="font-semibold">Нажмите для выбора</span> или перетащите файл
            </p>
            <p className="text-xs text-gray-400">PDF, DOCX, TXT</p>
          </div>
          <input type="file" accept=".pdf,.docx,.txt" onChange={handleFileUpload} className="hidden" />
        </label>
        <div className="text-xs text-gray-500">или вставьте текст:</div>
        <textarea
          value={resumeText}
          onChange={(e) => setResumeText(e.target.value)}
          placeholder="Вставьте текст резюме..."
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent h-32 text-sm"
        />
        <button
          onClick={handleUploadResume}
          disabled={uploading || !resumeText.trim()}
          className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {uploading ? "Загрузка..." : "Импортировать текст"}
        </button>
      </div>

      {/* Альтернативные источники профиля */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Альтернативные источники</h2>
        <p className="text-xs text-gray-500 mb-3">
          Можно создать профиль без файла резюме — вручную или импортом публичного GitHub-профиля.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2 border border-gray-200 rounded-lg p-3">
            <h3 className="text-sm font-medium">Ручное создание</h3>
            <input
              value={manualHeadline}
              onChange={(e) => setManualHeadline(e.target.value)}
              placeholder="Целевая роль *"
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <input
              value={manualLocation}
              onChange={(e) => setManualLocation(e.target.value)}
              placeholder="Локация"
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <input
              value={manualTech}
              onChange={(e) => setManualTech(e.target.value)}
              placeholder="Технологии через запятую"
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <button
              onClick={handleManualIntake}
              disabled={intaking}
              className="px-3 py-1 text-sm bg-gray-700 text-white rounded hover:bg-gray-800 disabled:opacity-50"
            >
              {intaking ? "Создание…" : "Создать профиль"}
            </button>
          </div>

          <div className="space-y-2 border border-gray-200 rounded-lg p-3">
            <h3 className="text-sm font-medium">Импорт GitHub (public)</h3>
            <input
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/username"
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <input
              value={githubRole}
              onChange={(e) => setGithubRole(e.target.value)}
              placeholder="Целевая роль (необязательно)"
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <label className="text-xs text-gray-500 flex items-center gap-2">
              Репозиториев: {repoCount}
              <input
                type="range"
                min={1}
                max={30}
                value={repoCount}
                onChange={(e) => setRepoCount(Number(e.target.value))}
              />
            </label>
            <button
              onClick={handleGithubIntake}
              disabled={intaking || !githubUrl.trim()}
              className="px-3 py-1 text-sm bg-gray-700 text-white rounded hover:bg-gray-800 disabled:opacity-50"
            >
              {intaking ? "Импорт…" : "Импортировать GitHub"}
            </button>
          </div>
        </div>
      </div>

      {/* Profile State */}
      {profile && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Текущий профиль</h2>
            <button
              onClick={handleExtractAchievements}
              disabled={extracting}
              className="px-3 py-1 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {extracting ? "Извлечение..." : "Извлечь достижения"}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Имя:</span>{" "}
              <span className="font-medium">{profile.structured_profile?.full_name || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">Должность:</span>{" "}
              <span className="font-medium">{profile.structured_profile?.headline || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">Статус:</span>{" "}
              <span className="font-medium">{profile.resume_import?.status || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">Локация:</span>{" "}
              <span className="font-medium">{profile.structured_profile?.location || "—"}</span>
            </div>
          </div>

          {profile.structured_profile?.technologies?.length > 0 && (
            <div className="mt-3 text-sm">
              <span className="text-gray-500">Навыки:</span>{" "}
              <span className="font-medium">{profile.structured_profile.technologies.join(", ")}</span>
            </div>
          )}

          {profile.structured_profile?.ai_tools?.length > 0 && (
            <div className="mt-2 text-sm">
              <span className="text-gray-500">AI инструменты:</span>{" "}
              <span className="font-medium">{profile.structured_profile.ai_tools.join(", ")}</span>
            </div>
          )}

          {profile.structured_profile?.automation_tools?.length > 0 && (
            <div className="mt-2 text-sm">
              <span className="text-gray-500">Automation:</span>{" "}
              <span className="font-medium">{profile.structured_profile.automation_tools.join(", ")}</span>
            </div>
          )}

          {profile.structured_profile?.structured_evidence?.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Факты из резюме</h3>
              <div className="space-y-2">
                {profile.structured_profile.structured_evidence.map((e: any, i: number) => (
                  <div key={i} className="p-2 bg-gray-50 rounded text-sm">
                    <span className="font-medium">{e.title}</span>
                    {e.skills?.length > 0 && (
                      <span className="text-gray-500 ml-2">({e.skills.join(", ")})</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {profile.achievements?.achievements?.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Достижения ({profile.achievements.achievements.length})
              </h3>
              <p className="text-xs text-gray-500 mb-2">
                Подтвердите достижения (статус «Подтверждено»), чтобы они попали в адаптированное резюме.
              </p>
              <div className="space-y-3">
                {profile.achievements.achievements.map((a: any) => (
                  <AchievementReviewCard
                    key={a.id}
                    token={token ?? ""}
                    achievement={a}
                    onSaved={reloadProfile}
                  />
                ))}
              </div>
            </div>
          )}

          {profile.structured_profile?.warnings?.length > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 rounded-lg">
              <h3 className="text-sm font-medium text-yellow-800 mb-2">Рекомендации</h3>
              <ul className="space-y-1">
                {profile.structured_profile.warnings.map((w: string, i: number) => (
                  <li key={i} className="text-sm text-yellow-700">• {w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!profile && (
        <div className="text-center text-gray-500 py-8">
          Загрузите резюме или создайте профиль вручную, чтобы начать.
        </div>
      )}
    </div>
  );
}