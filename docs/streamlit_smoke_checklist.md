# Streamlit Smoke Checklist

Use this checklist before or during a manual Streamlit demo.

## 1. Startup

- [ ] Streamlit opens without traceback.
- [ ] Login and registration modes load in the sidebar.
- [ ] Registration creates a new user.
- [ ] Login form works for an existing user.
- [ ] Demo user can log in.
- [ ] Connection check passes.

## 2. Main Tabs

- [ ] Main tabs are readable and mostly Russian-facing.
- [ ] `Состояние системы` shows backend, DB, demo state, counts, and current application.
- [ ] `Панель доверия` shows seeded active documents or interview prep state.
- [ ] `Проверка документов` shows a selected document when seeded docs exist.
- [ ] `Подготовка к интервью` shows sessions and readiness details.
- [ ] `Источники доказательств` shows the evidence catalog and insights.
- [ ] `Стратегия карьеры` shows career insights without noisy raw JSON in the main view.

## 3. Trust / Review UX

- [ ] Risk badges are readable.
- [ ] Confidence badges are readable.
- [ ] Blockers and warnings are visible.
- [ ] Recommended actions are visible.
- [ ] Empty states are in Russian.
- [ ] Trust Panel and Document Review Workspace fall back to `/health/diagnostics` when session state is empty.

## 4. Noise Check

- [ ] No raw JSON is shown where it blocks the operator view.
- [ ] No obvious English-only heading remains in the main tabs.
- [ ] No broken spinner or crash is visible.

## 5. Manual E2E

- [ ] Upload resume.
- [ ] Import profile.
- [ ] Create vacancy.
- [ ] Generate resume.
- [ ] Review claims.
- [ ] Generate cover letter.
- [ ] Open Trust Panel.
- [ ] Create application.
- [ ] Run interview prep.
- [ ] Answer questions.
- [ ] Export documents.
