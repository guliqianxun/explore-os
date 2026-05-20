from __future__ import annotations

import pytest
from django.contrib.auth.models import User


@pytest.fixture(autouse=True)
def default_user(db):
    """Ensure a User with id=1 exists for single-user desktop mode."""
    user, _ = User.objects.get_or_create(
        id=1,
        defaults={"username": "default", "email": "default@local"},
    )
    if not user.has_usable_password():
        user.set_unusable_password()
        user.save()
    return user
