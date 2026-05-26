from __future__ import annotations

import os

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL


def render_sidebar() -> tuple[str, CareerCopilotApiClient, str | None]:
    st.sidebar.header("Backend")

    api_base_url = st.sidebar.text_input(
        "Базовый URL API",
        value=os.getenv("CAREER_COPILOT_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="Например: http://localhost:8000/api/v1",
    ).strip()

    client = CareerCopilotApiClient(api_base_url=api_base_url)
    token = st.session_state.get("auth_token")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔐 Авторизация")

    if not token:
        auth_mode = st.sidebar.radio(
            "Режим",
            options=["login", "register"],
            horizontal=True,
            format_func=lambda value: "Вход" if value == "login" else "Регистрация",
            key="auth_mode",
        )

        demo_email = os.getenv("DEMO_EMAIL", "demo.candidate@example.com")
        demo_password = os.getenv("DEMO_PASSWORD", "DemoPass123!")

        default_email = demo_email if auth_mode == "login" else ""
        default_password = demo_password if auth_mode == "login" else ""

        email = st.sidebar.text_input(
            "Email",
            value=default_email,
            key=f"auth_email_{auth_mode}",
        )
        password = st.sidebar.text_input(
            "Пароль",
            value=default_password,
            type="password",
            key=f"auth_password_{auth_mode}",
        )

        if auth_mode == "register":
            password_confirm = st.sidebar.text_input(
                "Повторите пароль",
                value="",
                type="password",
                key="auth_password_confirm",
            )
        else:
            password_confirm = password

        if auth_mode == "login":
            button_label = "Войти"
            success_message = "✅ Авторизация успешна"
        else:
            button_label = "Зарегистрироваться"
            success_message = "✅ Пользователь зарегистрирован. Теперь можно войти."

        if st.sidebar.button(button_label, use_container_width=True, type="primary"):
            normalized_email = email.strip().lower()

            if not normalized_email:
                st.sidebar.error("Укажите email.")
            elif not password:
                st.sidebar.error("Укажите пароль.")
            elif auth_mode == "register" and password != password_confirm:
                st.sidebar.error("Пароли не совпадают.")
            else:
                try:
                    if auth_mode == "login":
                        result = client.login(normalized_email, password)
                        st.session_state.auth_token = result.get("access_token")
                        st.session_state.user_email = normalized_email
                        st.sidebar.success(success_message)
                        st.rerun()
                    else:
                        client.register(normalized_email, password)
                        st.sidebar.success(success_message)

                except httpx.HTTPStatusError as exc:
                    if auth_mode == "register" and exc.response.status_code == 409:
                        st.sidebar.error("Пользователь с таким email уже существует.")
                    elif auth_mode == "login" and exc.response.status_code == 401:
                        st.sidebar.error("Неверный email или пароль.")
                    else:
                        st.sidebar.error(f"Backend вернул HTTP {exc.response.status_code}")
                        st.sidebar.code(exc.response.text)
                except httpx.RequestError as exc:
                    st.sidebar.error("Не удалось подключиться к backend.")
                    st.sidebar.code(str(exc))
                except ValueError as exc:
                    st.sidebar.error("Backend вернул неожиданный ответ.")
                    st.sidebar.code(str(exc))
    else:
        st.sidebar.success(f"👤 {st.session_state.get('user_email', 'user')}")
        st.sidebar.caption(f"Токен активен до завершения сессии")
        if st.sidebar.button("Выйти", use_container_width=True):
            st.session_state.pop("auth_token", None)
            st.session_state.pop("user_email", None)
            st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("Проверить соединение", use_container_width=True):
        result = client.check_backend()
        if result.ok:
            st.sidebar.success("✅ Backend доступен")
        else:
            st.sidebar.error(f"❌ {result.error}")

    return api_base_url, client, token
