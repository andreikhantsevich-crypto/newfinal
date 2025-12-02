from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class FinalSportCenter(models.Model):
    _name = "final.sport.center"
    _description = "Спортивный центр"

    name = fields.Char(required=True, string="Название СЦ")
    manager_id = fields.Many2one(
        "hr.employee",
        string="Менеджер",
        required=True,
        domain="['|', ('sport_center_id', '=', False), ('sport_center_id', '=', id)]",
        readonly=True,
        copy=False,
    )
    manager_name = fields.Char(
        string="Имя менеджера",
        required=True,
        copy=False,
        help="ФИО менеджера спортивного центра.",
    )
    work_time_start = fields.Float(
        string="Начало работы (часы)",
        required=True,
        default=8.0,
    )
    work_time_end = fields.Float(
        string="Окончание работы (часы)",
        required=True,
        default=22.0,
    )
    tennis_court_ids = fields.One2many(
        "final.tennis.court",
        "sport_center_id",
        string="Теннисные корты",
        copy=True,
    )
    tennis_court_count = fields.Integer(
        string="Количество кортов",
        compute="_compute_tennis_court_count",
    )
    client_ids = fields.Many2many(
        "res.partner",
        "final_center_res_partner_rel",
        "center_id",
        "partner_id",
        string="Клиенты",
        help="Клиенты этого спортивного центра (с привязанным Telegram ID)",
    )
    trainer_ids = fields.One2many(
        "final.center.trainer",
        "sport_center_id",
        string="Тренеры",
        copy=True,
    )
    tennis_court_ids = fields.One2many(
        "final.tennis.court",
        "sport_center_id",
        string="Теннисные корты",
    )
    manager_login = fields.Char(
        string="Логин менеджера",
        copy=False,
        help="Логин пользователя менеджера. Заполните при создании нового пользователя.",
    )
    manager_email = fields.Char(
        string="E-mail менеджера",
        copy=False,
        help="E-mail пользователя менеджера.",
    )
    manager_password = fields.Char(
        string="Пароль менеджера",
        copy=False,
        help="Пароль нового пользователя менеджера. После сохранения будет очищен.",
    )
    training_price_ids = fields.One2many(
        "final.center.training.price",
        "center_id",
        string="Цены на тренировки",
        copy=True,
    )
    
    # Computed поля для цен на тренировки
    individual_price = fields.Monetary(
        string="Цена за индивидуальную тренировку (за чел.)",
        compute="_compute_training_prices",
        inverse="_inverse_training_prices",
        currency_field="currency_id",
        help="Стоимость одного часа индивидуальной тренировки за человека",
    )
    split_price = fields.Monetary(
        string="Цена за сплит тренировку (за чел.)",
        compute="_compute_training_prices",
        inverse="_inverse_training_prices",
        currency_field="currency_id",
        help="Стоимость одного часа сплит тренировки за человека",
    )
    group_price = fields.Monetary(
        string="Цена за групповую тренировку (за чел.)",
        compute="_compute_training_prices",
        inverse="_inverse_training_prices",
        currency_field="currency_id",
        help="Стоимость одного часа групповой тренировки за человека",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="company_id.currency_id",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Компания",
        default=lambda self: self.env.company,
    )
    trainer_attached_center_ids = fields.Many2many(
        "final.sport.center",
        string="Центры текущего тренера",
        compute="_compute_trainer_attached_centers",
        search="_search_trainer_attached_centers",
    )
    is_trainer_attached = fields.Boolean(
        string="Тренер привязан",
        compute="_compute_is_trainer_attached",
        search="_search_is_trainer_attached",
        help="Показывает, привязан ли текущий тренер к этому центру",
    )
    # Поля для ввода ставок тренера (временные, не stored)
    _trainer_rates_storage = fields.Char(
        string="Временное хранилище ставок",
        default="{}",
        help="Временное хранилище для ставок тренера в формате JSON",
    )
    trainer_individual_rate = fields.Monetary(
        string="Ставка за индивидуальную тренировку",
        currency_field="currency_id",
        compute="_compute_trainer_rates",
        inverse="_inverse_trainer_rates",
        help="Ставка тренера за час индивидуальной тренировки",
    )
    trainer_split_rate = fields.Monetary(
        string="Ставка за сплит тренировку",
        currency_field="currency_id",
        compute="_compute_trainer_rates",
        inverse="_inverse_trainer_rates",
        help="Ставка тренера за час сплит тренировки",
    )
    trainer_group_rate = fields.Monetary(
        string="Ставка за групповую тренировку",
        currency_field="currency_id",
        compute="_compute_trainer_rates",
        inverse="_inverse_trainer_rates",
        help="Ставка тренера за час групповой тренировки",
    )

    def action_ensure_training_prices(self):
        """Действие для создания цен на тренировки для существующего СЦ"""
        self.ensure_one()
        self._create_default_training_prices()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Цены созданы'),
                'message': _('Цены на все виды тренировок успешно созданы.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.constrains("work_time_start", "work_time_end")
    def _check_work_time(self):
        for record in self:
            if not 0 <= record.work_time_start < 24:
                raise ValidationError("Время начала работы СЦ должно быть в диапазоне 0-24.")
            if not 0 <= record.work_time_end <= 24:
                raise ValidationError("Время окончания работы СЦ должно быть в диапазоне 0-24.")
            if record.work_time_start >= record.work_time_end:
                raise ValidationError("Время окончания работы СЦ должно быть позже времени начала.")

    @api.constrains("manager_id")
    def _check_manager_available(self):
        for record in self:
            manager = record.manager_id
            if not manager:
                continue
            if manager.sport_center_id and manager.sport_center_id != record:
                raise ValidationError(
                    "Выбранный менеджер уже назначен на другой спортивный центр."
                )

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env["hr.employee"].sudo()
        new_vals_list = []
        for vals in vals_list:
            vals = vals.copy()
            manager_name = vals.get("manager_name")
            if not manager_name:
                raise ValidationError(
                    _("Необходимо указать имя менеджера спортивного центра.")
                )
            manager_email = vals.get("manager_email")
            employee_vals = {
                "name": manager_name,
            }
            if manager_email:
                employee_vals["work_email"] = manager_email
            manager_employee = Employee.create(employee_vals)
            vals["manager_id"] = manager_employee.id
            new_vals_list.append(vals)
        records = super().create(new_vals_list)
        records._assign_manager_center()
        for center, vals in zip(records, new_vals_list):
            center._sync_manager_user(vals)
        records._create_default_training_prices()
        return records

    def write(self, vals):
        old_managers = {record.id: record.manager_id for record in self}
        vals = vals.copy()
        res = super().write(vals)
        self._assign_manager_center()
        self._cleanup_old_managers(old_managers)
        if not self.env.context.get("skip_manager_user_sync"):
            for center in self:
                center._sync_manager_user(vals)
        return res

    def _assign_manager_center(self):
        Trainer = self.env["final.center.trainer"]
        for record in self:
            manager = record.manager_id
            if manager and manager.sport_center_id != record:
                manager.write(
                    {
                        "sport_center_id": record.id,
                        "is_final_manager": True,
                    }
                )
            elif manager and not manager.is_final_manager:
                manager.write({"is_final_manager": True})
            if manager:
                trainer_link = Trainer.search(
                    [
                        ("sport_center_id", "=", record.id),
                        ("employee_id", "=", manager.id),
                    ],
                    limit=1,
                )
                if trainer_link:
                    trainer_link.unlink()

    def _cleanup_old_managers(self, old_managers):
        Trainer = self.env["final.center.trainer"]
        for record in self:
            old_manager = old_managers.get(record.id)
            if not old_manager or old_manager == record.manager_id:
                continue
            if old_manager in record.trainer_ids.mapped("employee_id"):
                continue
            if old_manager.sport_center_id != record:
                continue
            trainer_link = Trainer.search(
                [
                    ("sport_center_id", "=", record.id),
                    ("employee_id", "=", old_manager.id),
                ],
                limit=1,
            )
            if trainer_link:
                continue
            old_manager.write(
                {
                    "sport_center_id": False,
                    "is_final_trainer": False,
                    "is_final_manager": False,
                }
            )

    @api.depends("tennis_court_ids")
    def _compute_tennis_court_count(self):
        for record in self:
            record.tennis_court_count = len(record.tennis_court_ids)

    def _compute_trainer_attached_centers(self):
        """Вычисляет центры, к которым привязан текущий тренер"""
        trainer_employee = self.env.user.employee_id
        if trainer_employee and trainer_employee.is_final_trainer:
            attached_centers = trainer_employee.trainer_center_ids
            for record in self:
                record.trainer_attached_center_ids = attached_centers
        else:
            for record in self:
                record.trainer_attached_center_ids = False

    def _search_trainer_attached_centers(self, operator, value):
        """Поиск по привязанным центрам тренера"""
        trainer_employee = self.env.user.employee_id
        if trainer_employee and trainer_employee.is_final_trainer:
            center_ids = trainer_employee.trainer_center_ids.ids
            if operator == 'in':
                return [('id', 'in', center_ids)]
            elif operator == 'not in':
                return [('id', 'not in', center_ids)]
        return [('id', '=', False)]

    @api.depends("trainer_ids.employee_id")
    def _compute_is_trainer_attached(self):
        """Вычисляет, привязан ли текущий тренер к этому центру"""
        trainer_employee = self.env.user.employee_id
        if trainer_employee and trainer_employee.is_final_trainer:
            attached_center_ids = trainer_employee.trainer_center_ids.ids
            for record in self:
                record.is_trainer_attached = record.id in attached_center_ids
        else:
            for record in self:
                record.is_trainer_attached = False

    @api.model
    def _search_is_trainer_attached(self, operator, value):
        """Поиск по привязке тренера к центру"""
        trainer_employee = self.env.user.employee_id
        if not trainer_employee or not trainer_employee.is_final_trainer:
            # Если тренер не найден, возвращаем пустой результат
            return [('id', '=', False)]
        
        attached_center_ids = trainer_employee.trainer_center_ids.ids
        
        if operator == '=' and value is True:
            # Ищем центры, к которым привязан тренер
            return [('id', 'in', attached_center_ids)]
        elif operator == '=' and value is False:
            # Ищем центры, к которым НЕ привязан тренер
            return [('id', 'not in', attached_center_ids)]
        elif operator == '!=' and value is True:
            # Ищем центры, к которым НЕ привязан тренер
            return [('id', 'not in', attached_center_ids)]
        elif operator == '!=' and value is False:
            # Ищем центры, к которым привязан тренер
            return [('id', 'in', attached_center_ids)]
        else:
            # Для других операторов возвращаем пустой результат
            return [('id', '=', False)]

    def action_open_tennis_courts(self):
        self.ensure_one()
        action = self.env.ref("final.action_final_tennis_court").read()[0]
        action["domain"] = [("sport_center_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = safe_eval(ctx, {})
        elif not isinstance(ctx, dict):
            ctx = {}
        action["context"] = {
            **ctx,
            "default_sport_center_id": self.id,
            "search_default_sport_center_id": self.id,
        }
        action["name"] = f"{self.name}: Теннисные корты"
        return action

    @api.depends("_trainer_rates_storage", "is_trainer_attached")
    def _compute_trainer_rates(self):
        """Вычисляет ставки тренера из временного хранилища или из БД"""
        import json
        for record in self:
            # Сначала пытаемся получить из временного хранилища
            try:
                storage = json.loads(record._trainer_rates_storage or "{}")
                record.trainer_individual_rate = storage.get('individual', 0.0)
                record.trainer_split_rate = storage.get('split', 0.0)
                record.trainer_group_rate = storage.get('group', 0.0)
            except:
                record.trainer_individual_rate = 0.0
                record.trainer_split_rate = 0.0
                record.trainer_group_rate = 0.0
            
            # Если тренер уже привязан, загружаем из БД
            if record.is_trainer_attached and record.id:
                trainer_employee = self.env.user.employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    TrainingType = self.env["final.training.type"]
                    TrainerRate = self.env["final.trainer.rate"]
                    
                    individual_type = TrainingType.search([("code", "=", "individual")], limit=1)
                    split_type = TrainingType.search([("code", "=", "split")], limit=1)
                    group_type = TrainingType.search([("code", "=", "group")], limit=1)
                    
                    if individual_type:
                        rate = TrainerRate.search([
                            ("trainer_id", "=", trainer_employee.id),
                            ("center_id", "=", record.id),
                            ("training_type_id", "=", individual_type.id),
                        ], limit=1)
                        if rate:
                            record.trainer_individual_rate = rate.hour_rate
                    
                    if split_type:
                        rate = TrainerRate.search([
                            ("trainer_id", "=", trainer_employee.id),
                            ("center_id", "=", record.id),
                            ("training_type_id", "=", split_type.id),
                        ], limit=1)
                        if rate:
                            record.trainer_split_rate = rate.hour_rate
                    
                    if group_type:
                        rate = TrainerRate.search([
                            ("trainer_id", "=", trainer_employee.id),
                            ("center_id", "=", record.id),
                            ("training_type_id", "=", group_type.id),
                        ], limit=1)
                        if rate:
                            record.trainer_group_rate = rate.hour_rate

    def _inverse_trainer_rates(self):
        """Сохраняет ставки во временное хранилище"""
        import json
        for record in self:
            storage = {
                'individual': record.trainer_individual_rate or 0.0,
                'split': record.trainer_split_rate or 0.0,
                'group': record.trainer_group_rate or 0.0,
            }
            record._trainer_rates_storage = json.dumps(storage)

    def action_apply_as_trainer(self):
        """Открывает wizard для устройства тренера в СЦ"""
        self.ensure_one()
        trainer_employee = self.env.user.employee_id
        
        if not trainer_employee or not trainer_employee.is_final_trainer:
            raise ValidationError(
                _("Текущий пользователь не является тренером.")
            )
        
        # Проверяем, не привязан ли уже
        existing_link = self.env["final.center.trainer"].search([
            ("employee_id", "=", trainer_employee.id),
            ("sport_center_id", "=", self.id),
        ], limit=1)
        
        if existing_link:
            raise ValidationError(
                _("Вы уже привязаны к спортивному центру '%s'.") % self.name
            )
        
        # Открываем wizard
        return {
            "type": "ir.actions.act_window",
            "name": _("Устроиться в спортивный центр"),
            "res_model": "final.apply.trainer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sport_center_id": self.id,
            },
        }

    @api.model
    def action_open_manager_center(self):
        """Открывает форму СЦ для менеджера"""
        employee = self.env.user.employee_id
        if not employee:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ошибка'),
                    'message': _('Сотрудник не найден для текущего пользователя.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        # Ищем СЦ, где этот сотрудник является менеджером
        center = self.search([('manager_id', '=', employee.id)], limit=1)
        if not center:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ошибка'),
                    'message': _('Спортивный центр не найден для текущего менеджера.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Мой спортивный центр'),
            'res_model': 'final.sport.center',
            'res_id': center.id,
            'view_mode': 'form',
            'view_id': self.env.ref('final.view_final_sport_center_form_manager').id,
            'target': 'current',
            'views': [(self.env.ref('final.view_final_sport_center_form_manager').id, 'form')],
            'context': {'form_view_initial_mode': 'readonly', 'create': False, 'edit': False},
        }

    def _sync_manager_user(self, vals=None):
        if self.env.context.get("skip_manager_user_sync"):
            return
        for center in self:
            manager = center.manager_id
            if not manager:
                continue

            login = (
                vals.get("manager_login")
                if vals and "manager_login" in vals
                else center.manager_login
            )
            email = (
                vals.get("manager_email")
                if vals and "manager_email" in vals
                else center.manager_email
            )
            password = (
                vals.get("manager_password")
                if vals and "manager_password" in vals
                else center.manager_password
            )

            User = self.env["res.users"]
            manager_group = self.env.ref("final.group_final_manager")
            internal_group = self.env.ref("base.group_user")

            user = manager.user_id
            if not user:
                missing = []
                if not login:
                    missing.append(_("логин"))
                if not email:
                    missing.append(_("e-mail"))
                if not password:
                    missing.append(_("пароль"))
                if missing:
                    raise ValidationError(
                        _(
                            "Для создания пользователя менеджера необходимо заполнить: %s."
                        )
                        % ", ".join(missing)
                    )
                company_id = self.env.company.id
                user_vals = {
                    "name": manager.name or center.name,
                    "login": login,
                    "email": email,
                    "password": password,
                    "company_id": company_id,
                    "company_ids": [(6, 0, [company_id])],
                    "groups_id": [(6, 0, [internal_group.id, manager_group.id])],
                }
                user = User.sudo().create(user_vals)
                manager.sudo().write(
                    {"user_id": user.id, "work_email": email, "name": manager.name}
                )
            else:
                updates = {}
                if login and user.login != login:
                    updates["login"] = login
                if email and user.email != email:
                    updates["email"] = email
                if updates:
                    user.sudo().write(updates)
                if password:
                    user.sudo().write({"password": password})
                add_groups = []
                if manager_group not in user.groups_id:
                    add_groups.append(manager_group.id)
                if internal_group not in user.groups_id:
                    add_groups.append(internal_group.id)
                if add_groups:
                    user.sudo().write({"groups_id": [(4, gid) for gid in add_groups]})
                if email and manager.work_email != email:
                    manager.sudo().write({"work_email": email})
                if manager.name != center.manager_name:
                    manager.sudo().write({"name": center.manager_name})

            center.with_context(skip_manager_user_sync=True).write(
                {
                    "manager_name": manager.name,
                    "manager_login": user.login,
                    "manager_email": user.email,
                    "manager_password": False,
                }
            )

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Автоматически создает цены при открытии формы"""
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and self.env.context.get('active_id'):
            center = self.browse(self.env.context['active_id'])
            if center.exists():
                center._create_default_training_prices()
        return res

    def _create_default_training_prices(self):
        """Автоматически создает записи цен для всех видов тренировок при создании СЦ"""
        TrainingPrice = self.env["final.center.training.price"]
        TrainingType = self.env["final.training.type"]
        for center in self:
            if not center.id:
                continue
            # Получаем все виды тренировок
            training_types = TrainingType.search([("active", "=", True)])
            for training_type in training_types:
                # Проверяем, не создана ли уже запись
                existing = TrainingPrice.search([
                    ("center_id", "=", center.id),
                    ("training_type_id", "=", training_type.id),
                ], limit=1)
                if not existing:
                    TrainingPrice.create({
                        "center_id": center.id,
                        "training_type_id": training_type.id,
                        "price_per_hour": 0.0,  # По умолчанию 0, директор заполнит
                    })

    @api.depends("training_price_ids.price_per_hour", "training_price_ids.training_type_id.code")
    def _compute_training_prices(self):
        """Вычисляет цены на тренировки из training_price_ids"""
        for center in self:
            center.individual_price = 0.0
            center.split_price = 0.0
            center.group_price = 0.0
            for price in center.training_price_ids:
                if price.training_type_id.code == "individual":
                    center.individual_price = price.price_per_hour
                elif price.training_type_id.code == "split":
                    center.split_price = price.price_per_hour
                elif price.training_type_id.code == "group":
                    center.group_price = price.price_per_hour

    def _inverse_training_prices(self):
        """Записывает цены обратно в training_price_ids"""
        TrainingPrice = self.env["final.center.training.price"]
        TrainingType = self.env["final.training.type"]
        for center in self:
            if not center.id:
                continue
            # Получаем виды тренировок
            individual_type = TrainingType.search([("code", "=", "individual")], limit=1)
            split_type = TrainingType.search([("code", "=", "split")], limit=1)
            group_type = TrainingType.search([("code", "=", "group")], limit=1)
            
            # Обновляем или создаем цены
            for code, price_value, training_type in [
                ("individual", center.individual_price, individual_type),
                ("split", center.split_price, split_type),
                ("group", center.group_price, group_type),
            ]:
                if not training_type:
                    continue
                existing = TrainingPrice.search([
                    ("center_id", "=", center.id),
                    ("training_type_id", "=", training_type.id),
                ], limit=1)
                if existing:
                    existing.price_per_hour = price_value
                else:
                    TrainingPrice.create({
                        "center_id": center.id,
                        "training_type_id": training_type.id,
                        "price_per_hour": price_value,
                    })


class FinalTennisCourt(models.Model):
    _name = "final.tennis.court"
    _description = "Tennis Court"

    name = fields.Char(required=True, string="Название корта")
    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        ondelete="cascade",
    )
    work_time_start = fields.Float(
        string="Начало работы (часы)",
        required=True,
    )
    work_time_end = fields.Float(
        string="Окончание работы (часы)",
        required=True,
    )
    training_type_ids = fields.Many2many(
        "final.training.type",
        "final_court_training_rel",
        "court_id",
        "training_type_id",
        string="Виды тренировок",
    )

    @api.onchange("sport_center_id")
    def _onchange_sport_center_id(self):
        for record in self:
            center = record.sport_center_id
            if center:
                record.work_time_start = center.work_time_start
                record.work_time_end = center.work_time_end

    @api.constrains("work_time_start", "work_time_end", "sport_center_id")
    def _check_work_time(self):
        for record in self:
            if record.work_time_start is None or record.work_time_end is None:
                raise ValidationError("Необходимо указать время работы корта.")
            if record.work_time_start < 0 or record.work_time_start >= 24:
                raise ValidationError("Начало работы корта должно быть в диапазоне 0-24.")
            if record.work_time_end <= 0 or record.work_time_end > 24:
                raise ValidationError("Окончание работы корта должно быть в диапазоне 0-24.")
            if record.work_time_start >= record.work_time_end:
                raise ValidationError("Время окончания корта должно быть позже времени начала.")
            center = record.sport_center_id
            if center:
                if record.work_time_start < center.work_time_start or record.work_time_end > center.work_time_end:
                    raise ValidationError(
                        "Время корта должно находиться в пределах рабочего времени спортивного центра."
                    )

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            center_id = vals.get("sport_center_id")
            center = self.env["final.sport.center"].browse(center_id) if center_id else False
            if center:
                vals.setdefault("work_time_start", center.work_time_start)
                vals.setdefault("work_time_end", center.work_time_end)
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        vals = vals.copy()
        if "sport_center_id" in vals:
            center = self.env["final.sport.center"].browse(vals["sport_center_id"])
            if center:
                vals.setdefault("work_time_start", center.work_time_start)
                vals.setdefault("work_time_end", center.work_time_end)
        res = super().write(vals)
        return res

