"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Info } from "lucide-react";

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
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-full mb-6" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const allRequiredGranted = consents
    .filter((c) => c.required)
    .every((c) => c.granted);

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-2">Согласия</h1>
      <p className="text-[color:var(--brand-teal-60)] mb-6">
        Управляйте своими согласиями на обработку данных и использование AI.
      </p>

      {!allRequiredGranted && (
        <Alert className="mb-6 border-yellow-200 bg-yellow-50 text-yellow-800">
          <AlertCircle />
          <AlertDescription>
            Для полного использования сервиса необходимо предоставить обязательные
            согласия (отмечены звездочкой).
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-4">
        {consents.map((consent) => (
          <Card key={consent.consent_type}>
            <CardContent className="pt-4">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">
                    {CONSENT_ICONS[consent.consent_type] || "📋"}
                  </span>
                  <div>
                    <h3 className="font-semibold">
                      {consent.description}
                      {consent.required && (
                        <span className="text-destructive ml-1">*</span>
                      )}
                    </h3>
                    <p className="text-xs text-[color:var(--brand-teal-60)] mt-1">
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
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRevoke(consent.consent_type)}
                      disabled={saving === consent.consent_type || consent.required}
                    >
                      {saving === consent.consent_type
                        ? "..."
                        : consent.required
                        ? "Обязательное"
                        : "Отозвать"}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => handleGrant(consent.consent_type)}
                      disabled={saving === consent.consent_type}
                    >
                      {saving === consent.consent_type ? "..." : "Предоставить"}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-6 bg-[color:var(--brand-teal-5)]">
        <CardContent className="pt-4">
          <p className="text-xs text-[color:var(--brand-teal-60)] flex items-start gap-2">
            <Info className="size-4 shrink-0 mt-0.5" />
            <span>
              * Обязательные согласия необходимы для базовой работы сервиса. Вы не
              можете отозвать обязательные согласия, пока используете сервис.
              Отзыв необязательных согласий может ограничить некоторые функции.
            </span>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
