from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.dependencies import get_current_dev_user
from app.main import app
from app.models import User


pytestmark = pytest.mark.asyncio


API_PREFIX = "/api/v1"


async def test_file_access_is_scoped_to_current_user(client, db_session, test_user):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    file_id = upload_response.json()["id"]

    other_user = User(
        email="other@local.test",
        auth_provider="test",
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    def override_other_user():
        return SimpleNamespace(id=other_user.id)

    app.dependency_overrides[get_current_dev_user] = override_other_user

    forbidden_response = await client.get(f"{API_PREFIX}/files/{file_id}")
    assert forbidden_response.status_code == 404, forbidden_response.text
    assert forbidden_response.json()["detail"] == "file not found"

    def override_original_user():
        return SimpleNamespace(id=test_user.id)

    app.dependency_overrides[get_current_dev_user] = override_original_user