# Plain Language Checker

MVP для проверки русскоязычного текста по правилам простого языка.

## Стек
- Frontend: React + Vite + TypeScript
- Backend: Django + DRF
- DB: PostgreSQL
- Runtime: Docker Compose

## Быстрый старт
1. Запустите сервисы:
   - `docker compose up --build`
2. Откройте frontend:
   - `http://localhost:5173`
3. API backend:
   - `http://localhost:8000/api/health/`

## Что уже заложено в каркас
- Базовый UI для ввода текста и токена.
- Заглушка endpoint анализа с цветовой разметкой.
- Базовая инфраструктура для дальнейшей интеграции Yandex AI Studio.

## План
Подробный roadmap: [PLAN.md](PLAN.md)
