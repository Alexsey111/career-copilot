"""Запуск uvicorn с WindowsSelectorEventLoopPolicy (обход psycopg/Proactor issue).

Использовать ТОЛЬКО для локальной отладки на Windows, пока не перешли на
asyncio.run() на уровне приложения. Не для production.
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7000, reload=False)
