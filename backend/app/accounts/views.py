from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .crypto import decrypt_token, encrypt_token
from .models import UserApiToken
from .serializers import RegisterSerializer


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class UserTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        token_obj = UserApiToken.objects.filter(user=request.user).first()
        if not token_obj:
            return Response({"has_token": False}, status=status.HTTP_200_OK)

        return Response(
            {
                "has_token": True,
                "masked_token": self._mask_token(token_obj.encrypted_token),
                "updated_at": token_obj.updated_at,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        token = request.data.get("token", "").strip()
        # Token is required
        if not token:
            return Response(
                {"detail": "Поле token обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        encrypted = encrypt_token(token)
        obj, _ = UserApiToken.objects.update_or_create(
            user=request.user,
            defaults={
                "encrypted_token": encrypted,
            },
        )
        return Response(
            {
                "has_token": True,
                "masked_token": self._mask_token(obj.encrypted_token),
                "updated_at": obj.updated_at,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        UserApiToken.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _mask_token(encrypted_token: str) -> str:
        token = decrypt_token(encrypted_token)
        tail = token[-4:] if len(token) >= 4 else token
        return f"***{tail}"
