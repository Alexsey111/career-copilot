"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToastCtx } from "@/contexts/ToastContext";
import { useSessionDocs } from "@/contexts/SessionDocumentsContext";
import { api } from "@/lib/api";
import DocumentActions from "@/components/DocumentActions";
import type { ActiveDocumentResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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

      {loading && (
        <div className="mb-4 space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {/* Активные документы */}
      {active.length > 0 && (
        <div className="mb-6">
          <h2 className="font-semibold mb-3">Активные документы</h2>
          <div className="space-y-3">
            {active.map((d) => (
              <Card key={d.id}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle>{d.label}</CardTitle>
                      <CardDescription>
                        {d.id.slice(0, 8)}… · статус: {d.reviewStatus ?? "—"} · {d.isActive ? "активен" : "не активен"}
                      </CardDescription>
                    </div>
                    <Link
                      href={`/documents/${d.id}`}
                      className={cn(buttonVariants({ variant: "link" }))}
                    >
                      Открыть workspace →
                    </Link>
                  </div>
                </CardHeader>
                <CardContent>
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
                </CardContent>
              </Card>
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
                className="block rounded-lg hover:bg-muted/50 transition-colors"
              >
                <Card>
                  <CardContent className="flex items-center gap-2 py-3">
                    <span className="text-sm text-foreground">{d.label}</span>
                    <span className="text-xs text-muted-foreground ml-2">{d.id.slice(0, 8)}…</span>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Ручной ввод ID */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Открыть по ID</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              type="text"
              value={manualId}
              onChange={(e) => setManualId(e.target.value)}
              placeholder="ID документа"
              className="flex-1"
            />
            {manualId.trim() && (
              <Link
                href={`/documents/${manualId.trim()}`}
                className={cn(buttonVariants({ variant: "default" }))}
              >
                Открыть
              </Link>
            )}
          </div>
        </CardContent>
      </Card>

      {active.length === 0 && recentOnly.length === 0 && !loading && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Сгенерируйте резюме или письмо из страницы вакансии — они появятся здесь.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
