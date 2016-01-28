# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime

from django.db import models
from django.db.models import signals, Q
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

from trusts import ENTITY_MODEL_NAME, PERMISSION_MODEL_NAME, GROUP_MODEL_NAME, DEFAULT_SETTLOR, utils


ROOT_PK = getattr(settings, 'TRUSTS_ROOT_PK', 1)

class TrustManager(models.Manager):
    def get_or_create_settlor_default(self, settlor, defaults={}, **kwargs):
        if 'trust' in kwargs:
            raise TypeError('"%s" are invalid keyword arguments' % 'trust')
        if settlor is None:
            raise ValueError('"settlor" must has a value.')
        if settlor.is_anonymous():
            # @TODO -- Handle anonymous settings
            raise ValueError('Anonymous is not yet supported.')

        try:
            return self.get(settlor=settlor, title='', **kwargs), False
        except Trust.DoesNotExist:
            params = {k: v for k, v in kwargs.items() if '__' not in k}
            params.update(defaults)
            params.update({'title': '', 'trust_id': ROOT_PK})
            trust = self.model(**params)
            trust.save()
            return trust, True

    def get_root(self):
        return self.get(pk=ROOT_PK)

    def filter_by_content(self, obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False

        if Content.is_content_model(klass):
            fieldlookup = Content.get_content_fieldlookup(klass)
            if fieldlookup is None:
                fieldlookup = '%(applabel)s_%(model)s_content' % utils.get_applabel_model(klass)

            filters = {}
            if is_qs:
                filters['%s__in' % fieldlookup] = obj
            else:
                filters[fieldlookup] = obj
            return self.filter(**filters).distinct()

        return self.none()

    def filter_by_user_perm(self, user, **kwargs):
        if 'group__user' in kwargs:
            raise TypeError('"%s" are invalid keyword arguments' % 'group__user')

        return self.filter(Q(groups__user=user) | Q(trustees__entity=user), **kwargs)


class ReadonlyFieldsMixin(object):
    def __init__(self, *args, **kwargs):
        super(ReadonlyFieldsMixin, self).__init__(*args, **kwargs)

        if hasattr(self, '_readonly_fields'):
            self._state.init_fields = {
                field: getattr(self, field) for field in self._readonly_fields
                        if hasattr(self, field)
            }

    def clean(self):
        super(ReadonlyFieldsMixin, self).clean()

        if hasattr(self, '_readonly_fields') and hasattr(self._state, 'init_fields'):
            for field in self._readonly_fields:
                if field in self._state.init_fields:
                    saved_value = self._state.init_fields[field]
                    if saved_value != getattr(self, field):
                        raise ValidationError('Field "%s" is readonly.' % 'trust')


class Content(ReadonlyFieldsMixin, models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='%(app_label)s_%(class)s_content',
                default=ROOT_PK, null=False, blank=False)
    _contents = {}

    class Meta:
        abstract = True
        default_permissions = ('add', 'change', 'delete', 'read',)

    @staticmethod
    def register_content(klass, fieldlookup=None):
        if fieldlookup is None:
            content_model_fields = [f for f in klass._meta.fields if f.rel is not None and f.name == 'trust']
            if len(content_model_fields) != 1:
                raise AttributeError('Expect "trust" field in model %s.' % klass)
        Content._contents[klass] = fieldlookup

    @staticmethod
    def is_content_model(klass):
        if klass in Content._contents.keys():
            return True
        return False

    @staticmethod
    def get_content_fieldlookup(klass):
        if klass in Content._contents.keys():
            return Content._contents[klass]
        return None

    @staticmethod
    def is_content(obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False
        return Content.is_content_model(klass)


class Trust(Content):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=40, null=False, blank=False, verbose_name=_('title'))
    settlor = models.ForeignKey(ENTITY_MODEL_NAME, default=DEFAULT_SETTLOR, null=False, blank=False)
    groups = models.ManyToManyField(GROUP_MODEL_NAME,
                related_name='trusts', blank=True, verbose_name=_('groups'),
                help_text=_('The groups this trust grants permissions to. A user will'
                            'get all permissions granted to each of his/her group.'),
    )
    _readonly_fields = ('trust', 'settlor',)

    objects = TrustManager()

    class Meta:
        unique_together = ('settlor', 'title')
        default_permissions = ('add', 'change', 'delete', 'read',)

    def __str__(self):
        settlor_str = ' of %s' % str(self.settlor) if self.settlor is not None else ''
        return 'Trust[%s]: "%s"' % (self.id, self.title)
Content.register_content(Trust)


class TrustUserPermission(models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='trustees', null=False, blank=False)
    entity = models.ForeignKey(ENTITY_MODEL_NAME, related_name='trustpermissions', null=False, blank=False)
    permission = models.ForeignKey(PERMISSION_MODEL_NAME, related_name='trustentities', null=False, blank=False)

    class Meta:
        unique_together = ('trust', 'entity', 'permission')


class Junction(ReadonlyFieldsMixin, models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='%(app_label)s_%(class)s',
                null=False, blank=False)
    _readonly_fields = ('trust',)
    _junctions = dict()

    class Meta:
        abstract = True
        default_permissions = ()

    @staticmethod
    def register_junction(content_klass, junction_klass):
        Junction._junctions[content_klass] = junction_klass
        fieldlookup = '%(applabel)s_%(model)s__content' % utils.get_applabel_model(junction_klass)
        Content.register_content(content_klass, fieldlookup)

    @staticmethod
    def get_junction_model(klass):
        return Junction._junctions[klass]

    @staticmethod
    def is_junction_content_model(klass):
        if klass in Junction._junctions:
            return True
        return False

    @classmethod
    def get_content_model(cls):
        # introspect for the content model class with the easy case
        content_model_fields = [f for f in cls._meta.fields if f.rel is not None and f.name != 'trust']
        if len(content_model_fields) == 1:
            return content_model_fields[0].rel.to

        raise NotImplementedError('Juctnion\'s classmethod "get_content_model" is not implemented.')


def register_content_junction(sender, **kwargs):
    if issubclass(sender, Junction):
        content_model = sender.get_content_model()
        Junction.register_junction(content_model, sender)
    elif issubclass(sender, Content):
        Content.register_content(sender)
signals.class_prepared.connect(register_content_junction)


