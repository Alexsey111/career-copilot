from app.services.profile_structuring_service import ProfileStructuringService


def test_structured_profile_extracts_contacts_into_response_shape() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Иванов Иван
ivan.ivanov@example.com
+7 (903) 111-22-33
https://github.com/ivanov
@ivanov_dev
г. Москва
Профессиональные навыки
Python, FastAPI, SQL
Желаемая должность
Backend Developer
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    contacts = draft.contacts.as_dict()

    assert contacts["email"] == "ivan.ivanov@example.com"
    assert contacts["phone"] == "+7 (903) 111-22-33"
    assert contacts["github"] == "https://github.com/ivanov"
    assert contacts["telegram"] == "@ivanov_dev"

