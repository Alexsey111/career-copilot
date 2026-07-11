"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function ProfilePage() {
  const { token } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<any>(null);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);

  useEffect(() => {
    if (token) {
      console.log("DEBUG: useEffect - loading profile with token");
      api.getProfile(token).then((data) => {
        console.log("DEBUG: profile loaded", data);
        setProfile(data);
      }).catch((err) => {
        console.error("DEBUG: getProfile failed", err.message);
      });
    } else {
      console.log("DEBUG: useEffect - no token");
    }
  }, [token]);

  const handleUploadResume = async () => {
    if (!resumeText.trim() || !token) {
      console.log("DEBUG: no text or token");
      return;
    }
    setUploading(true);
    try {
      console.log("DEBUG: step1 - import");
      const importResult: any = await api.importResume(token, resumeText);
      console.log("DEBUG: step1 done", importResult?.extraction_id);
      
      if (importResult?.extraction_id) {
        console.log("DEBUG: step2 - extract");
        const extractResult: any = await api.extractStructured(token, importResult.extraction_id);
        console.log("DEBUG: step2 done", extractResult?.full_name);
      }
      
      console.log("DEBUG: step3 - getProfile");
      const updated: any = await api.getProfile(token);
      console.log("DEBUG: step3 done", updated?.structured_profile?.full_name);
      setProfile(updated);
      setResumeText("");
      console.log("DEBUG: all done");
    } catch (err: any) {
      console.error("DEBUG: FAILED", err.message);
      alert("Ошибка: " + err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleExtractAchievements = async () => {
    if (!token) return;
    const extractionId = profile?.structured_profile?.extraction_id;
    if (!extractionId) {
      alert("Сначала загрузите резюме");
      return;
    }
    setExtracting(true);
    try {
      await api.extractAchievements(token, extractionId);
      const updated = await api.getProfile(token);
      setProfile(updated);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setExtracting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setUploading(true);
    try {
      const uploadResult = await api.uploadFile(token, file, "resume") as any;
      if (uploadResult?.id) {
        await api.extractResume(token, uploadResult.id);
      }
      const updated = await api.getProfile(token);
      setProfile(updated);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
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
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={handleFileUpload}
            className="hidden"
          />
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
              <h3 className="text-sm font-medium text-gray-700 mb-2">Достижения</h3>
              <ul className="space-y-1">
                {profile.achievements.achievements.map((a: any, i: number) => (
                  <li key={i} className="text-sm text-green-700">• {a.title}</li>
                ))}
              </ul>
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
          Загрузите резюме, чтобы начать.
        </div>
      )}
    </div>
  );
}
