from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CreateTrainerWizard(models.TransientModel):
    _name = "final.create.trainer.wizard"
    _description = "Мастер создания тренера"
    trainer_name = fields.Char(
        string="Имя тренера",
        required=True,
    )
    trainer_login = fields.Char(
        string="Логин",
        required=True,
    )
    trainer_email = fields.Char(
        string="E-mail",
    )
    trainer_password = fields.Char(
        string="Пароль",
        required=True,
    )

    def action_create_trainer(self):
        self.ensure_one()
        if not self.trainer_name or not self.trainer_login or not self.trainer_password:
            raise ValidationError(
                _("Необходимо заполнить имя тренера, логин и пароль.")
            )

        Employee = self.env["hr.employee"]
        User = self.env["res.users"]
        trainer_group = self.env.ref("final.group_final_trainer")
        internal_group = self.env.ref("base.group_user")

        # Проверяем, существует ли пользователь с таким логином
        existing_user = User.search([("login", "=", self.trainer_login)], limit=1)
        if existing_user:
            raise ValidationError(
                _("Пользователь с логином '%s' уже существует.") % self.trainer_login
            )

        # Создаем пользователя
        company_id = self.env.company.id
        user_vals = {
            "name": self.trainer_name,
            "login": self.trainer_login,
            "email": self.trainer_email or False,
            "password": self.trainer_password,
            "company_id": company_id,
            "company_ids": [(6, 0, [company_id])],
            "groups_id": [(6, 0, [internal_group.id, trainer_group.id])],
        }
        user = User.sudo().create(user_vals)

        # Создаем сотрудника (тренера)
        employee_vals = {
            "name": self.trainer_name,
            "user_id": user.id,
            "work_email": self.trainer_email or False,
            "is_final_trainer": True,
        }
        employee = Employee.sudo().create(employee_vals)

        # Возвращаем действие для открытия списка тренеров
        return {
            "type": "ir.actions.act_window",
            "name": _("Тренеры"),
            "res_model": "hr.employee",
            "view_mode": "list,form",
            "domain": [("is_final_trainer", "=", True)],
            "target": "current",
            "context": {"search_default_trainers": 1},
        }

