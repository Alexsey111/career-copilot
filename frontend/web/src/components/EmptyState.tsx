"use client";

import { useRouter } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
}

/**
 * Универсальный EmptyState — используется на /applications, /career, /interview,
 * /documents и /vacancies (когда поиск не дал результатов).
 *
 * Иконка + заголовок + описание + опциональный CTA. Внутри Card, чтобы выглядело
 * как часть основного потока (а не «плавающее» сообщение).
 */
export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  const router = useRouter();
  const handleAction = action?.onClick ?? (action?.href ? () => router.push(action.href!) : undefined);

  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center text-center py-12 px-6">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal-60)] mb-4">
          <Icon className="size-6" />
        </div>
        <h3 className="text-base font-semibold mb-1">{title}</h3>
        {description && (
          <p className="text-sm text-[color:var(--brand-teal-60)] max-w-sm mb-4">{description}</p>
        )}
        {action && (
          <Button onClick={handleAction} variant="default" size="sm">
            {action.label}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
