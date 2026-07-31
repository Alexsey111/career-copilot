"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { runAiAction } from "@/lib/ai-action";
import DocumentActions from "@/components/DocumentActions";
import DocumentReviewSummaryView from "@/components/DocumentReviewSummary";
import DocumentDiffView from "@/components/DocumentDiffView";
import type { DocumentRead, DocumentReviewSummary, DocumentDiffResponse } from "@/lib/types";

export default function DocumentWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const toast = useToastCtx();
  const router = useRouter();

  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [summary, setSummary] = useState<DocumentReviewSummary | null>(null);
  const [diffTarget, setDiffTarget] = useState("");
  const [diff, setDiff] = useState<DocumentDiffResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [enhancing, setEnhancing] = useState(false);

  useEffect(() => {
    if (!token || !id) return;
    setLoading(true);
    Promise.allSettled([
      api.getDocument(token, id).then((r) => r as DocumentRead),
      api.getDocumentReviewSummary(token, id).then((r) => r as DocumentReviewSummary),
    ])
      .then(([docRes, sumRes]) => {
        if (docRes.status === "fulfilled") setDoc(docRes.value);
        if (sumRes.status === "fulfilled") setSummary(sumRes.value);
      })
      .finally(() => setLoading(false));
  }, [token, id]);

  const reloadSummary = () => {
    if (!token || !id) return;
    api.getDocumentReviewSummary(token, id).then((r) => setSummary(r as DocumentReviewSummary)).catch(() => {});
    api.getDocument(token, id).then((r) => setDoc(r as DocumentRead)).catch(() => {});
  };

  const handleDiff = async () => {
    if (!token || !id || !diffTarget.trim()) return;
    try {
      const res = (await api.getDocumentDiff(token, id, diffTarget.trim())) as DocumentDiffResponse;
      setDiff(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Diff недоступен");
    }
  };

  const handleEnhance = async () => {
    if (!token || !id || !doc) return;
    const text = doc.rendered_text ?? "";
    if (!text.trim()) {
      toast.error("Нет текста документа для улучшения");
      return;
    }
    setEnhancing(true);
    const kind = doc.document_kind ?? "resume";
    const result = await runAiAction(toast, "Улучшение документа", async () => {
      if (kind === "cover_letter") {
        return api.enhanceCoverLetter(token, id, text);
      }
      return api.enhanceResume(token, id, text);
    });
    setEnhancing(false);
    if (result) {
      toast.success("Создана улучшенная версия-черновик");
      // Bug#102: раньше вызывали reloadSummary() — он перезапрашивал СТАРЫЙ
      // документ по id из URL, а новый document_id из ответа игнорировался.
      // Юзер видел оригинальный текст без изменений. Теперь переходим на
      // страницу нового документа с улучшенным текстом (актуально и для
      // resume, и для cover letter — один handleEnhance на оба).
      const newId = (result as { document_id?: string })?.document_id;
      if (newId && newId !== id) {
        router.push(`/documents/${newId}`);
      } else {
        reloadSummary();
      }
    }
  };

  const handleActivate = async () => {
    if (!token || !id) return;
    try {
      await api.activateDocument(token, id);
      toast.success("Документ сделан активным");
      reloadSummary();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Активация не удалась");
    }
  };

  if (loading) return <div className="text-[color:var(--brand-teal-60)]">Загрузка…</div>;

  if (!doc) {
    return (
      <div className="max-w-4xl">
        <p className="text-[color:var(--brand-teal-60)]">Документ не найден или нет доступа.</p>
        <button onClick={() => router.push("/documents")} className="mt-3 text-[color:var(--brand-teal)] hover:underline">
          ← К списку документов
        </button>
      </div>
    );
  }

  const kind = doc.document_kind ?? "resume";

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.back()} className="text-[color:var(--brand-teal-60)] hover:text-[color:var(--brand-teal)] mb-4">
        &larr; Назад
      </button>

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">
          {kind === "cover_letter" ? "Сопроводительное письмо" : "Резюме"}
        </h1>
        <span className="text-xs text-[color:var(--brand-teal-40)]">{doc.id.slice(0, 8)}… · {doc.version_label ?? "v1"}</span>
      </div>

      {/* Действия */}
      <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-4 mb-6 space-y-3">
        {token && (
          <DocumentActions
            token={token}
            documentId={doc.id}
            filename={kind}
            reviewStatus={doc.review_status}
            isActive={doc.is_active}
            onApproved={reloadSummary}
          />
        )}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleActivate}
            className="px-3 py-1 text-sm border border-[color:var(--brand-teal-20)] rounded-lg hover:bg-[color:var(--brand-cream-soft)]"
          >
            Сделать активным
          </button>
          <button
            onClick={handleEnhance}
            disabled={enhancing}
            className="px-3 py-1 text-sm bg-[color:var(--brand-teal)] text-white rounded-lg hover:opacity-90 disabled:opacity-50"
          >
            {enhancing ? "Улучшение…" : "Создать улучшенную версию (AI)"}
          </button>
        </div>
      </div>

      {/* Текст документа */}
      {doc.rendered_text && (
        <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6 mb-6">
          <h2 className="font-semibold mb-3">Текст документа</h2>
          <pre className="text-sm text-[color:var(--brand-teal)] whitespace-pre-wrap bg-[color:var(--brand-cream-soft)] p-4 rounded max-h-96 overflow-y-auto">
            {doc.rendered_text}
          </pre>
        </div>
      )}

      {/* Сводка проверки */}
      {summary && (
        <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6 mb-6">
          <h2 className="font-semibold mb-3">Сводка проверки</h2>
          <DocumentReviewSummaryView summary={summary} />
        </div>
      )}

      {/* Сравнение версий */}
      <div className="bg-white rounded-xl shadow-sm border border-[color:var(--brand-teal-20)] p-6">
        <h2 className="font-semibold mb-3">Сравнение версий (diff)</h2>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={diffTarget}
            onChange={(e) => setDiffTarget(e.target.value)}
            placeholder="ID другой версии для сравнения"
            className="flex-1 px-3 py-2 border border-[color:var(--brand-teal-20)] rounded-lg text-sm"
          />
          <button
            onClick={handleDiff}
            disabled={!diffTarget.trim()}
            className="px-4 py-2 bg-[color:var(--brand-ink)] text-white rounded-lg hover:bg-[#142527] disabled:opacity-50 text-sm"
          >
            Сравнить
          </button>
        </div>
        <DocumentDiffView diff={diff} />
      </div>
    </div>
  );
}