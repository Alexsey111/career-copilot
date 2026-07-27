"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Loader2, Briefcase } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import DemoBanner from "@/components/DemoBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

interface Vacancy {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  salary_from: number | null;
  salary_to: number | null;
  similarity?: number | null;
  created_at: string;
}

export default function VacanciesPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Vacancy[]>([]);
  const [searchResults, setSearchResults] = useState<Vacancy[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [importUrl, setImportUrl] = useState("");
  const [vacancyText, setVacancyText] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [searchMode, setSearchMode] = useState<"text" | "semantic">("text");
  const [fileInput, setFileInput] = useState<File | null>(null);
  const [fileTitle, setFileTitle] = useState("");
  const [fileCompany, setFileCompany] = useState("");
  const [fileLocation, setFileLocation] = useState("");
  const [fileSourceUrl, setFileSourceUrl] = useState("");
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    const loadRecommendations = async () => {
      try {
        const profile = await api.getProfile(token) as any;
        const technologies = profile?.structured_profile?.technologies || [];
        const headline = profile?.structured_profile?.headline || "";
        const query = [headline, ...technologies.slice(0, 5)].join(" ");
        if (query.trim()) {
          const res = await api.searchVacancies(token, { query }) as any;
          setRecommendations(res.items || []);
        }
      } catch (err) {
        console.error("Failed to load recommendations:", err);
      }
    };
    loadRecommendations();
  }, [token]);

  const handleSearch = async () => {
    if (!searchQuery.trim() || !token) return;
    setLoading(true);
    try {
      const res =
        searchMode === "semantic"
          ? await api.semanticSearchVacancies(token, searchQuery) as any
          : await api.searchVacancies(token, { query: searchQuery }) as any;
      setSearchResults(res.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importUrl.trim() || !token) return;
    setImporting(true);
    try {
      const res = (await api.importVacancyFromUrl(token, importUrl)) as any;
      setImportUrl("");
      setQuotaRefreshKey((k) => k + 1);
      if (searchQuery) handleSearch();
      // Редирект на detail — там «1. Анализировать вакансию» и дальше
      // пошаговый CTA (резюме/письмо/отклик). Раньше юзер оставался в списке
      // без перехода к анализу («вакансия по ссылке получается, но дальше
      // анализа нет»). Паритет с text/file-импортом (router.push ниже).
      if (res?.vacancy_id || res?.id) {
        toast.success("Вакансия импортирована по ссылке");
        router.push(`/vacancies/${res.vacancy_id || res.id}`);
      } else {
        toast.success("Вакансия импортирована по ссылке");
      }
    } catch (err: any) {
      toast.error(err.message || "Ошибка импорта");
    } finally {
      setImporting(false);
    }
  };

  const handleImportFromText = async () => {
    if (!vacancyText.trim() || !token) return;
    setImporting(true);
    try {
      const res = await api.importVacancyFromText(token, vacancyText) as any;
      setVacancyText("");
      toast.success("Вакансия импортирована из текста");
      setQuotaRefreshKey((k) => k + 1);
      router.push(`/vacancies/${res.vacancy_id}`);
    } catch (err: any) {
      toast.error(err.message || "Ошибка импорта");
    } finally {
      setImporting(false);
    }
  };

  const handleImportFromFile = async () => {
    if (!fileInput || !token) return;
    if (!fileTitle.trim()) {
      toast.error("Укажите название вакансии для файла");
      return;
    }
    setImporting(true);
    try {
      const uploaded = (await api.uploadFile(token, fileInput, "vacancy")) as any;
      const sourceFileId = uploaded?.source_file_id || uploaded?.id;
      if (!sourceFileId) throw new Error("Файл не загружен");
      const res = (await api.importVacancyFromFile(
        token,
        sourceFileId,
        fileTitle.trim(),
        fileCompany.trim() || undefined,
        fileLocation.trim() || undefined,
        fileSourceUrl.trim() || undefined
      )) as any;
      toast.success("Вакансия импортирована из файла");
      setQuotaRefreshKey((k) => k + 1);
      router.push(`/vacancies/${res.vacancy_id}`);
    } catch (err: any) {
      toast.error(err.message || "Ошибка загрузки файла");
    } finally {
      setImporting(false);
    }
  };

  const renderVacancyCard = (v: Vacancy) => (
    <Link key={v.id} href={`/vacancies/${v.id}`} className="block">
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardContent className="pt-6">
          <div className="flex justify-between items-start gap-3">
            <div className="min-w-0">
              <h3 className="font-semibold text-[color:var(--brand-teal)]">{v.title}</h3>
              <p className="text-sm text-[color:var(--brand-teal-60)]">
                {v.company || "Не указана"} {v.location ? `• ${v.location}` : ""}
              </p>
              {(v.salary_from || v.salary_to) && (
                <p className="text-sm text-[color:var(--brand-teal)] mt-1">
                  {v.salary_from && v.salary_to
                    ? `${v.salary_from.toLocaleString()} - ${v.salary_to.toLocaleString()}`
                    : v.salary_from
                    ? `от ${v.salary_from.toLocaleString()}`
                    : `до ${v.salary_to?.toLocaleString()}`}
                </p>
              )}
            </div>
            {v.similarity != null && v.similarity > 0 && (
              <Badge variant="secondary">{Math.round(v.similarity * 100)}% match</Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Вакансии</h1>

      {token && <DemoBanner token={token} refreshKey={quotaRefreshKey} />}

      <Card>
        <CardHeader>
          <CardTitle>Добавить вакансию</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Label
            htmlFor="vacancy-file"
            className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-[color:var(--brand-teal-20)] rounded-lg cursor-pointer hover:bg-[color:var(--brand-teal-5)] transition-colors"
          >
            <div className="flex flex-col items-center justify-center">
              <p className="text-sm text-[color:var(--brand-teal-60)]">
                <span className="font-semibold">Перетащите файл</span> с описанием вакансии или нажмите для выбора
              </p>
              <p className="text-xs text-[color:var(--brand-teal-60)]">
                TXT, DOCX, PDF {fileInput ? `— выбран: ${fileInput.name}` : ""}
              </p>
            </div>
            <Input
              id="vacancy-file"
              type="file"
              accept=".txt,.docx,.pdf"
              onChange={(e) => setFileInput(e.target.files?.[0] ?? null)}
              className="hidden"
            />
          </Label>

          {fileInput && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 p-3 bg-[color:var(--brand-teal-5)] rounded-lg">
              <Input
                type="text"
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
                placeholder="Название вакансии *"
              />
              <Input
                type="text"
                value={fileCompany}
                onChange={(e) => setFileCompany(e.target.value)}
                placeholder="Компания"
              />
              <Input
                type="text"
                value={fileLocation}
                onChange={(e) => setFileLocation(e.target.value)}
                placeholder="Локация"
              />
              <Input
                type="url"
                value={fileSourceUrl}
                onChange={(e) => setFileSourceUrl(e.target.value)}
                placeholder="Ссылка-источник (необязательно)"
              />
              <Button
                onClick={handleImportFromFile}
                disabled={importing || !fileTitle.trim()}
                className="md:col-span-2"
              >
                {importing ? <Loader2 className="animate-spin" /> : null}
                {importing ? "Импорт..." : "Импортировать из файла"}
              </Button>
            </div>
          )}

          <Separator />

          <div>
            <p className="text-xs text-[color:var(--brand-teal-60)] mb-2">или вставьте текст:</p>
            <Textarea
              value={vacancyText}
              onChange={(e) => setVacancyText(e.target.value)}
              placeholder="Вставьте описание вакансии..."
              className="h-32"
            />
            <Button
              onClick={handleImportFromText}
              disabled={importing || !vacancyText.trim()}
              className="mt-3"
            >
              {importing ? <Loader2 className="animate-spin" /> : null}
              {importing ? "Импорт..." : "Импортировать текст"}
            </Button>
          </div>

          <Separator />

          <div>
            <p className="text-xs text-[color:var(--brand-teal-60)] mb-2">или по ссылке:</p>
            <div className="flex gap-2">
              <Input
                type="url"
                value={importUrl}
                onChange={(e) => setImportUrl(e.target.value)}
                placeholder="https://hh.ru/vacancy/..."
                className="flex-1"
              />
              <Button
                variant="secondary"
                onClick={handleImport}
                disabled={importing || !importUrl.trim()}
              >
                {importing ? <Loader2 className="animate-spin" /> : null}
                {importing ? "Импорт..." : "По ссылке"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Поиск вакансий</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="inline-flex bg-[color:var(--brand-teal-5)] rounded-lg p-1">
            <Button
              variant={searchMode === "semantic" ? "default" : "ghost"}
              size="sm"
              onClick={() => setSearchMode("semantic")}
            >
              Похожие (AI)
            </Button>
            <Button
              variant={searchMode === "text" ? "default" : "ghost"}
              size="sm"
              onClick={() => setSearchMode("text")}
            >
              Текстовый
            </Button>
          </div>
          <div className="flex gap-2">
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Python developer, remote..."
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={loading || !searchQuery.trim()}>
              {loading ? <Loader2 className="animate-spin" /> : <Search />}
              {loading ? "Поиск..." : "Найти"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Рекомендовано вам</h2>
            <p className="text-sm text-[color:var(--brand-teal-60)]">На основе вашего профиля и навыков</p>
          </div>
          <div className="space-y-3">
            {recommendations.slice(0, 5).map(renderVacancyCard)}
          </div>
        </div>
      )}

      {searchResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Результаты поиска</h2>
          <div className="space-y-3">
            {searchResults.map(renderVacancyCard)}
          </div>
        </div>
      )}

      {searchResults.length === 0 && recommendations.length === 0 && !loading && (
        <Card>
          <CardContent className="py-8 text-center text-[color:var(--brand-teal-60)]">
            <Briefcase className="mx-auto mb-2 size-8 opacity-50" />
            Вставьте ссылку на вакансию или воспользуйтесь поиском
          </CardContent>
        </Card>
      )}
    </div>
  );
}
