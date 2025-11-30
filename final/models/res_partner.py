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

