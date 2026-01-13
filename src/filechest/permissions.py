from django.conf import settings

from .models import Volume, VolumePermission, Role


def get_user_role(user, volume: Volume) -> str | None:
    """
    Get user's role for the given Volume.

    Returns:
        'viewer', 'editor', or None (no access)
    """
    # Adhoc mode: everyone gets editor access
    if getattr(settings, "FILECHEST_ADHOC_MODE", False):
        return Role.EDITOR

    # superuser always has editor access
    if user.is_authenticated and user.is_superuser:
        return Role.EDITOR

    # Authenticated user: check VolumePermission
    if user.is_authenticated:
        try:
            perm = VolumePermission.objects.get(user=user, volume=volume)
            return perm.role
        except VolumePermission.DoesNotExist:
            pass  # Fall through to check public_read

    # No VolumePermission: check public_read
    return Role.VIEWER if volume.public_read else None


def can_edit(user, volume: Volume) -> bool:
    """Check if user has edit permission."""
    return get_user_role(user, volume) == Role.EDITOR


def can_view(user, volume: Volume) -> bool:
    """Check if user has view permission."""
    return get_user_role(user, volume) in (Role.VIEWER, Role.EDITOR)
