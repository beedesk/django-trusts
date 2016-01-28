# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def get_applabel_model(klass):
    return {'applabel': klass._meta.app_label.lower(), 'model': klass._meta.model_name.lower()}
