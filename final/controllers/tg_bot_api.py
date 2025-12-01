# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request


class TelegramBotApiController(http.Controller):
    """REST API для Telegram-бота.

    Основной сценарий:
    - Менеджер в Odoo создаёт клиента и заполняет поле Telegram User ID.
    - Клиент пишет нашему боту в Telegram.
    - Бот отправляет telegram_user_id в Odoo через эти эндпоинты.
    - Odoo ищет клиента по telegram_user_id и возвращает данные (баланс, тренировки и т.д.).
    """

    # === Вспомогательные методы ===

    def _get_api_token(self):
        """Читает токен API бота из настроек системы."""
        param_env = request.env["ir.config_parameter"].sudo()
        return param_env.get_param("final.tg_bot_api_token") or ""

    def _authenticate_request(self, data):
        """Проверка токена в запросе.

        Ожидаем поле api_token в JSON.
        """
        data = data or {}
        request_token = data.get("api_token") or ""
        expected_token = self._get_api_token()

        # Упрощённая логика: если токен в системе не задан, разрешаем все запросы.
        # Если задан — требуем точного совпадения.
        if not expected_token:
            return True
        return bool(request_token) and request_token == expected_token

    def _find_partner_by_telegram_id(self, telegram_user_id):
        """Поиск клиента по Telegram User ID."""
        if not telegram_user_id:
            return request.env["res.partner"]

        return (
            request.env["res.partner"]
            .sudo()
            .search([("telegram_user_id", "=", int(telegram_user_id))], limit=1)
        )

    # === Эндпоинты ===

    @http.route(
        "/api/tg/balance",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_tg_balance(self, **kwargs):
        """Получение баланса клиента по telegram_user_id.

        Вход (JSON):
        {
            "api_token": "секретный_токен",
            "telegram_user_id": 123456789
        }

        Ответ (успех):
        {
            "success": true,
            "partner_id": 42,
            "name": "Иван Иванов",
            "balance": 1000.0,
            "currency": "RUB"
        }

        Ответ (ошибка):
        {
            "success": false,
            "error": "INVALID_TOKEN" | "NOT_FOUND" | "NO_TELEGRAM_ID"
        }
        """
        # Для type="json" Odoo оборачивает входные данные в параметр "params"
        # при вызове через JSON-RPC. Поэтому поддерживаем оба варианта:
        # прямой вызов: {"telegram_user_id": 123}
        # JSON-RPC: {"params": {"telegram_user_id": 123, ...}, ...}
        # Для type="json" корректный способ получить тело запроса в Odoo 18 -
        # использовать request.get_json_data()
        data = request.get_json_data() or {}

        # Проверка токена
        if not self._authenticate_request(data):
            return {"success": False, "error": "INVALID_TOKEN"}

        telegram_user_id = data.get("telegram_user_id") or data.get("telegram_id")
        if not telegram_user_id:
            return {"success": False, "error": "NO_TELEGRAM_ID"}

        partner = self._find_partner_by_telegram_id(telegram_user_id)
        if not partner:
            return {"success": False, "error": "NOT_FOUND"}

        currency = partner.balance_currency_id or request.env.company.currency_id

        return {
            "success": True,
            "partner_id": partner.id,
            "name": partner.name,
            "balance": float(partner.balance or 0.0),
            "currency": currency.name,
        }

    @http.route(
        "/api/tg/trainings",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_tg_trainings(self, **kwargs):
        """Получение предстоящих тренировок клиента по telegram_user_id.

        Вход (JSON):
        {
            "api_token": "секретный_токен",
            "telegram_user_id": 123456789
        }

        Ответ (успех):
        {
            "success": true,
            "partner_id": 42,
            "name": "Иван Иванов",
            "trainings": [
                {
                    "id": 10,
                    "date": "2025-12-01",
                    "time_start": "15:00",
                    "time_end": "16:00",
                    "sport_center": "СЦ Центральный",
                    "tennis_court": "Корт 1",
                    "trainer": "Петров Петр",
                    "training_type": "Индивидуальная"
                },
                ...
            ]
        }
        """
        data = request.get_json_data() or {}

        # Проверка токена
        if not self._authenticate_request(data):
            return {"success": False, "error": "INVALID_TOKEN"}

        telegram_user_id = data.get("telegram_user_id") or data.get("telegram_id")
        if not telegram_user_id:
            return {"success": False, "error": "NO_TELEGRAM_ID"}

        partner = self._find_partner_by_telegram_id(telegram_user_id)
        if not partner:
            return {"success": False, "error": "NOT_FOUND"}

        # Ищем предстоящие подтверждённые тренировки клиента
        now = fields.Datetime.now()
        booking_env = request.env["final.training.booking"].sudo()
        bookings = booking_env.search(
            [
                ("state", "=", "confirmed"),
                ("start_datetime", ">=", now),
                ("client_ids", "in", [partner.id]),
            ],
            order="start_datetime asc",
        )

        trainings = []
        for booking in bookings:
            # Локализуем время под текущую таймзону Odoo
            start_local = fields.Datetime.context_timestamp(booking, booking.start_datetime)
            end_local = fields.Datetime.context_timestamp(booking, booking.end_datetime)

            trainings.append(
                {
                    "id": booking.id,
                    "date": start_local.strftime("%Y-%m-%d") if start_local else "",
                    "time_start": start_local.strftime("%H:%M") if start_local else "",
                    "time_end": end_local.strftime("%H:%M") if end_local else "",
                    "sport_center": booking.sport_center_id.name if booking.sport_center_id else "",
                    "tennis_court": booking.tennis_court_id.name if booking.tennis_court_id else "",
                    "trainer": booking.trainer_id.name if booking.trainer_id else "",
                    "training_type": booking.training_type_id.name if booking.training_type_id else "",
                }
            )

        return {
            "success": True,
            "partner_id": partner.id,
            "name": partner.name,
            "trainings": trainings,
        }


