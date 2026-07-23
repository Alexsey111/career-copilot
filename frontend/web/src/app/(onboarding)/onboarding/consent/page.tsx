"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ShieldCheck, AlertTriangle, XCircle } from "lucide-react";

interface Consent {
  consent_type: string;
  description: string;
  required: boolean;
  version: string;
  granted: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

const TYPE_ICONS: Record<string, string> = {
  data_processing: "🔐",
  ai_generation: "🤖",
  profile_storage: "💾",
  analytics_tracking: "📊",
  third_party_sharing: "🔗",
};

export default function OnboardingConsentPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const toast = useToastCtx();
  const [consents, setConsents] = useState<Consent[]>([]);
  const [loading, setLoading] = useState(true);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  // Двухэкранный flow: сначала чекбоксы ("принять/отклонить"),
  // при отказе — экран apology с кнопкой выхода.
  const [declined, setDeclined] = useState(false);

  useEffect(() => {
    // Ждём окончания auth-bootstrap: пока AuthProvider грузит /auth/me,
    // user === null и isLoading === true. Без этой проверки мы бы
    // сразу редиректили на /login при первом рендере.
    if (isLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }
    const token = localStorage.getItem("auth_token");
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .listConsents(token)
      .then((data) => {
        const list = data as Consent[];
        setConsents(list);
        // Чекбоксы обязательных согласий: active by default
        // (если ранее не было явного отказа). Если согласие уже granted — true.
        const initial: Record<string, boolean> = {};
        for (const c of list) {
          if (c.required) {
            initial[c.consent_type] = c.granted || !c.revoked_at;
          } else {
            initial[c.consent_type] = c.granted;
          }
        }
        setAccepted(initial);
      })
      .catch((err) => {
        toast.error("Не удалось загрузить согласия: " + (err?.message || ""));
      })
      .finally(() => setLoading(false));
  }, [user, isLoading, router, toast]);

  const requiredConsents = consents.filter((c) => c.required);
  const allRequiredAccepted = requiredConsents.every((c) => accepted[c.consent_type]);

  const handleAccept = async () => {
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    if (!allRequiredAccepted) {
      // Сработает ветка decline — сразу показываем apology
      setDeclined(true);
      return;
    }
    setSaving(true);
    try {
      for (const c of consents) {
        const shouldBeGranted = accepted[c.consent_type];
        if (shouldBeGranted && !c.granted) {
          await api.grantConsent(token, c.consent_type);
        } else if (!shouldBeGranted && c.granted) {
          await api.revokeConsent(token, c.consent_type);
        }
      }
      toast.success("Согласия сохранены");
      router.push("/profile");
    } catch (err: any) {
      toast.error("Ошибка: " + (err?.message || ""));
    } finally {
      setSaving(false);
    }
  };

  const handleDecline = () => {
    setDeclined(true);
  };

  const handleExit = () => {
    logout();
    router.push("/login");
  };

  if (loading) {
    return (
      <Card className="w-full max-w-2xl">
        <CardContent className="py-8 text-center text-muted-foreground">
          Загрузка…
        </CardContent>
      </Card>
    );
  }

  // Экран apology: пользователь не принял обязательные согласия.
  if (declined) {
    return (
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-3">
            <XCircle className="w-8 h-8 text-red-600" />
          </div>
          <CardTitle className="text-2xl">Сервис недоступен без согласия</CardTitle>
          <CardDescription>
            Для работы AI Career Copilot необходимо ваше согласие на обработку
            персональных данных и использование AI в соответствии с ФЗ-152.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert className="border-amber-200 bg-amber-50">
            <AlertTriangle className="text-amber-600" />
            <AlertTitle className="text-amber-900">Что это значит</AlertTitle>
            <AlertDescription className="text-amber-800">
              Без обязательных согласий мы не сможем сохранять ваше резюме,
              вакансии и сгенерированные документы. Это требование закона, а
              не наше решение.
            </AlertDescription>
          </Alert>
          <p className="text-sm text-muted-foreground text-center">
            Извините, что не можем быть полезными. Если передумаете — зарегистрируйтесь снова
            и примите согласия на первом экране.
          </p>
          <div className="flex flex-col gap-2">
            <Button onClick={handleExit} variant="default" size="lg">
              Выйти
            </Button>
            <Button
              onClick={() => setDeclined(false)}
              variant="ghost"
              size="sm"
            >
              ← Вернуться к согласиям
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-primary" />
          </div>
          <div>
            <CardTitle className="text-2xl">Прежде чем начать</CardTitle>
            <CardDescription>
              Шаг 1 из 1 — согласия на обработку данных
            </CardDescription>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-2">
          AI Career Copilot обрабатывает ваши персональные данные в соответствии
          с ФЗ-152 «О персональных данных». Пожалуйста, ознакомьтесь с условиями
          и подтвердите согласие.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {consents.map((c) => (
            <div
              key={c.consent_type}
              className={`flex items-start gap-3 p-3 border rounded-lg ${
                c.required
                  ? "border-primary/30 bg-primary/5"
                  : "border-border"
              }`}
            >
              <Checkbox
                id={`consent-${c.consent_type}`}
                checked={!!accepted[c.consent_type]}
                onCheckedChange={(checked) =>
                  setAccepted((prev) => ({
                    ...prev,
                    [c.consent_type]: checked === true,
                  }))
                }
                className="mt-0.5"
              />
              <div className="flex-1">
                <Label
                  htmlFor={`consent-${c.consent_type}`}
                  className="cursor-pointer flex items-center gap-2"
                >
                  <span className="text-lg">
                    {TYPE_ICONS[c.consent_type] || "📋"}
                  </span>
                  <span className="font-medium">
                    {c.description}
                    {c.required && (
                      <span className="text-destructive ml-1" title="Обязательное">
                        *
                      </span>
                    )}
                  </span>
                </Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Версия: {c.version}
                  {c.required && (
                    <span className="ml-2 text-destructive">
                      • обязательно для работы сервиса
                    </span>
                  )}
                </p>
              </div>
            </div>
          ))}
        </div>

        <Alert className="border-blue-200 bg-blue-50">
          <ShieldCheck className="text-blue-600" />
          <AlertDescription className="text-blue-900 text-sm">
            <strong>Обязательные согласия</strong> отмечены звёздочкой и активны
            по умолчанию. Снимая галочку, вы отказываетесь от сервиса — мы
            не сможем хранить и обрабатывать ваши данные.
          </AlertDescription>
        </Alert>

        <div className="flex flex-col gap-2 pt-2">
          <Button
            onClick={handleAccept}
            disabled={saving}
            size="lg"
            className="w-full"
          >
            {saving
              ? "Сохранение..."
              : allRequiredAccepted
              ? "Принять и продолжить →"
              : "Принять выбранные"}
          </Button>
          <Button
            onClick={handleDecline}
            variant="ghost"
            size="sm"
            disabled={saving}
          >
            Я не согласен(на) с обязательными условиями
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center pt-2">
          Вы сможете изменить согласия в любое время в разделе{" "}
          <button
            onClick={() => router.push("/consent")}
            className="underline hover:text-foreground"
          >
            «Согласия»
          </button>{" "}
          в боковом меню.
        </p>
      </CardContent>
    </Card>
  );
}
