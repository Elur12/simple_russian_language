from django.contrib import admin
from django.utils.html import format_html

from .models import ApiRequestLog


@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "endpoint",
        "status_code",
        "short_input",
        "summary_badge",
        "paragraphs_count",
        "duration_ms",
    )
    list_filter = ("endpoint", "status_code", "created_at", "user")
    search_fields = (
        "user__username",
        "user__email",
        "input_text",
        "input_url",
        "error_message",
        "ip_address",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50

    readonly_fields = (
        "user",
        "endpoint",
        "created_at",
        "duration_ms",
        "status_code",
        "input_text",
        "input_url",
        "input_chars",
        "paragraphs_count",
        "summary_green",
        "summary_orange",
        "summary_red",
        "response_pretty",
        "error_message",
        "ip_address",
        "user_agent",
    )
    exclude = ("response_json",)

    fieldsets = (
        ("Запрос", {
            "fields": (
                "created_at",
                "user",
                "endpoint",
                "status_code",
                "duration_ms",
                "ip_address",
                "user_agent",
            ),
        }),
        ("Вход", {
            "fields": ("input_chars", "input_url", "input_text"),
        }),
        ("Результат", {
            "fields": (
                "paragraphs_count",
                "summary_green",
                "summary_orange",
                "summary_red",
                "response_pretty",
                "error_message",
            ),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Вход", ordering="created_at")
    def short_input(self, obj: ApiRequestLog) -> str:
        src = obj.input_url or obj.input_text or ""
        src = src.replace("\n", " ")
        return (src[:80] + "…") if len(src) > 80 else src

    @admin.display(description="Сводка")
    def summary_badge(self, obj: ApiRequestLog) -> str:
        if obj.summary_green is None:
            return "—"
        return format_html(
            '<span title="Чистые абзацы / orange / red">'
            '<span style="color:#16a34a">●{}</span> '
            '<span style="color:#f59e0b">●{}</span> '
            '<span style="color:#dc2626">●{}</span>'
            "</span>",
            obj.summary_green,
            obj.summary_orange,
            obj.summary_red,
        )

    @admin.display(description="Ответ (JSON)")
    def response_pretty(self, obj: ApiRequestLog) -> str:
        import json
        if obj.response_json is None:
            return "—"
        try:
            pretty = json.dumps(obj.response_json, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pretty = str(obj.response_json)
        return format_html(
            '<pre style="max-height:500px;overflow:auto;'
            'background:#f8fafc;padding:12px;border-radius:6px;'
            'font-size:12px;">{}</pre>',
            pretty,
        )
