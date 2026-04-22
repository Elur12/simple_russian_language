from django.contrib.auth.models import User
from rest_framework import serializers

from .models import UserApiToken


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class UserApiTokenSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, required=False)
    masked_token = serializers.SerializerMethodField()

    class Meta:
        model = UserApiToken
        fields = ("token", "masked_token", "updated_at")
        read_only_fields = ("updated_at",)
    
    def get_masked_token(self, obj: UserApiToken) -> str:
        """Return masked version of encrypted token (just first 5 chars + ...)."""
        if obj.encrypted_token:
            return f"{obj.encrypted_token[:5]}...***"
        return "No token set"

