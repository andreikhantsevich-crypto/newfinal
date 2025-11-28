# -*- coding: utf-8 -*-
{
    'name': 'final',
    'version': '18.0.0.0.0',
    'category': 'Custom',
    'summary': 'Пустой модуль для дальнейшей разработки.',
    'description': """
        Модуль final.
        =============

        Заготовка для реализации требований проекта.
    """,
    'author': 'final',
    'website': '',
    'depends': ['base', 'hr', 'calendar'],
    'data': [
        'security/final_security.xml',
        'security/ir.model.access.csv',
        'data/training_type_data.xml',
        'views/final_training_type_views.xml',
        'views/final_order_views.xml',
        'views/hr_employee_views.xml',
        'views/final_trainer_views.xml',
        'views/create_trainer_wizard_views.xml',
        'views/attach_trainer_wizard_views.xml',
        'views/apply_trainer_wizard_views.xml',
        'views/trainer_cabinet_views.xml',
        'views/final_center_training_price_views.xml',
        'views/final_training_booking_views.xml',
        'views/training_booking_wizard_views.xml',
        'views/final_menu.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
