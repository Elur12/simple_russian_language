from django.conf import settings
from django.db import models


class UserApiToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    encrypted_token = models.TextField()
    yandex_folder_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Legacy field (no longer used by API requests).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"UserApiToken(user_id={self.user_id})"

