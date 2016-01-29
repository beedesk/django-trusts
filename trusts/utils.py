# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import six

def get_short_model_name_lower(klass):
    if isinstance(klass, six.string_types):
        return klass.lower()
    return '%s.%s' % (klass._meta.app_label.lower(), klass._meta.model_name)

def get_short_model_name(klass):
    if isinstance(klass, six.string_types):
        return klass
    return '%s.%s' % (klass._meta.app_label, klass._meta.object_name)

def parse_perm_code(perm):
    applabel, action_modelname_permcode = perm.split('.', 1)
    action, modelname_permcode = action_modelname_permcode.rsplit('_', 1)
    modelname, sep, cond = modelname_permcode.partition(':')

    return applabel, modelname, action, cond
