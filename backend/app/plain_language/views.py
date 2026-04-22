import logging
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings

from accounts.models import UserApiToken
from accounts.crypto import decrypt_token

from .schemas import AnalysisResponse
from .url_fetcher import UrlFetchError, fetch_url
from .yandex_adapter import YandexAIAnalyzer, YandexAIError, YandexAITokenError

logger = logging.getLogger(__name__)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class FetchUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = request.data.get("url", "").strip()
        if not url:
            return Response(
                {"detail": "Поле url обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = fetch_url(url)
            return Response(result, status=status.HTTP_200_OK)
        except UrlFetchError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Unexpected error in FetchUrlView: %s", e, exc_info=True)
            return Response(
                {"detail": "Не удалось загрузить страницу."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AnalyzeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if user has saved Yandex token
        user_token_obj = UserApiToken.objects.filter(user=request.user).first()
        if not user_token_obj:
            return Response(
                {"detail": "Сначала сохраните токен Yandex AI Studio в профиле."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get and validate text
        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"detail": "Поле text обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Decrypt user's token
        try:
            decrypted_token = decrypt_token(user_token_obj.encrypted_token)
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            return Response(
                {"detail": "Ошибка при расшифровке токена. Пожалуйста, сохраните токен заново."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return Response(
                {"detail": "Не удалось выделить абзацы для анализа."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Analyze text with Yandex AI (sliding window: prev/current/next)
        try:
            analyzer = YandexAIAnalyzer(decrypted_token, model=settings.YANDEX_MODEL)
            raw_items = []
            total = len(paragraphs)
            for idx, current in enumerate(paragraphs):
                prev_paragraph = paragraphs[idx - 1] if idx > 0 else ""
                next_paragraph = paragraphs[idx + 1] if idx < total - 1 else ""
                analysis = analyzer.analyze_paragraph_with_context(
                    current_paragraph=current,
                    current_index=idx,
                    total_paragraphs=total,
                    prev_paragraph=prev_paragraph,
                    next_paragraph=next_paragraph,
                )

                window_items = analysis.get("items", [])
                if window_items:
                    window_item = window_items[0]
                    if not isinstance(window_item, dict):
                        window_item = {}
                    # Keep original paragraph text from input to preserve formatting.
                    window_item["unit_index"] = idx
                    window_item["source_text"] = current
                    raw_items.append(window_item)
                else:
                    raw_items.append(
                        {
                            "unit_index": idx,
                            "unit_type": "paragraph",
                            "source_text": current,
                            "severity": "green",
                            "violations": [],
                            "overall_comment": "Нарушения не обнаружены.",
                            "sentence_findings": [],
                        }
                    )

            # Format response
            items = self._format_analysis_items({"items": raw_items})
            summary = self._compute_summary(items)
            
            payload = AnalysisResponse(summary=summary, items=items).model_dump()
            return Response(payload, status=status.HTTP_200_OK)
            
        except YandexAITokenError as e:
            logger.error(f"Token error: {e}")
            return Response(
                {"detail": f"Ошибка аутентификации: {str(e)}. Проверьте токен в профиле."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except YandexAIError as e:
            logger.error(f"Yandex AI error: {e}")
            return Response(
                {"detail": f"Ошибка анализа текста: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
            return Response(
                {"detail": "Неожиданная ошибка при анализе текста."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def _get_stub_analysis(self, text: str) -> Response:
        """
        Return stub analysis when Yandex AI is not configured.
        Useful for development without API credentials.
        """
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        items = []
        
        for idx, paragraph in enumerate(paragraphs):
            severity = "green" if len(paragraph) < 180 else "orange"
            stub_violations = []
            if severity != "green":
                stub_violations = [{
                    "rule_id": "R1",
                    "rule_name": "Используйте часто употребляемые слова",
                    "severity": "orange",
                    "problematic_text": "",
                    "comment": "Черновая оценка (Yandex AI не настроен). Сохраните корректный API-ключ в профиле.",
                    "suggested_rewrite": "",
                }]
            items.append(
                {
                    "unit_index": idx,
                    "unit_type": "paragraph",
                    "source_text": paragraph,
                    "severity": severity,
                    "violations": stub_violations,
                    "overall_comment": "Черновая оценка (Yandex AI не настроен).",
                    "paragraph_rewrite": paragraph,
                    "sentence_findings": [],
                }
            )
        
        summary = {
            "green": sum(1 for i in items if i["severity"] == "green"),
            "orange": sum(1 for i in items if i["severity"] == "orange"),
            "red": sum(1 for i in items if i["severity"] == "red"),
            "overall": "green" if all(i["severity"] == "green" for i in items) else "orange",
        }
        
        payload = AnalysisResponse(summary=summary, items=items).model_dump()
        return Response(payload, status=status.HTTP_200_OK)
    
    def _format_analysis_items(self, analysis: dict) -> list:
        """
        Convert Yandex AI response to our internal format.

        Args:
            analysis: Response from YandexAIAnalyzer.analyze_text()

        Returns:
            List of formatted analysis items
        """
        ALLOWED_SEVERITY = {"green", "orange", "red"}
        SEVERITY_RANK = {"green": 1, "orange": 2, "red": 3}
        formatted_items = []

        for item in analysis.get("items", []):
            source_text = item.get("source_text", "")

            # Build structured violation objects
            raw_violations = item.get("violations", [])
            violations = []
            for v in raw_violations:
                if not isinstance(v, dict):
                    continue
                v_severity = v.get("severity", "orange")
                if v_severity not in ALLOWED_SEVERITY:
                    v_severity = "orange"
                violations.append({
                    "rule_id": str(v.get("rule_id", "R1")),
                    "rule_name": str(v.get("rule_name", "")),
                    "severity": v_severity,
                    "problematic_text": str(v.get("problematic_text", "")).strip(),
                    "comment": str(v.get("comment", "")),
                    "suggested_rewrite": str(v.get("suggested_rewrite", "")).strip(),
                })

            # Recalculate paragraph severity from violations (never trust model blindly)
            if violations:
                max_rank = max(SEVERITY_RANK.get(v["severity"], 1) for v in violations)
                severity = {1: "green", 2: "orange", 3: "red"}[max_rank]
            else:
                severity = "green"

            # Build paragraph_rewrite by applying all violation rewrites sequentially.
            # Prefer model's paragraph_rewrite if provided and non-empty.
            paragraph_rewrite = str(item.get("paragraph_rewrite", "")).strip()
            if not paragraph_rewrite:
                paragraph_rewrite = source_text
                for v in violations:
                    prob = v["problematic_text"]
                    replacement = v["suggested_rewrite"]
                    if prob and replacement and prob in paragraph_rewrite:
                        paragraph_rewrite = paragraph_rewrite.replace(prob, replacement, 1)

            formatted_items.append({
                "unit_index": item.get("unit_index", 0),
                "unit_type": item.get("unit_type", "paragraph"),
                "source_text": source_text,
                "severity": severity,
                "violations": violations,
                "overall_comment": str(item.get("overall_comment", item.get("comment", ""))),
                "paragraph_rewrite": paragraph_rewrite,
                "sentence_findings": item.get("sentence_findings", []),
            })

        return formatted_items

    def _split_paragraphs(self, text: str) -> list[str]:
        """
        Split text into paragraphs by empty lines and preserve list-like blocks.
        """
        lines = [line.rstrip() for line in text.splitlines()]
        paragraphs: list[str] = []
        buffer: list[str] = []

        for line in lines:
            if line.strip() == "":
                if buffer:
                    paragraphs.append("\n".join(buffer).strip())
                    buffer = []
                continue
            buffer.append(line)

        if buffer:
            paragraphs.append("\n".join(buffer).strip())

        return paragraphs
    
    def _compute_summary(self, items: list) -> dict:
        """
        Compute summary statistics from analysis items.
        """
        green_count = sum(1 for i in items if i["severity"] == "green")
        orange_count = sum(1 for i in items if i["severity"] == "orange")
        red_count = sum(1 for i in items if i["severity"] == "red")
        
        # Determine overall severity
        if red_count > 0:
            overall = "red"
        elif orange_count > 0:
            overall = "orange"
        else:
            overall = "green"
        
        return {
            "green": green_count,
            "orange": orange_count,
            "red": red_count,
            "overall": overall,
        }

