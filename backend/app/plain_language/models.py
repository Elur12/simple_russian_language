from django.conf import settings
from django.db import models


class ApiRequestLog(models.Model):
    ENDPOINT_ANALYZE = "analyze"
    ENDPOINT_FETCH_URL = "fetch_url"
    ENDPOINT_CHOICES = [
        (ENDPOINT_ANALYZE, "Анализ текста"),
        (ENDPOINT_FETCH_URL, "Загрузка URL"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_request_logs",
    )
    endpoint = models.CharField(max_length=32, choices=ENDPOINT_CHOICES, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    status_code = models.PositiveSmallIntegerField()

    input_text = models.TextField(blank=True, default="")
    input_url = models.CharField(max_length=2000, blank=True, default="")
    input_chars = models.PositiveIntegerField(default=0)

    response_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    summary_green = models.PositiveIntegerField(null=True, blank=True)
    summary_orange = models.PositiveIntegerField(null=True, blank=True)
    summary_red = models.PositiveIntegerField(null=True, blank=True)
    paragraphs_count = models.PositiveIntegerField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Лог запроса"
        verbose_name_plural = "Логи запросов"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["endpoint", "-created_at"]),
        ]

    def __str__(self) -> str:
        who = self.user.username if self.user else "anon"
        return f"{self.endpoint} · {who} · {self.created_at:%Y-%m-%d %H:%M:%S} · {self.status_code}"
