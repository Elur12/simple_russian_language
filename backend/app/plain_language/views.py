import logging
import time
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings

from accounts.models import UserApiToken
from accounts.crypto import decrypt_token

from .models import ApiRequestLog
from .schemas import AnalysisResponse
from .url_fetcher import UrlFetchError, fetch_url
from .yandex_adapter import YandexAIAnalyzer, YandexAIError, YandexAITokenError

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _record_log(
    *,
    request,
    endpoint: str,
    started_at: float,
    status_code: int,
    input_text: str = "",
    input_url: str = "",
    response_json=None,
    error_message: str = "",
    summary: dict | None = None,
    paragraphs_count: int | None = None,
) -> None:
    """Write a single ApiRequestLog row. Never raises — logging must not break the view."""
    try:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        ApiRequestLog.objects.create(
            user=user,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            input_text=input_text[:50_000],
            input_url=input_url[:2000],
            input_chars=len(input_text) if input_text else len(input_url),
            response_json=response_json,
            error_message=error_message[:4000] if error_message else "",
            summary_green=(summary or {}).get("green"),
            summary_orange=(summary or {}).get("orange"),
            summary_red=(summary or {}).get("red"),
            paragraphs_count=paragraphs_count,
            ip_address=_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        )
    except Exception as exc:
        logger.warning("Failed to write ApiRequestLog: %s", exc, exc_info=True)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class FetchUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        started_at = time.monotonic()
        url = request.data.get("url", "").strip()
        if not url:
            _record_log(
                request=request, endpoint=ApiRequestLog.ENDPOINT_FETCH_URL,
                started_at=started_at, status_code=400, input_url=url,
                error_message="url field missing",
            )
            return Response(
                {"detail": "Поле url обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = fetch_url(url)
            # Store only metadata + a truncated preview of the extracted text,
            # not the full page contents (can be large).
            log_response = {
                "url": result.get("url"),
                "title": result.get("title"),
                "text_preview": (result.get("text") or "")[:2000],
                "text_chars": len(result.get("text") or ""),
            }
            _record_log(
                request=request, endpoint=ApiRequestLog.ENDPOINT_FETCH_URL,
                started_at=started_at, status_code=200, input_url=url,
                response_json=log_response,
            )
            return Response(result, status=status.HTTP_200_OK)
        except UrlFetchError as e:
            _record_log(
                request=request, endpoint=ApiRequestLog.ENDPOINT_FETCH_URL,
                started_at=started_at, status_code=400, input_url=url,
                error_message=str(e),
            )
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Unexpected error in FetchUrlView: %s", e, exc_info=True)
            _record_log(
                request=request, endpoint=ApiRequestLog.ENDPOINT_FETCH_URL,
                started_at=started_at, status_code=500, input_url=url,
                error_message=repr(e),
            )
            return Response(
                {"detail": "Не удалось загрузить страницу."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AnalyzeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        started_at = time.monotonic()
        text = request.data.get("text", "").strip()

        def log(code, *, response_json=None, err="", summary=None, paragraphs_count=None):
            _record_log(
                request=request, endpoint=ApiRequestLog.ENDPOINT_ANALYZE,
                started_at=started_at, status_code=code,
                input_text=text, response_json=response_json,
                error_message=err, summary=summary, paragraphs_count=paragraphs_count,
            )

        # Check if user has saved Yandex token
        user_token_obj = UserApiToken.objects.filter(user=request.user).first()
        if not user_token_obj:
            log(400, err="no yandex token in profile")
            return Response(
                {"detail": "Сначала сохраните токен Yandex AI Studio в профиле."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get and validate text
        if not text:
            log(400, err="text field empty")
            return Response(
                {"detail": "Поле text обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Decrypt user's token
        try:
            decrypted_token = decrypt_token(user_token_obj.encrypted_token)
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            log(400, err=f"token decrypt failed: {e}")
            return Response(
                {"detail": "Ошибка при расшифровке токена. Пожалуйста, сохраните токен заново."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            log(400, err="no paragraphs extracted")
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
            log(200, response_json=payload, summary=summary, paragraphs_count=len(paragraphs))
            return Response(payload, status=status.HTTP_200_OK)

        except YandexAITokenError as e:
            logger.error(f"Token error: {e}")
            log(401, err=str(e), paragraphs_count=len(paragraphs))
            return Response(
                {"detail": f"Ошибка аутентификации: {str(e)}. Проверьте токен в профиле."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except YandexAIError as e:
            logger.error(f"Yandex AI error: {e}")
            log(502, err=str(e), paragraphs_count=len(paragraphs))
            return Response(
                {"detail": f"Ошибка анализа текста: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
            log(500, err=repr(e), paragraphs_count=len(paragraphs))
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
        
        summary = self._compute_summary(items)
        
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

        green = number of paragraphs with zero violations (clean paragraphs).
        orange / red = total number of individual violations with that severity
        across all paragraphs. This matches the user-facing semantics: the
        orange / red numbers tell the user how many fixes to make, while
        green tells how many paragraphs are already fine.
        """
        clean_paragraphs = sum(1 for i in items if not i.get("violations"))
        orange_violations = sum(
            1 for i in items for v in i.get("violations", [])
            if v.get("severity") == "orange"
        )
        red_violations = sum(
            1 for i in items for v in i.get("violations", [])
            if v.get("severity") == "red"
        )

        if red_violations > 0:
            overall = "red"
        elif orange_violations > 0:
            overall = "orange"
        else:
            overall = "green"

        return {
            "green": clean_paragraphs,
            "orange": orange_violations,
            "red": red_violations,
            "overall": overall,
        }

