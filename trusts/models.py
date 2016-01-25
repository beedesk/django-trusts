from datetime import datetime

from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from trusts import ENTITY_MODEL_NAME, PERMISSION_MODEL_NAME, GROUP_MODEL_NAME, DEFAULT_SETTLOR


ROOT_PK = getattr(settings, 'TRUSTS_ROOT_PK', 1)

class TrustManager(models.Manager):
    contents = set()
    junctions = dict()

    def get_or_create_settlor_default(self, settlor, defaults={}, **kwargs):
        if 'trust' in kwargs:
            raise TypeError('"%s" are invalid keyword arguments' % 'trust')
        if settlor is None:
            raise ValueError('"settlor" must has a value.')
        if settlor.is_anonymous():
            # @TODO -- Handle anonymous settings
            raise ValueError('Anonymous is not yet supported.')

        created = False

        root_trust = self.get_root()
        try:
            trust = self.get(settlor=settlor, title='', **kwargs)
        except Trust.DoesNotExist:
            params = {k: v for k, v in kwargs.items() if '__' not in k}
            params.update(defaults)
            params.update({'title': '', 'trust': root_trust})
            trust = self.model(**params)
            trust.save()
            created = True

        return trust, created

    def get_root(self):
        return self.get(pk=ROOT_PK)

    def get_by_content(self, obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False

        if klass == Trust or klass in self.contents:
            if is_qs:
                return obj.values('trust').distinct()
            else:
                if hasattr(obj, 'trust'):
                    return getattr(obj, 'trust')
        elif klass in self.junctions:
            junction_klass = self.junctions[klass]
            if is_qs:
                return junction_klass.objects.filter(content=obj).values('trust').distinct()
            else:
                junction = junction_klass.objects.filter(content=obj).select_related('trust').first()

                if junction is not None:
                    return getattr(junction, 'trust')
        return None

    def filter_by_user_perm(self, user, **kwargs):
        if 'group__user' in kwargs:
            raise TypeError('"%s" are invalid keyword arguments' % 'group__user')

        return self.filter(Q(groups__user=user) | Q(trustees__entity=user), **kwargs)

    def is_content(self, obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False

        if klass == Trust or klass in self.contents:
            if is_qs or hasattr(obj, 'trust'):
                return True
        elif klass in self.junctions:
            return True

        return False

    def register_content(self, klass):
        self.contents.add(klass)

    def register_junction(self, content_klass, junction_klass):
        self.junctions[content_klass] = junction_klass


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


class Trust(ReadonlyFieldsMixin, models.Model):
    id = models.AutoField(primary_key=True)
    trust = models.ForeignKey('self', related_name='content', default=ROOT_PK, null=False, blank=False)
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


class TrustUserPermission(models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='trustees', null=False, blank=False)
    entity = models.ForeignKey(ENTITY_MODEL_NAME, related_name='trustpermissions', null=False, blank=False)
    permission = models.ForeignKey(PERMISSION_MODEL_NAME, related_name='trustentities', null=False, blank=False)

    class Meta:
        unique_together = ('trust', 'entity', 'permission')


class ContentMixin(ReadonlyFieldsMixin, models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='content', null=False, blank=False)
    _readonly_fields = ('trust',)

    class Meta:
        abstract = True
        default_permissions = ('add', 'change', 'delete', 'read',)


class Junction(ReadonlyFieldsMixin, models.Model):
    trust = models.ForeignKey('trusts.Trust', null=False, blank=False)
    _readonly_fields = ('trust',)

    class Meta:
        abstract = True
