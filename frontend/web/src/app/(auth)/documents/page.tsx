"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { useSessionDocs } from "@/contexts/SessionDocumentsContext";
import { api } from "@/lib/api";
import DocumentActions from "@/components/DocumentActions";
import type { ActiveDocumentResponse } from "@/lib/types";

interface DocEntry {
  id: string;
  kind: string;
  vacancyId?: string | null;
  reviewStatus?: string;
  isActive?: boolean;
  label: string;
}

export default function DocumentsPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const sessionDocs = useSessionDocs();
  const [active, setActive] = useState<DocEntry[]>([]);
  const [recent, setRecent] = useState<DocEntry[]>([]);
  const [manualId, setManualId] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    Promise.allSettled([
      api.getActiveDocument(token, "resume").then((r) => r as ActiveDocumentResponse),
      api.getActiveDocument(token, "cover_letter").then((r) => r as ActiveDocumentResponse),
    ])
      .then((results) => {
        const entries: DocEntry[] = [];
        results.forEach((res, idx) => {
          if (res.status === "fulfilled" && res.value?.id) {
            entries.push({
              id: res.value.id,
              kind: res.value.document_kind,
              vacancyId: res.value.vacancy_id,
              reviewStatus: res.value.review_status,
              isActive: res.value.is_active,
              label: idx === 0 ? "Активное резюме" : "Активное письмо",
            });
          }
        });
        setActive(entries);
      })
      .finally(() => setLoading(false));
  }, [token]);

  // Последние сгенерированные из сессионного контекста.
  useEffect(() => {
    if (!token) return;
    // SessionDocumentsContext хранит данные в localStorage; перечитываем при монтировании.
    const collected: DocEntry[] = [];
    try {
      const raw = window.localStorage.getItem("ccp:session-docs");
      const map = raw ? JSON.parse(raw) : {};
      Object.entries(map).forEach(([vacancyId, s]) => {
        const sess = s as Record<string, string | undefined>;
        if (sess.resumeId) {
          collected.push({ id: sess.resumeId, kind: "resume", vacancyId, label: `Резюме (вакансия ${vacancyId.slice(0, 8)}…)` });
        }
        if (sess.coverLetterId) {
          collected.push({ id: sess.coverLetterId, kind: "cover_letter", vacancyId, label: `Письмо (вакансия ${vacancyId.slice(0, 8)}…)` });
        }
      });
    } catch {
      // ignore
    }
    setRecent(collected);
  }, [token]);

  const reloadActive = () => {
    if (!token) return;
    Promise.allSettled([
      api.getActiveDocument(token, "resume").then((r) => r as ActiveDocumentResponse),
      api.getActiveDocument(token, "cover_letter").then((r) => r as ActiveDocumentResponse),
    ]).then((results) => {
      const entries: DocEntry[] = [];
      results.forEach((res, idx) => {
        if (res.status === "fulfilled" && res.value?.id) {
          entries.push({
            id: res.value.id,
            kind: res.value.document_kind,
            vacancyId: res.value.vacancy_id,
            reviewStatus: res.value.review_status,
            isActive: res.value.is_active,
            label: idx === 0 ? "Активное резюме" : "Активное письмо",
          });
        }
      });
      setActive(entries);
    });
  };

  const recentOnly = recent.filter((r) => !active.some((a) => a.id === r.id));

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Документы</h1>

      {loading && <p className="text-gray-500 mb-4">Загрузка активных документов…</p>}

      {/* Активные документы */}
      {active.length > 0 && (
        <div className="mb-6">
          <h2 className="font-semibold mb-3">Активные документы</h2>
          <div className="space-y-3">
            {active.map((d) => (
              <div key={d.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium text-gray-800">{d.label}</p>
                    <p className="text-xs text-gray-400">
                      {d.id.slice(0, 8)}… · статус: {d.reviewStatus ?? "—"} · {d.isActive ? "активен" : "не активен"}
                    </p>
                  </div>
                  <Link
                    href={`/documents/${d.id}`}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Открыть workspace →
                  </Link>
                </div>
                {token && (
                  <DocumentActions
                    token={token}
                    documentId={d.id}
                    filename={d.kind}
                    reviewStatus={d.reviewStatus}
                    isActive={d.isActive}
                    onApproved={reloadActive}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Последние сгенерированные */}
      {recentOnly.length > 0 && (
        <div className="mb-6">
          <h2 className="font-semibold mb-3">Последние сгенерированные</h2>
          <div className="space-y-2">
            {recentOnly.map((d) => (
              <Link
                key={d.id}
                href={`/documents/${d.id}`}
                className="block bg-white rounded-lg border border-gray-200 p-3 hover:shadow-sm"
              >
                <span className="text-sm text-gray-700">{d.label}</span>
                <span className="text-xs text-gray-400 ml-2">{d.id.slice(0, 8)}…</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Ручной ввод ID */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Открыть по ID</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            placeholder="ID документа"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          {manualId.trim() && (
            <Link
              href={`/documents/${manualId.trim()}`}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
            >
              Открыть
            </Link>
          )}
        </div>
      </div>

      {active.length === 0 && recentOnly.length === 0 && !loading && (
        <div className="text-center text-gray-500 py-8">
          Сгенерируйте резюме или письмо из страницы вакансии — они появятся здесь.
        </div>
      )}
    </div>
  );
}