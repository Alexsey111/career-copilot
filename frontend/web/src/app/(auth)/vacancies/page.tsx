"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import DemoBanner from "@/components/DemoBanner";

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

  // Load recommendations based on profile
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
      await api.importVacancyFromUrl(token, importUrl);
      setImportUrl("");
      toast.success("Вакансия импортирована по ссылке");
      setQuotaRefreshKey((k) => k + 1);
      if (searchQuery) handleSearch();
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
    <Link
      key={v.id}
      href={`/vacancies/${v.id}`}
      className="block bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-semibold text-blue-700">{v.title}</h3>
          <p className="text-sm text-gray-600">
            {v.company || "Не указана"} {v.location ? `• ${v.location}` : ""}
          </p>
          {(v.salary_from || v.salary_to) && (
            <p className="text-sm text-green-700 mt-1">
              {v.salary_from && v.salary_to
                ? `${v.salary_from.toLocaleString()} - ${v.salary_to.toLocaleString()}`
                : v.salary_from
                ? `от ${v.salary_from.toLocaleString()}`
                : `до ${v.salary_to?.toLocaleString()}`}
            </p>
          )}
        </div>
        {v.similarity != null && v.similarity > 0 && (
          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
            {Math.round(v.similarity * 100)}% match
          </span>
        )}
      </div>
    </Link>
  );

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Вакансии</h1>

      {token && <DemoBanner token={token} refreshKey={quotaRefreshKey} />}

      {/* Import from URL */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Добавить вакансию</h2>

        {/* File upload */}
        <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors mb-3">
          <div className="flex flex-col items-center justify-center">
            <p className="text-sm text-gray-500">
              <span className="font-semibold">Перетащите файл</span> с описанием вакансии или нажмите для выбора
            </p>
            <p className="text-xs text-gray-400">
              TXT, DOCX, PDF {fileInput ? `— выбран: ${fileInput.name}` : ""}
            </p>
          </div>
          <input
            type="file"
            accept=".txt,.docx,.pdf"
            onChange={(e) => setFileInput(e.target.files?.[0] ?? null)}
            className="hidden"
          />
        </label>

        {fileInput && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3 p-3 bg-gray-50 rounded-lg">
            <input
              type="text"
              value={fileTitle}
              onChange={(e) => setFileTitle(e.target.value)}
              placeholder="Название вакансии *"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="text"
              value={fileCompany}
              onChange={(e) => setFileCompany(e.target.value)}
              placeholder="Компания"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="text"
              value={fileLocation}
              onChange={(e) => setFileLocation(e.target.value)}
              placeholder="Локация"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="url"
              value={fileSourceUrl}
              onChange={(e) => setFileSourceUrl(e.target.value)}
              placeholder="Ссылка-источник (необязательно)"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <button
              onClick={handleImportFromFile}
              disabled={importing || !fileTitle.trim()}
              className="md:col-span-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
            >
              {importing ? "Импорт..." : "Импортировать из файла"}
            </button>
          </div>
        )}

        <div className="text-xs text-gray-500 mb-2">или вставьте текст:</div>
        <textarea
          value={vacancyText}
          onChange={(e) => setVacancyText(e.target.value)}
          placeholder="Вставьте описание вакансии..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent h-32 text-sm mb-3"
        />
        <button
          onClick={handleImportFromText}
          disabled={importing || !vacancyText.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {importing ? "Импорт..." : "Импортировать текст"}
        </button>

        <div className="text-xs text-gray-500 mt-3">или по ссылке:</div>
        <div className="flex gap-2 mt-2">
          <input
            type="url"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            placeholder="https://hh.ru/vacancy/..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importUrl.trim()}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50"
          >
            {importing ? "Импорт..." : "По ссылке"}
          </button>
        </div>
      </div>

      {/* Manual search */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Поиск вакансий</h2>
        <div className="flex gap-2 mb-3">
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setSearchMode("semantic")}
              className={`px-3 py-1 text-sm rounded-md ${
                searchMode === "semantic"
                  ? "bg-white shadow text-blue-600"
                  : "text-gray-600"
              }`}
            >
              Похожие (AI)
            </button>
            <button
              onClick={() => setSearchMode("text")}
              className={`px-3 py-1 text-sm rounded-md ${
                searchMode === "text"
                  ? "bg-white shadow text-blue-600"
                  : "text-gray-600"
              }`}
            >
              Текстовый
            </button>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Python developer, remote..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !searchQuery.trim()}
            className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 disabled:opacity-50"
          >
            {loading ? "Поиск..." : "Найти"}
          </button>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Рекомендовано вам</h2>
          <p className="text-sm text-gray-500 mb-3">На основе вашего профиля и навыков</p>
          <div className="space-y-3">
            {recommendations.slice(0, 5).map(renderVacancyCard)}
          </div>
        </div>
      )}

      {/* Search results */}
      {searchResults.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Результаты поиска</h2>
          <div className="space-y-3">
            {searchResults.map(renderVacancyCard)}
          </div>
        </div>
      )}

      {/* Empty state */}
      {searchResults.length === 0 && recommendations.length === 0 && !loading && (
        <div className="text-center text-gray-500 py-8">
          Вставьте ссылку на вакансию или воспользуйтесь поиском
        </div>
      )}
    </div>
  );
}
