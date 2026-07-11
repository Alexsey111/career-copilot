"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function DocumentsPage() {
  const { token } = useAuth();
  const [documentId, setDocumentId] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);

  const handleLoad = async () => {
    if (!documentId.trim() || !token) return;
    setLoading(true);
    try {
      const doc = await api.getDocument(token, documentId) as any;
      setContent(doc.rendered_text || JSON.stringify(doc.content_json, null, 2));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!documentId.trim() || !token) return;
    setApproving(true);
    try {
      await api.approveDocument(token, documentId);
      alert("Документ утверждён!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setApproving(false);
    }
  };

  const handleExport = async (format: string) => {
    if (!documentId.trim() || !token) return;
    try {
      const text = await api.exportDocument(token, documentId, format);
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `document.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Документы</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold mb-3">Загрузить документ</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            placeholder="ID документа"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleLoad}
            disabled={loading || !documentId.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Загрузка..." : "Загрузить"}
          </button>
        </div>
      </div>

      {content && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Содержимое документа</h2>
            <div className="flex gap-2">
              <button
                onClick={() => handleExport("txt")}
                className="px-3 py-1 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Export TXT
              </button>
              <button
                onClick={() => handleExport("docx")}
                className="px-3 py-1 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Export DOCX
              </button>
              <button
                onClick={handleApprove}
                disabled={approving}
                className="px-3 py-1 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {approving ? "Утверждение..." : "Утвердить"}
              </button>
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
              {content}
            </pre>
          </div>
        </div>
      )}

      {!content && (
        <div className="text-center text-gray-500 py-8">
          Сгенерируйте документы из страницы вакансии, затем загрузите их по ID.
        </div>
      )}
    </div>
  );
}
