# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    balance = fields.Monetary(
        string="Баланс",
        default=0.0,
        currency_field="balance_currency_id",
        help="Текущий баланс клиента",
    )
    balance_currency_id = fields.Many2one(
        "res.currency",
        string="Валюта баланса",
        default=lambda self: self.env.company.currency_id,
        help="Валюта баланса клиента",
    )
    training_booking_ids = fields.Many2many(
        "final.training.booking",
        "final_training_booking_partner_rel",
        "partner_id",
        "booking_id",
        string="Тренировки",
        help="Тренировки клиента",
    )
    balance_history_ids = fields.One2many(
        "final.balance.transaction",
        "partner_id",
        string="История баланса",
        help="История транзакций баланса клиента",
    )
    sport_center_ids = fields.Many2many(
        "final.sport.center",
        "final_center_res_partner_rel",
        "partner_id",
        "center_id",
        string="Спортивные центры",
        help="Спортивные центры, к которым относится клиент.",
    )
    telegram_user_id = fields.Integer(
        string="Telegram User ID",
        help="Уникальный идентификатор пользователя в Telegram, вводится менеджером вручную",
    )
    telegram_username = fields.Char(
        string="Telegram Username",
        help="Имя пользователя в Telegram (@username), опционально, для удобства",
    )

    @api.constrains("balance")
    def _check_balance_not_negative(self):
        """Проверка что баланс не отрицательный (опционально, можно убрать если разрешены отрицательные балансы)"""
        # Эта проверка может быть отключена, если нужно разрешить отрицательные балансы
        # для record in self:
        #     if record.balance < 0:
        #         raise ValidationError(
        #             _("Баланс клиента '%s' не может быть отрицательным.") % record.name
        #         )
        pass

    @api.constrains("telegram_user_id")
    def _check_telegram_user_id(self):
        """Проверка корректности и уникальности Telegram User ID"""
        for record in self:
            if record.telegram_user_id:
                # ID должен быть положительным числом
                if record.telegram_user_id <= 0:
                    raise ValidationError(
                        _("Telegram User ID для клиента '%s' должен быть положительным числом.")
                        % (record.name,)
                    )

                # Уникальность в системе
                duplicate = (
                    self.search(
                        [
                            ("id", "!=", record.id),
                            ("telegram_user_id", "=", record.telegram_user_id),
                        ],
                        limit=1,
                    )
                    if record.id
                    else False
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            "Telegram User ID %d уже привязан к клиенту '%s'. "
                            "Один Telegram-аккаунт не может быть привязан к нескольким клиентам."
                        )
                        % (record.telegram_user_id, duplicate.name)
                    )

    def get_balance(self):
        """Получить текущий баланс клиента"""
        return self.balance

    def deposit_balance(self, amount, description=""):
        """Пополнить баланс клиента"""
        if amount <= 0:
            raise ValidationError(_("Сумма пополнения должна быть положительным числом."))
        
        self.env["final.balance.transaction"].action_deposit(
            self.id, amount, description
        )
        return True

    def withdraw_balance(self, amount, booking_id=None, description=""):
        """Списать с баланса клиента"""
        if amount <= 0:
            raise ValidationError(_("Сумма списания должна быть положительным числом."))
        
        self.env["final.balance.transaction"].action_withdrawal(
            self.id, amount, booking_id, description
        )
        return True

    def action_open_balance_deposit_wizard(self):
        """Открывает wizard пополнения баланса"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Пополнить баланс"),
            "res_model": "final.balance.deposit.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Автоматически привязываем клиентов к центру менеджера, который их создаёт.

        - Если клиент создаётся пользователем с ролью Менеджер
          и у него есть manager_center_ids,
          привязываем клиента к этим центрам (если явно не указано иное).
        """
        records = super().create(vals_list)
        user = self.env.user

        if user.has_group("final.group_final_manager"):
            centers = user.employee_id.manager_center_ids
            if centers:
                for partner in records:
                    # Если при создании явно не указали центры, добавляем центры менеджера
                    if not partner.sport_center_ids:
                        partner.sudo().write(
                            {"sport_center_ids": [(6, 0, centers.ids)]}
                        )

        return records

