"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

interface Consent {
  consent_type: string;
  description: string;
  required: boolean;
  version: string;
  granted: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

const CONSENT_ICONS: Record<string, string> = {
  data_processing: "🔐",
  ai_generation: "🤖",
  profile_storage: "💾",
  analytics_tracking: "📊",
  third_party_sharing: "🔗",
};

export default function ConsentPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [consents, setConsents] = useState<Consent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      api
        .listConsents(token)
        .then((data) => setConsents(data as Consent[]))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [token]);

  const handleGrant = async (consentType: string) => {
    if (!token) return;
    setSaving(consentType);
    try {
      await api.grantConsent(token, consentType);
      setConsents((prev) =>
        prev.map((c) =>
          c.consent_type === consentType
            ? { ...c, granted: true, granted_at: new Date().toISOString() }
            : c
        )
      );
      toast.success("Согласие предоставлено");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(null);
    }
  };

  const handleRevoke = async (consentType: string) => {
    if (!token) return;
    setSaving(consentType);
    try {
      await api.revokeConsent(token, consentType);
      setConsents((prev) =>
        prev.map((c) =>
          c.consent_type === consentType
            ? { ...c, granted: false, revoked_at: new Date().toISOString() }
            : c
        )
      );
      toast.info("Согласие отозвано");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl">
        <div className="text-gray-500">Загрузка...</div>
      </div>
    );
  }

  const allRequiredGranted = consents
    .filter((c) => c.required)
    .every((c) => c.granted);

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-2">Согласия</h1>
      <p className="text-gray-600 mb-6">
        Управляйте своими согласиями на обработку данных и использование AI.
      </p>

      {!allRequiredGranted && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
          <p className="text-sm text-yellow-800">
            Для полного использования сервиса необходимо предоставить обязательные
            согласия (отмечены звездочкой).
          </p>
        </div>
      )}

      <div className="space-y-4">
        {consents.map((consent) => (
          <div
            key={consent.consent_type}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-5"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <span className="text-2xl">
                  {CONSENT_ICONS[consent.consent_type] || "📋"}
                </span>
                <div>
                  <h3 className="font-semibold">
                    {consent.description}
                    {consent.required && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    Версия: {consent.version}
                    {consent.granted_at && (
                      <span>
                        {" "}
                        • Предоставлено:{" "}
                        {new Date(consent.granted_at).toLocaleDateString("ru")}
                      </span>
                    )}
                    {consent.revoked_at && (
                      <span>
                        {" "}
                        • Отозвано:{" "}
                        {new Date(consent.revoked_at).toLocaleDateString("ru")}
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div>
                {consent.granted ? (
                  <button
                    onClick={() => handleRevoke(consent.consent_type)}
                    disabled={saving === consent.consent_type || consent.required}
                    className="px-3 py-1 text-sm border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {saving === consent.consent_type
                      ? "..."
                      : consent.required
                      ? "Обязательное"
                      : "Отозвать"}
                  </button>
                ) : (
                  <button
                    onClick={() => handleGrant(consent.consent_type)}
                    disabled={saving === consent.consent_type}
                    className="px-3 py-1 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {saving === consent.consent_type ? "..." : "Предоставить"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 p-4 bg-gray-50 rounded-xl">
        <p className="text-xs text-gray-500">
          * Обязательные согласия необходимы для базовой работы сервиса. Вы не
          можете отозвать обязательные согласия, пока используете сервис.
          Отзыв необязательных согласий может ограничить некоторые функции.
        </p>
      </div>
    </div>
  );
}
