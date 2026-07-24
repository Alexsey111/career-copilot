"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToastCtx } from "@/contexts/ToastContext";

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const PDF_MIME = "application/pdf";

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Кнопки экспорта документа (TXT, MD, DOCX, PDF) и approve/activate.
 * Бэкенд требует документ approved+active для экспорта (иначе 409). DOCX/PDF —
 * бинарные, поэтому грузим как blob с правильным mime, а не как text.
 */
export default function DocumentActions({
  token,
  documentId,
  filename = "document",
  reviewStatus,
  isActive,
  onApproved,
  compact = false,
}: {
  token: string;
  documentId: string;
  filename?: string;
  reviewStatus?: string;
  isActive?: boolean;
  onApproved?: () => void;
  compact?: boolean;
}) {
  const toast = useToastCtx();
  const [exporting, setExporting] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);

  const isApproved = reviewStatus === "approved";
  const canExport = isApproved && isActive;

  const handleExportText = async (format: "txt" | "md") => {
    setExporting(format);
    try {
      const text = await api.exportDocument(token, documentId, format);
      downloadBlob(new Blob([text], { type: "text/plain" }), `${filename}.${format}`);
      toast.success(`Экспорт .${format} готов`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Экспорт не удался");
    } finally {
      setExporting(null);
    }
  };

  const handleExportDocx = async () => {
    setExporting("docx");
    try {
      const blob = await api.exportDocumentBlob(token, documentId, "docx");
      downloadBlob(new Blob([blob], { type: DOCX_MIME }), `${filename}.docx`);
      toast.success("Экспорт .docx готов");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Экспорт не удался");
    } finally {
      setExporting(null);
    }
  };

  const handleExportPdf = async () => {
    setExporting("pdf");
    try {
      const blob = await api.exportDocumentBlob(token, documentId, "pdf");
      downloadBlob(new Blob([blob], { type: PDF_MIME }), `${filename}.pdf`);
      toast.success("Экспорт .pdf готов");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Экспорт не удался");
    } finally {
      setExporting(null);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await api.approveDocument(token, documentId, true);
      toast.success("Документ утверждён и активирован");
      onApproved?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Утверждение не удалось");
    } finally {
      setApproving(false);
    }
  };

  const btn =
    "px-3 py-1 text-sm border border-[color:var(--brand-teal-20)] rounded-lg hover:bg-[color:var(--brand-cream-soft)] disabled:opacity-50";

  return (
    <div className={`flex flex-wrap gap-2 ${compact ? "" : "items-center"}`}>
      <button onClick={() => handleExportText("txt")} disabled={exporting !== null || !canExport} className={btn}>
        {exporting === "txt" ? "..." : "TXT"}
      </button>
      <button onClick={() => handleExportText("md")} disabled={exporting !== null || !canExport} className={btn}>
        {exporting === "md" ? "..." : "MD"}
      </button>
      <button onClick={handleExportDocx} disabled={exporting !== null || !canExport} className={btn}>
        {exporting === "docx" ? "..." : "DOCX"}
      </button>
      <button onClick={handleExportPdf} disabled={exporting !== null || !canExport} className={btn}>
        {exporting === "pdf" ? "..." : "PDF"}
      </button>
      {!isApproved && (
        <button
          onClick={handleApprove}
          disabled={approving}
          className="px-3 py-1 text-sm bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded-lg hover:bg-[#b8e85c] disabled:opacity-50"
        >
          {approving ? "Утверждение..." : "Утвердить"}
        </button>
      )}
      {!canExport && (
        <span className="text-xs text-[color:var(--brand-teal-40)]">
          Экспорт доступен после утверждения (approved + active)
        </span>
      )}
    </div>
  );
}