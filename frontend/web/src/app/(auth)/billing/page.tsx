"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import UsageMeter from "@/components/UsageMeter";
import type { MySubscriptionResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

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
