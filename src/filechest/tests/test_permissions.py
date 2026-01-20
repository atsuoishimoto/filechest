from django.contrib.auth.models import AnonymousUser

from filechest.models import Role
from filechest.permissions import get_user_role, can_view, can_edit


def test_superuser_always_editor(volume, superuser):
    """Superuser should always have editor role."""
    assert get_user_role(superuser, volume) == Role.EDITOR
    assert can_edit(superuser, volume) is True
    assert can_view(superuser, volume) is True


def test_editor_permission(volume, editor_user):
    """User with editor permission should have editor role."""
    assert get_user_role(editor_user, volume) == Role.EDITOR
    assert can_edit(editor_user, volume) is True
    assert can_view(editor_user, volume) is True


def test_viewer_permission(volume, viewer_user):
    """User with viewer permission should have viewer role."""
    assert get_user_role(viewer_user, volume) == Role.VIEWER
    assert can_edit(viewer_user, volume) is False
    assert can_view(viewer_user, volume) is True


def test_no_permission(volume, user):
    """User without permission should have no access."""
    assert get_user_role(user, volume) is None
    assert can_edit(user, volume) is False
    assert can_view(user, volume) is False


def test_public_read_anonymous(public_volume):
    """Anonymous user should have viewer access to public volume."""
    anon = AnonymousUser()
    assert get_user_role(anon, public_volume) == Role.VIEWER
    assert can_view(anon, public_volume) is True
    assert can_edit(anon, public_volume) is False


def test_public_read_authenticated_no_permission(public_volume, user):
    """Authenticated user without permission should have viewer access to public volume."""
    assert get_user_role(user, public_volume) == Role.VIEWER
    assert can_view(user, public_volume) is True


def test_private_volume_anonymous(volume):
    """Anonymous user should have no access to private volume."""
    anon = AnonymousUser()
    assert get_user_role(anon, volume) is None
    assert can_view(anon, volume) is False
