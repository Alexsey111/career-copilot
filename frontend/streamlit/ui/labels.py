from __future__ import annotations


APPLICATION_STATUS_LABELS = {
    "draft": "Черновик",
    "ready": "Готов к отправке",
    "applied": "Отправлен вручную",
    "screening": "Скрининг",
    "interview": "Интервью",
    "rejected": "Отказ",
    "offer": "Оффер",
    "withdrawn": "Отозван",
}

APPLICATION_OUTCOME_LABELS = {
    "rejected": "Отказ",
    "offer": "Оффер",
}

APPLICATION_REMINDER_LABELS = {
    "draft_stale": "Черновик без активности",
    "ready_not_submitted": "Готов к отправке, но не отправлен",
    "follow_up_missing": "Нет follow-up по отклику",
}

DEMO_VACANCY_TITLE_LABELS = {
    "Backend Developer": "Backend-разработчик",
}

DEMO_COMPANY_LABELS = {
    "Test Company": "Тестовая компания",
}

DEMO_LOCATION_LABELS = {
    "Remote": "Удалённо",
}

RISK_LEVEL_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

CONFIDENCE_LEVEL_LABELS = {
    "high": "Высокая уверенность",
    "medium": "Средняя уверенность",
    "low": "Низкая уверенность",
    "needs_review": "Требует проверки",
}

ACTION_SEVERITY_LABELS = {
    "blocker": "Блокер",
    "warning": "Предупреждение",
    "info": "Инфо",
}

ENTITY_TYPE_LABELS = {
    "document": "Документ",
    "interview_prep": "Подготовка к интервью",
}

DOCUMENT_KIND_LABELS = {
    "resume": "Резюме",
    "cover_letter": "Сопроводительное письмо",
}

SEVERITY_TONES = {
    "blocker": {"bg": "#FEE2E2", "fg": "#991B1B"},
    "warning": {"bg": "#FFEDD5", "fg": "#9A3412"},
    "info": {"bg": "#DBEAFE", "fg": "#1D4ED8"},
    "success": {"bg": "#DCFCE7", "fg": "#166534"},
    "neutral": {"bg": "#E5E7EB", "fg": "#374151"},
}

CONFIDENCE_TONES = {
    "high": "success",
    "medium": "warning",
    "low": "warning",
    "needs_review": "blocker",
}

RISK_LEVEL_TONES = {
    "low": "success",
    "medium": "warning",
    "high": "blocker",
}

ACTION_GROUP_ORDER = (
    "Resolve blockers",
    "Review unsupported claims",
    "Prepare interview gaps",
    "Improve confidence",
)

TRUST_PANEL_TEXT_REPLACEMENTS = {
    "Unified review summary from a single backend contract. No internal document or interview JSON is shown here.": (
        "Единая сводка проверки на одном backend-контракте. "
        "Внутренний JSON документов или интервью здесь не показывается."
    ),
    "No generated documents are available yet.": "Пока нет доступных сгенерированных документов.",
    "No active scoped documents available.": "Пока нет активных привязанных документов.",
    "No active document.": "Активный документ отсутствует.",
    "Current active scoped application": "Текущее активное приложение",
    "Active scoped documents": "Активные привязанные документы",
    "Demo scenarios": "Демо-сценарии",
    "Reset and verify commands": "Команды сброса и проверки",
    "Select document": "Выберите документ",
    "Select interview prep session": "Выберите сессию подготовки к интервью",
    "No interview prep sessions are available yet.": "Пока нет доступных сессий подготовки к интервью.",
    "No valid interview prep sessions are available.": "Нет валидных сессий подготовки к интервью.",
    "Entity id is missing.": "Не указан идентификатор сущности.",
    "Backend returned an unexpected response": "Backend вернул неожиданный ответ",
    "Backend returned an unexpected review summary payload": "Backend вернул неожиданный payload сводки проверки",
    "Unable to connect to backend": "Не удалось подключиться к backend",
    "No blockers detected. All critical claims confirmed. Interview prep readiness acceptable.": (
        "Блокеров не обнаружено. Все критичные утверждения подтверждены. "
        "Подготовка к интервью приемлема."
    ),
    "No blockers detected.": "Блокеров не обнаружено.",
    "No warnings detected.": "Предупреждений не обнаружено.",
    "All critical claims confirmed.": "Все критичные утверждения подтверждены.",
    "Interview prep readiness acceptable.": "Подготовка к интервью приемлема.",
    "No selected evidence was returned by the backend.": "Backend не вернул выбранные доказательства.",
    "No recommended actions. The review looks stable.": "Рекомендованных действий нет. Проверка выглядит стабильной.",
    "No confirmed Python evidence": "Нет подтверждённых доказательств по Python",
    "No confirmed Kubernetes evidence": "Нет подтверждённых доказательств по Kubernetes",
    "How would you honestly answer about the weak area: No confirmed Python evidence": (
        "Как вы честно ответите на вопрос о слабой зоне: Нет подтверждённых доказательств по Python"
    ),
    "How would you honestly answer about the weak area: No confirmed Kubernetes evidence": (
        "Как вы честно ответите на вопрос о слабой зоне: Нет подтверждённых доказательств по Kubernetes"
    ),
    "Resolve blockers": "Устранить блокеры",
    "Review unsupported claims": "Проверить неподтверждённые утверждения",
    "Prepare interview gaps": "Подготовить ответы на пробелы",
    "Improve confidence": "Повысить уверенность",
    "Resolve blocker": "Устранить блокер",
    "Interview Prep": "Подготовка к интервью",
    "Interview Question": "Вопрос интервью",
    "Prepare a careful gap-risk response": "Подготовьте аккуратный ответ на вопрос о пробеле",
    "Strong evidence": "Сильные доказательства",
    "Medium evidence": "Средние доказательства",
    "No confirmed evidence": "Нет подтверждённых доказательств",
    "Show evidence provenance": "Показать provenance доказательств",
    "Document": "Документ",
    "Interview prep": "Подготовка к интервью",
    "draft": "черновик",
    "Target id": "целевой ID",
    "Resume": "Резюме",
    "Cover Letter": "Сопроводительное письмо",
    "Claims requiring confirmation": "Утверждения, требующие подтверждения",
    "Gap-risk items": "Пункты с риском по пробелам",
    "Selected evidence": "Выбранные доказательства",
    "Recommended actions": "Рекомендованные действия",
    "Blockers": "Блокеры",
    "Warnings": "Предупреждения",
    "Risk": "Риск",
    "Ready": "Готово",
    "Human review": "Человеческая проверка",
    "Confidence": "Уверенность",
    "Required": "Требуется",
    "Not required": "Не требуется",
    "Ready": "Готово",
    "Blocked": "Есть блокировка",
    "No items.": "Элементов нет.",
    "Source": "Источник",
    "Generation mode": "Режим генерации",
    "Confidence level": "Уровень уверенности",
    "Requires human review": "Требуется ручная проверка",
    "Analysis id": "ID анализа",
    "Application id": "ID заявки",
    "Vacancy id": "ID вакансии",
    "Document id": "ID документа",
    "Question generation mode": "Режим генерации вопросов",
    "Selected achievement ids": "Выбранные ID достижений",
    "Selected evidence ids": "Выбранные ID доказательств",
    "Competency sources": "Источники компетенций",
    "Question source counts": "Количество источников вопросов",
    "target id": "целевой ID",
    "Backend": "Backend",
    "Ready": "Готово",
    "No active scoped application found yet.": "Активное приложение пока не найдено.",
    "No active scoped documents available.": "Активные привязанные документы пока не найдены.",
}
