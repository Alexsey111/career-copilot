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
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Профиль кандидата</h1>

      {/* Upload Resume */}
      <Card>
        <CardHeader>
          <CardTitle>Загрузить резюме</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-muted/50 transition-colors mb-4">
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold">Нажмите для выбора</span> или перетащите файл
              </p>
              <p className="text-xs text-muted-foreground/70">PDF, DOCX, TXT</p>
            </div>
            <input type="file" accept=".pdf,.docx,.txt" onChange={handleFileUpload} className="hidden" />
          </label>
          <p className="text-xs text-muted-foreground mb-2">или вставьте текст:</p>
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

      {/* Альтернативные источники профиля */}
      <Card>
        <CardHeader>
          <CardTitle>Альтернативные источники</CardTitle>
          <CardDescription>
            Можно создать профиль без файла резюме — вручную или импортом публичного GitHub-профиля.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2 border border-border rounded-lg p-3">
              <h3 className="text-sm font-medium">Ручное создание</h3>
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

            <div className="space-y-2 border border-border rounded-lg p-3">
              <h3 className="text-sm font-medium">Импорт GitHub (public)</h3>
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
              <Label className="text-xs text-muted-foreground flex items-center gap-2">
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
                <User className="h-5 w-5 text-muted-foreground" />
                <CardTitle>Текущий профиль</CardTitle>
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
              return (
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <BarChart3 className="h-3.5 w-3.5" />
                  <span>Заполнено {filled} из {fields.length} полей</span>
                  <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden max-w-32">
                    <div
                      className={`h-full transition-all ${pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-400"}`}
                      style={{ width: `${pct}%` }}
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
                <span className="text-muted-foreground">Имя:</span>{" "}
                <span className="font-medium">{profile.structured_profile?.full_name || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Должность:</span>{" "}
                <span className="font-medium">{profile.structured_profile?.headline || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Статус:</span>{" "}
                <span className="font-medium">{profile.resume_import?.status || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Локация:</span>{" "}
                <span className="font-medium">{profile.structured_profile?.location || "—"}</span>
              </div>
            </div>

            {profile.structured_profile?.technologies?.length > 0 && (
              <div className="text-sm">
                <span className="text-muted-foreground">Навыки:</span>{" "}
                <span className="font-medium">{profile.structured_profile.technologies.join(", ")}</span>
              </div>
            )}

            {profile.structured_profile?.ai_tools?.length > 0 && (
              <div className="text-sm">
                <span className="text-muted-foreground">AI инструменты:</span>{" "}
                <span className="font-medium">{profile.structured_profile.ai_tools.join(", ")}</span>
              </div>
            )}

            {profile.structured_profile?.automation_tools?.length > 0 && (
              <div className="text-sm">
                <span className="text-muted-foreground">Automation:</span>{" "}
                <span className="font-medium">{profile.structured_profile.automation_tools.join(", ")}</span>
              </div>
            )}

            {profile.structured_profile?.structured_evidence?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Факты из резюме</h3>
                <div className="space-y-2">
                  {profile.structured_profile.structured_evidence.map((e: any, i: number) => (
                    <div key={i} className="p-2 bg-muted/50 rounded text-sm">
                      <span className="font-medium">{e.title}</span>
                      {e.skills?.length > 0 && (
                        <span className="text-muted-foreground ml-2">({e.skills.join(", ")})</span>
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
                    <h3 className="text-sm font-medium text-foreground">
                      Достижения ({total})
                    </h3>
                    <Badge variant={allConfirmed ? "default" : "secondary"}>
                      Подтверждено {confirmed} / {total}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-3">
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
                  <Alert className={`mt-4 ${allConfirmed ? "border-green-200 bg-green-50" : ""}`}>
                    {allConfirmed ? <CheckCircle2 className="text-green-600" /> : <AlertTriangle />}
                    <AlertTitle>
                      {allConfirmed ? "Все достижения подтверждены" : `Осталось подтвердить ${total - confirmed} из ${total}`}
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
              <div className="mt-4 rounded-lg border border-dashed border-border bg-muted/30 p-6 text-center">
                <Target className="mx-auto h-8 w-8 text-muted-foreground/60" />
                <p className="mt-2 text-sm font-medium text-foreground">
                  Достижений пока нет
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
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
          <CardContent className="py-8 text-center text-muted-foreground">
            Загрузите резюме или создайте профиль вручную, чтобы начать.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
