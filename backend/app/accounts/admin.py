from django.contrib import admin

from .models import UserApiToken


@admin.register(UserApiToken)
class UserApiTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "created_at", "updated_at", "yandex_folder_id")
    exclude = ("encrypted_token",)

    def has_add_permission(self, request):
        return False
