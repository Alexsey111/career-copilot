"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { runAiAction } from "@/lib/ai-action";
import AchievementReviewCard from "@/components/AchievementReviewCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Upload, Sparkles, CheckCircle2, AlertTriangle, User, Target, MapPin, BarChart3 } from "lucide-react";

export default function ProfilePage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const router = useRouter();
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
  // Bug#34: история текстовых импортов (localStorage), чтобы можно было
  // повторно применить ранее загруженное резюме без файла.
  const [resumeHistory, setResumeHistory] = useState<{ text: string; savedAt: number }[]>([]);
  // Backend resume history: список ранее загруженных SourceFile (PDF/DOCX/TXT)
  // + reuse-эндпоинт для повторной активации / reparse.
  const [serverResumes, setServerResumes] = useState<Array<{
    id: string;
    original_name: string;
    mime_type: string | null;
    size_bytes: number | null;
    lifecycle_status: "active" | "superseded";
    created_at: string;
    updated_at: string;
    latest_extraction_id: string | null;
    text_preview: string | null;
    detected_format: string | null;
    is_active: boolean;
    is_reusable: boolean;
  }>>([]);
  const [activeServerResumeId, setActiveServerResumeId] = useState<string | null>(null);
  const [loadingResumes, setLoadingResumes] = useState(false);
  const [reusingId, setReusingId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem("resume_text_history");
      if (!raw) return;
      const list = JSON.parse(raw) as { text: string; savedAt: number }[];
      if (Array.isArray(list)) setResumeHistory(list.slice(0, 5));
    } catch {
      // Не блокируем UI на повреждённом localStorage
    }
  }, []);

  const reloadProfile = () => {
    if (!token) return;
    api.getProfile(token).then(setProfile).catch(() => {});
  };

  const reloadServerResumes = async () => {
    if (!token) return;
    setLoadingResumes(true);
    try {
      const data = await api.listResumes(token);
      setServerResumes(data.items);
      setActiveServerResumeId(data.active_source_file_id);
    } catch (err: any) {
      console.error("listResumes failed", err?.message || err);
    } finally {
      setLoadingResumes(false);
    }
  };

  const handleReuseResume = async (sourceFileId: string, reparse: boolean) => {
    if (!token) return;
    setReusingId(sourceFileId);
    try {
      const result = await api.reuseResume(token, sourceFileId, { reparse });
      if (result.status === "needs_import") {
        toast.error("Файл ещё не был распарсен — загрузите его заново");
        return;
      }
      toast.success(
        reparse
          ? "Резюме перепарсено"
          : "Активировано ранее загруженное резюме",
      );
      reloadProfile();
      reloadServerResumes();
    } catch (err: any) {
      toast.error("Ошибка: " + (err?.message || "неизвестная"));
    } finally {
      setReusingId(null);
    }
  };

  useEffect(() => {
    if (token) {
      api.getProfile(token).then(setProfile).catch((err) => {
        console.error("getProfile failed", err.message);
      });
      reloadServerResumes();
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
      // Bug#34: сохраняем текст в localStorage (последние 5).
      try {
        const raw = localStorage.getItem("resume_text_history");
        const list = raw ? (JSON.parse(raw) as { text: string; savedAt: number }[]) : [];
        const next = [
          { text: resumeText, savedAt: Date.now() },
          ...list.filter((it) => it.text !== resumeText),
        ].slice(0, 5);
        localStorage.setItem("resume_text_history", JSON.stringify(next));
        setResumeHistory(next);
      } catch {
        // localStorage недоступен (приватный режим) — не критично.
      }
      reloadProfile();
      reloadServerResumes();
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
      // Bug#30a: бэк-схема GitHubPublicProfileImportRequest ждёт
      // `profile_url`, не `github_url`. Старый фронт отправлял
      // `github_url` → 422 «Request validation failed» (field required).
      api.intakeGithubPublic(token, {
        profile_url: githubUrl.trim(),
        target_role: githubRole.trim() || undefined,
        // Bug#30a: GitHubPublicProfileImportRequest.max_repositories/include_readme,
        // НЕ repository_count/include_readme_snippets (старые нестандартные
        // имена — pydantic их игнорирует, и парсер падал на defaults).
        max_repositories: repoCount,
        include_readme: true,
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
    <div className="max-w-4xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight" style={{ color: "var(--brand-teal)" }}>
        Профиль кандидата
      </h1>

      {/* Upload Resume */}
      <Card>
        <CardHeader>
          <CardTitle style={{ color: "var(--brand-teal)" }}>Загрузить резюме</CardTitle>
        </CardHeader>
        <CardContent>
          <label
            className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer transition-colors mb-4"
            style={{ borderColor: "var(--brand-teal-20)" }}
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-8 h-8 mb-2" style={{ color: "var(--brand-teal-60)" }} />
              <p className="text-sm" style={{ color: "var(--brand-teal-60)" }}>
                <span className="font-semibold" style={{ color: "var(--brand-teal)" }}>
                  Нажмите для выбора
                </span>{" "}
                или перетащите файл
              </p>
              <p className="text-xs" style={{ color: "var(--brand-teal-60)" }}>
                PDF, DOCX, TXT
              </p>
            </div>
            <input type="file" accept=".pdf,.docx,.txt" onChange={handleFileUpload} className="hidden" />
          </label>
          <p className="text-xs mb-2" style={{ color: "var(--brand-teal-60)" }}>
            или вставьте текст:
          </p>
          <Textarea
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder="Вставьте текст резюме..."
            className="min-h-32"
          />
          <Button
            onClick={handleUploadResume}
            disabled={uploading || !resumeText.trim()}
            className="mt-3"
          >
            {uploading ? "Загрузка..." : "Импортировать текст"}
          </Button>
        </CardContent>
      </Card>

      {/* Bug#34: недавние текстовые импорты — повторное использование без файла */}
      {resumeHistory.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base" style={{ color: "var(--brand-teal)" }}>
              Ранее загруженные текстовые резюме
            </CardTitle>
            <CardDescription style={{ color: "var(--brand-teal-60)" }}>
              Хранятся локально в вашем браузере (последние {resumeHistory.length}). Нажмите, чтобы подставить текст в поле выше.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {resumeHistory.map((item, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between gap-2 p-2 border rounded text-sm"
                  style={{ borderColor: "var(--brand-teal-20)" }}
                >
                  <span
                    className="truncate flex-1"
                    style={{ color: "var(--brand-teal-60)" }}
                    title={item.text.slice(0, 200)}
                  >
                    {item.text.slice(0, 100).replace(/\s+/g, " ")}
                    {item.text.length > 100 ? "…" : ""}
                  </span>
                  <span
                    className="text-xs shrink-0"
                    style={{ color: "var(--brand-teal-60)" }}
                  >
                    {new Date(item.savedAt).toLocaleString("ru")}
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setResumeText(item.text)}
                  >
                    Применить
                  </Button>
                </li>
              ))}
            </ul>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mt-3"
              onClick={() => {
                try {
                  localStorage.removeItem("resume_text_history");
                  setResumeHistory([]);
                  toast.info("История очищена");
                } catch {
                  // ignore
                }
              }}
            >
              Очистить историю
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Server-side resume history: PDF/DOCX/TXT, ранее загруженные на бэк.
          В отличие от localStorage выше — этот список общий между устройствами
          и не пропадает при очистке браузера. Можно переключаться между
          версиями («Использовать») или перепарсить («Перепарсить»). */}
      {serverResumes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base" style={{ color: "var(--brand-teal)" }}>
              Ранее загруженные файлы
            </CardTitle>
            <CardDescription style={{ color: "var(--brand-teal-60)" }}>
              PDF/DOCX/TXT на сервере ({serverResumes.length} шт.).
              «Использовать» — сделать активным, без перепарсинга.
              «Перепарсить» — заново извлечь текст (если файл правили или
              менялся парсер).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {serverResumes.map((item) => {
                const isLoading = reusingId === item.id;
                return (
                  <li
                    key={item.id}
                    className="flex items-center justify-between gap-2 p-2 border rounded text-sm"
                    style={{ borderColor: "var(--brand-teal-20)" }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className="truncate font-medium"
                          style={{ color: "var(--brand-teal)" }}
                          title={item.original_name}
                        >
                          {item.original_name}
                        </span>
                        {item.is_active ? (
                          <Badge
                            className="shrink-0"
                            style={{
                              backgroundColor: "var(--brand-lime)",
                              color: "var(--brand-teal)",
                            }}
                          >
                            активно
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="shrink-0">
                            в архиве
                          </Badge>
                        )}
                        {item.detected_format ? (
                          <Badge variant="outline" className="shrink-0 uppercase">
                            {item.detected_format}
                          </Badge>
                        ) : null}
                      </div>
                      {item.text_preview ? (
                        <p
                          className="text-xs truncate mt-0.5"
                          style={{ color: "var(--brand-teal-60)" }}
                          title={item.text_preview}
                        >
                          {item.text_preview.slice(0, 80).replace(/\s+/g, " ")}…
                        </p>
                      ) : (
                        <p
                          className="text-xs italic mt-0.5"
                          style={{ color: "var(--brand-teal-60)" }}
                        >
                          ещё не распарсен
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button
                        type="button"
                        size="sm"
                        variant={item.is_active ? "ghost" : "outline"}
                        disabled={item.is_active || isLoading}
                        onClick={() => handleReuseResume(item.id, false)}
                      >
                        {isLoading ? "…" : "Использовать"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isLoading}
                        onClick={() => handleReuseResume(item.id, true)}
                      >
                        Перепарсить
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
            {loadingResumes ? (
              <p
                className="text-xs mt-2"
                style={{ color: "var(--brand-teal-60)" }}
              >
                Загрузка…
              </p>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Альтернативные источники профиля */}
      <Card>
        <CardHeader>
          <CardTitle style={{ color: "var(--brand-teal)" }}>Альтернативные источники</CardTitle>
          <CardDescription style={{ color: "var(--brand-teal-60)" }}>
            Можно создать профиль без файла резюме — вручную или импортом публичного GitHub-профиля.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              className="space-y-2 border rounded-lg p-3"
              style={{ borderColor: "var(--brand-teal-20)" }}
            >
              <h3 className="text-sm font-medium" style={{ color: "var(--brand-teal)" }}>
                Ручное создание
              </h3>
              <Input
                value={manualHeadline}
                onChange={(e) => setManualHeadline(e.target.value)}
                placeholder="Целевая роль *"
              />
              <Input
                value={manualLocation}
                onChange={(e) => setManualLocation(e.target.value)}
                placeholder="Локация"
              />
              <Input
                value={manualTech}
                onChange={(e) => setManualTech(e.target.value)}
                placeholder="Технологии через запятую"
              />
              <Button
                onClick={handleManualIntake}
                disabled={intaking}
                variant="secondary"
                size="sm"
              >
                {intaking ? "Создание…" : "Создать профиль"}
              </Button>
            </div>

            <div
              className="space-y-2 border rounded-lg p-3"
              style={{ borderColor: "var(--brand-teal-20)" }}
            >
              <h3 className="text-sm font-medium" style={{ color: "var(--brand-teal)" }}>
                Импорт GitHub (public)
              </h3>
              <Input
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/username"
              />
              <Input
                value={githubRole}
                onChange={(e) => setGithubRole(e.target.value)}
                placeholder="Целевая роль (необязательно)"
              />
              <Label
                className="text-xs flex items-center gap-2"
                style={{ color: "var(--brand-teal-60)" }}
              >
                Репозиториев: {repoCount}
                <input
                  type="range"
                  min={1}
                  max={30}
                  value={repoCount}
                  onChange={(e) => setRepoCount(Number(e.target.value))}
                />
              </Label>
              <Button
                onClick={handleGithubIntake}
                disabled={intaking || !githubUrl.trim()}
                variant="secondary"
                size="sm"
              >
                {intaking ? "Импорт…" : "Импортировать GitHub"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Profile State */}
      {profile && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <User className="h-5 w-5" style={{ color: "var(--brand-teal-60)" }} />
                <CardTitle style={{ color: "var(--brand-teal)" }}>Текущий профиль</CardTitle>
              </div>
              <Button
                onClick={handleExtractAchievements}
                disabled={extracting}
                variant="default"
                size="sm"
              >
                <Sparkles />
                {extracting ? "Извлечение..." : "Извлечь достижения"}
              </Button>
            </div>
            {(() => {
              const sp = profile.structured_profile;
              const fields = [
                sp?.full_name, sp?.headline, sp?.location,
                sp?.technologies?.length, sp?.ai_tools?.length,
                sp?.automation_tools?.length, sp?.structured_evidence?.length,
              ];
              const filled = fields.filter((v) => v && (Array.isArray(v) ? v.length > 0 : true)).length;
              const pct = Math.round((filled / fields.length) * 100);
              const barColor =
                pct >= 80
                  ? "var(--brand-lime)"
                  : pct >= 50
                    ? "var(--brand-lime-soft)"
                    : "var(--brand-ink)";
              return (
                <div
                  className="mt-2 flex items-center gap-2 text-xs"
                  style={{ color: "var(--brand-teal-60)" }}
                >
                  <BarChart3 className="h-3.5 w-3.5" />
                  <span>Заполнено {filled} из {fields.length} полей</span>
                  <div
                    className="flex-1 h-1.5 rounded-full overflow-hidden max-w-32"
                    style={{ backgroundColor: "var(--brand-teal-10)" }}
                  >
                    <div
                      className="h-full transition-all"
                      style={{ width: `${pct}%`, backgroundColor: barColor }}
                    />
                  </div>
                  <span className="tabular-nums">{pct}%</span>
                </div>
              );
            })()}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span style={{ color: "var(--brand-teal-60)" }}>Имя:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile?.full_name || "—"}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--brand-teal-60)" }}>Должность:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile?.headline || "—"}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--brand-teal-60)" }}>Статус:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.resume_import?.status || "—"}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--brand-teal-60)" }}>Локация:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile?.location || "—"}
                </span>
              </div>
            </div>

            {profile.structured_profile?.technologies?.length > 0 && (
              <div className="text-sm">
                <span style={{ color: "var(--brand-teal-60)" }}>Навыки:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile.technologies.join(", ")}
                </span>
              </div>
            )}

            {profile.structured_profile?.ai_tools?.length > 0 && (
              <div className="text-sm">
                <span style={{ color: "var(--brand-teal-60)" }}>AI инструменты:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile.ai_tools.join(", ")}
                </span>
              </div>
            )}

            {profile.structured_profile?.automation_tools?.length > 0 && (
              <div className="text-sm">
                <span style={{ color: "var(--brand-teal-60)" }}>Automation:</span>{" "}
                <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                  {profile.structured_profile.automation_tools.join(", ")}
                </span>
              </div>
            )}

            {profile.structured_profile?.structured_evidence?.length > 0 && (
              <div>
                <h3
                  className="text-sm font-medium mb-2"
                  style={{ color: "var(--brand-teal)" }}
                >
                  Факты из резюме
                </h3>
                <div className="space-y-2">
                  {profile.structured_profile.structured_evidence.map((e: any, i: number) => (
                    <div
                      key={i}
                      className="p-2 rounded text-sm"
                      style={{ backgroundColor: "var(--brand-teal-5)" }}
                    >
                      <span className="font-medium" style={{ color: "var(--brand-teal)" }}>
                        {e.title}
                      </span>
                      {e.skills?.length > 0 && (
                        <span style={{ color: "var(--brand-teal-60)" }} className="ml-2">
                          ({e.skills.join(", ")})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {profile.achievements?.achievements?.length > 0 ? (() => {
              const list = profile.achievements.achievements as any[];
              const total = list.length;
              const confirmed = list.filter((a) => a.fact_status === "confirmed").length;
              const allConfirmed = confirmed === total;
              return (
                <div>
                  <Separator className="my-4" />
                  <div className="flex items-center justify-between mb-2">
                    <h3
                      className="text-sm font-medium"
                      style={{ color: "var(--brand-teal)" }}
                    >
                      Достижения ({total})
                    </h3>
                    <Badge
                      variant={allConfirmed ? "default" : "secondary"}
                      style={
                        allConfirmed
                          ? { backgroundColor: "var(--brand-lime)", color: "var(--brand-teal)" }
                          : undefined
                      }
                    >
                      Подтверждено {confirmed} / {total}
                    </Badge>
                  </div>
                  <p
                    className="text-xs mb-3"
                    style={{ color: "var(--brand-teal-60)" }}
                  >
                    Подтвердите достижения (статус «Подтверждено»), чтобы они попали в адаптированное резюме.
                  </p>
                  <div className="space-y-3">
                    {list.map((a: any) => (
                      <AchievementReviewCard
                        key={a.id}
                        token={token ?? ""}
                        achievement={a}
                        onSaved={reloadProfile}
                      />
                    ))}
                  </div>
                  <Alert
                    className="mt-4"
                    style={
                      allConfirmed
                        ? {
                            borderColor: "var(--brand-lime)",
                            backgroundColor: "var(--brand-lime-soft)",
                          }
                        : undefined
                    }
                  >
                    {allConfirmed ? (
                      <CheckCircle2 style={{ color: "var(--brand-teal)" }} />
                    ) : (
                      <AlertTriangle />
                    )}
                    <AlertTitle>
                      {allConfirmed
                        ? "Все достижения подтверждены"
                        : `Осталось подтвердить ${total - confirmed} из ${total}`}
                    </AlertTitle>
                    <AlertDescription>
                      {allConfirmed
                        ? "Можно перейти к подбору вакансий."
                        : "Часть достижений не подтверждена."}
                    </AlertDescription>
                    <Button
                      onClick={() => router.push("/vacancies")}
                      className="mt-2"
                      size="sm"
                      variant={allConfirmed ? "default" : "link"}
                    >
                      {allConfirmed ? "Перейти к вакансиям →" : "Пропустить и перейти к вакансиям"}
                    </Button>
                  </Alert>
                </div>
              );
            })() : (
              <div
                className="mt-4 rounded-lg border border-dashed p-6 text-center"
                style={{
                  borderColor: "var(--brand-teal-20)",
                  backgroundColor: "var(--brand-teal-5)",
                }}
              >
                <Target
                  className="mx-auto h-8 w-8"
                  style={{ color: "var(--brand-teal-60)" }}
                />
                <p
                  className="mt-2 text-sm font-medium"
                  style={{ color: "var(--brand-teal)" }}
                >
                  Достижений пока нет
                </p>
                <p
                  className="mt-1 text-xs"
                  style={{ color: "var(--brand-teal-60)" }}
                >
                  Нажмите «Извлечь достижения» — парсер найдёт результаты с метриками в вашем резюме.
                </p>
                <Button
                  onClick={handleExtractAchievements}
                  disabled={extracting}
                  variant="outline"
                  size="sm"
                  className="mt-3"
                >
                  <Sparkles />
                  {extracting ? "Извлечение..." : "Извлечь достижения"}
                </Button>
              </div>
            )}

            {profile.structured_profile?.warnings?.length > 0 && (
              <Alert className="mt-4">
                <AlertTriangle />
                <AlertTitle>Рекомендации</AlertTitle>
                <AlertDescription>
                  <ul className="space-y-1 mt-2">
                    {profile.structured_profile.warnings.map((w: string, i: number) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {!profile && (
        <Card>
          <CardContent
            className="py-8 text-center"
            style={{ color: "var(--brand-teal-60)" }}
          >
            Загрузите резюме или создайте профиль вручную, чтобы начать.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
