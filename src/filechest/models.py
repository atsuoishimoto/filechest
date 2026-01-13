from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Role(models.TextChoices):
    VIEWER = "viewer", _("Viewer")
    EDITOR = "editor", _("Editor")


class Volume(models.Model):
    """Root directory for file management."""

    name = models.SlugField(
        max_length=100,
        unique=True,
        help_text=_("Unique identifier (alphanumeric and hyphens only)"),
    )
    verbose_name = models.CharField(max_length=200, help_text=_("Display name"))
    path = models.CharField(
        max_length=500, unique=True, help_text=_("Absolute path on the filesystem")
    )
    public_read = models.BooleanField(
        default=False, help_text=_("Allow public read access (no login required)")
    )
    max_file_size = models.PositiveBigIntegerField(
        default=10 * 1024 * 1024,  # 10MB
        help_text=_("Maximum file size for uploads in bytes"),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Volume")
        verbose_name_plural = _("Volumes")

    def __str__(self):
        return self.verbose_name

    @property
    def is_s3(self):
        return self.path.startswith("s3://")


class VolumePermission(models.Model):
    """Per-user permission for a Volume."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="volume_permissions"
    )
    volume = models.ForeignKey(
        Volume, on_delete=models.CASCADE, related_name="permissions"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        verbose_name = _("Volume Permission")
        verbose_name_plural = _("Volume Permissions")
        unique_together = [["user", "volume"]]

    def __str__(self):
        return f"{self.user} - {self.volume} ({self.role})"
