# scripts\temp_debug_profile_structuring.py

from app.services.profile_structuring_service import ProfileStructuringService

text = '''
Перминов Алексей
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, ChatGPT, API, SQL,
Анализ данных, Tensorflow, автоматизация workflow.
Желаемая должность
Prompt Engineering, Data Science
Прошел 3 стажировки по направлению Data Science:
1. Создание ИИ-системы
для мониторинга безопасности в пансионатах для пожилых
2. Автоматизированный ИИ-контроль качества
ПВХ оконных изделий по изображениям и видео
3. Prompt Engineering
Создание нейроассистентов, чат-боты, промптинг
Курсы
Python с нуля
'''
service = ProfileStructuringService()
draft = service._build_draft(text)
print('EVIDENCE')
for item in draft.evidence_snippets:
    print(repr(item.title), item.category, item.skills)
print('PROJECTS')
for item in draft.projects:
    print(repr(item.title), item.category)
print('INTERNSHIPS')
for item in draft.internships:
    print(repr(item.title), item.category)
