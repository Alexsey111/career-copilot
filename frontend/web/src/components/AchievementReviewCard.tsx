"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToastCtx } from "@/contexts/ToastContext";
import type { AchievementItem } from "@/lib/types";

const STATUSES = [
  { value: "confirmed", label: "Подтверждено" },
  { value: "needs_confirmation", label: "Требует подтверждения" },
  { value: "unverifiable", label: "Невозможно проверить" },
  { value: "rejected", label: "Отклонено" },
  { value: "user_provided", label: "Указано пользователем" },
];

const STATUS_COLORS: Record<string, string> = {
  confirmed: "bg-[color:var(--brand-lime-soft)] text-[color:var(--brand-teal)]",
  needs_confirmation: "bg-yellow-100 text-yellow-800",
  unverifiable: "bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)]",
  rejected: "bg-[color:var(--brand-ink-10)] text-[color:var(--brand-ink)]",
  user_provided: "bg-[color:var(--brand-teal-5)] text-[color:var(--brand-teal)]",
};

/**
 * Карточка достижения с human-in-the-loop редактированием:
 * title/текст (situation/task/action/result/metric_text), статус, evidence_note,
 * сохранение через PATCH /profile/achievements/{id}/review.
 * Пока достижение не confirmed, оно не попадает в детерминированное резюме.
 */
export default function AchievementReviewCard({
  token,
  achievement,
  onSaved,
}: {
  token: string;
  achievement: AchievementItem;
  onSaved?: () => void;
}) {
  const toast = useToastCtx();
  const [title, setTitle] = useState(achievement.title ?? "");
  const [situation, setSituation] = useState(achievement.situation ?? "");
  const [task, setTask] = useState(achievement.task ?? "");
  const [action, setAction] = useState(achievement.action ?? "");
  const [result, setResult] = useState(achievement.result ?? "");
  const [metricText, setMetricText] = useState(achievement.metric_text ?? "");
  const [factStatus, setFactStatus] = useState(achievement.fact_status ?? "needs_confirmation");
  const [evidenceNote, setEvidenceNote] = useState(achievement.evidence_note ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim()) {
      toast.error("Заголовок достижения не может быть пустым");
      return;
    }
    setSaving(true);
    try {
      await api.reviewAchievement(token, achievement.id, {
        title: title.trim(),
        situation: situation.trim() || undefined,
        task: task.trim() || undefined,
        action: action.trim() || undefined,
        result: result.trim() || undefined,
        metric_text: metricText.trim() || undefined,
        fact_status: factStatus,
        evidence_note: evidenceNote.trim() || undefined,
      });
      toast.success("Достижение сохранено");
      onSaved?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  };

  const input = "w-full px-2 py-1 border border-[color:var(--brand-teal-20)] rounded text-sm";

  return (
    <div className="border border-[color:var(--brand-teal-20)] rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[factStatus] ?? "bg-[color:var(--brand-teal-5)]"}`}>
          {STATUSES.find((s) => s.value === factStatus)?.label ?? factStatus}
        </span>
        <span className="text-xs text-[color:var(--brand-teal-40)]">{achievement.source ?? ""}</span>
      </div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Заголовок достижения"
        className={`${input} font-medium`}
      />
      <textarea
        value={situation}
        onChange={(e) => setSituation(e.target.value)}
        placeholder="Ситуация (Situation)"
        rows={2}
        className={input}
      />
      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        placeholder="Задача (Task)"
        rows={2}
        className={input}
      />
      <textarea
        value={action}
        onChange={(e) => setAction(e.target.value)}
        placeholder="Действие (Action)"
        rows={2}
        className={input}
      />
      <textarea
        value={result}
        onChange={(e) => setResult(e.target.value)}
        placeholder="Результат (Result)"
        rows={2}
        className={input}
      />
      <input
        value={metricText}
        onChange={(e) => setMetricText(e.target.value)}
        placeholder="Метрика (например: +30% к скорости)"
        className={input}
      />
      <select
        value={factStatus}
        onChange={(e) => setFactStatus(e.target.value)}
        className={input}
      >
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <input
        value={evidenceNote}
        onChange={(e) => setEvidenceNote(e.target.value)}
        placeholder="Заметка/источник"
        className={input}
      />
      <button
        onClick={handleSave}
        disabled={saving}
        className="px-3 py-1 text-sm bg-[color:var(--brand-lime)] text-[color:var(--brand-teal)] font-semibold rounded hover:bg-[#b8e85c] disabled:opacity-50"
      >
        {saving ? "Сохранение…" : "Сохранить"
        }
      </button>
    </div>
  );
}