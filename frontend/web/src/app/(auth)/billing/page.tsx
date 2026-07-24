"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import UsageMeter from "@/components/UsageMeter";
import type { MySubscriptionResponse, UserAIProvider } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

export default function BillingPage() {
  const { token } = useAuth();
  const toast = useToastCtx();
  const [sub, setSub] = useState<MySubscriptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = () => {
    if (!token) return;
    api
      .getSubscription(token)
      .then((r) => setSub(r as MySubscriptionResponse))
      .finally(() => setLoading(false));
  };

  useEffect(reload, [token]);

  const handleCheckout = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const res = (await api.createCheckout(token, {})) as any;
      if (res?.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        toast.error("Не получен URL оплаты");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Checkout недоступен");
    } finally {
      setBusy(false);
    }
  };

  const handlePortal = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const res = (await api.createPortalSession(token)) as any;
      if (res?.portal_url) {
        window.location.href = res.portal_url;
      } else {
        toast.error("Не получен URL портала");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Портал недоступен");
    } finally {
      setBusy(false);
    }
  };

  const handleAIProviderChange = async (value: string) => {
    if (!token) return;
    const previous = sub?.ai_provider;
    // Оптимистичное обновление, чтобы Select не «дёргался» при ошибке.
    if (sub) {
      setSub({ ...sub, ai_provider: value as UserAIProvider });
    }
    try {
      const updated = (await api.updateSubscription(token, {
        ai_provider: value,
      })) as MySubscriptionResponse;
      setSub(updated);
      const label =
        value === "default"
          ? "по умолчанию сервера"
          : ({ gigachat: "GigaChat", openai: "OpenAI", deepseek: "DeepSeek" } as const)[
              value as "gigachat" | "openai" | "deepseek"
            ] ?? value;
      toast.success(`AI-провайдер: ${label}`);
    } catch (err) {
      // Откат к предыдущему значению.
      if (sub && previous) {
        setSub({ ...sub, ai_provider: previous });
      }
      toast.error(
        err instanceof Error ? err.message : "Не удалось обновить провайдера"
      );
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl space-y-4">
        <h1 className="text-2xl font-bold">Биллинг</h1>
        <Skeleton className="h-48" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Биллинг</h1>

      {sub && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="capitalize">{sub.plan}</CardTitle>
                <CardDescription>Статус: {sub.status ?? "—"}</CardDescription>
              </div>
              {sub.current_period_end && (
                <p className="text-xs text-muted-foreground">
                  до {new Date(sub.current_period_end).toLocaleDateString("ru")}
                </p>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleCheckout} disabled={busy}>
                Улучшить план
              </Button>
              <Button variant="outline" onClick={handlePortal} disabled={busy}>
                Управление подпиской
              </Button>
            </div>

            <div>
              <h3 className="font-medium mb-3">Использование квот</h3>
              {sub.usage && sub.usage.length > 0 ? (
                <div className="space-y-3">
                  {sub.usage.map((u, i) => (
                    <UsageMeter key={i} usage={u} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Квоты не настроены для этого плана.
                </p>
              )}
            </div>

            <div>
              <h3 className="font-medium mb-3">AI-провайдер</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Выберите, через какую языковую модель адаптировать тексты к
                вакансии. Модель фиксирована для каждого провайдера — выбор
                только между поставщиками.
              </p>
              <div className="flex items-center gap-3">
                <Label htmlFor="ai-provider" className="sr-only">
                  AI-провайдер
                </Label>
                <Select
                  value={sub.ai_provider ?? "default"}
                  onValueChange={handleAIProviderChange}
                  disabled={busy}
                >
                  <SelectTrigger id="ai-provider" className="w-64" aria-label="AI-провайдер">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">По умолчанию сервера</SelectItem>
                    <SelectItem value="gigachat">GigaChat</SelectItem>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="deepseek">DeepSeek</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {sub.canceled_at && (
              <p className="text-xs text-destructive">
                Подписка отменена: {new Date(sub.canceled_at).toLocaleDateString("ru")}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {!sub && <p className="text-muted-foreground">Подписка не найдена.</p>}
    </div>
  );
}
