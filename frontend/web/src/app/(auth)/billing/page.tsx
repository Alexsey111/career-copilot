"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import UsageMeter from "@/components/UsageMeter";
import type { MySubscriptionResponse } from "@/lib/types";

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

  if (loading) return <div className="text-gray-500">Загрузка…</div>;

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Биллинг</h1>

      {sub && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold capitalize">{sub.plan}</h2>
              <p className="text-sm text-gray-500">
                Статус: {sub.status ?? "—"}
              </p>
            </div>
            {sub.current_period_end && (
              <p className="text-xs text-gray-500">
                до {new Date(sub.current_period_end).toLocaleDateString("ru")}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mb-6">
            <button
              onClick={handleCheckout}
              disabled={busy}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
            >
              Улучшить план
            </button>
            <button
              onClick={handlePortal}
              disabled={busy}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 text-sm"
            >
              Управление подпиской
            </button>
          </div>

          <h3 className="font-medium mb-3">Использование квот</h3>
          {sub.usage && sub.usage.length > 0 ? (
            <div className="space-y-3">
              {sub.usage.map((u, i) => (
                <UsageMeter key={i} usage={u} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Квоты не настроены для этого плана.</p>
          )}

          {sub.canceled_at && (
            <p className="text-xs text-red-600 mt-4">
              Подписка отменена: {new Date(sub.canceled_at).toLocaleDateString("ru")}
            </p>
          )}
        </div>
      )}

      {!sub && (
        <p className="text-gray-500">Подписка не найдена.</p>
      )}
    </div>
  );
}