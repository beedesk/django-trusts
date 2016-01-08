from datetime import datetime

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User, Group, Permission
from django.utils.translation import ugettext_lazy as _

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
            params.update({'settlor': settlor, 'title': '', 'trust': root_trust})
            trust = self.model(**params)
            trust.save()
            trust.trustees.add(settlor)
            created = True

        return trust, created

    def get_root(self):
        return self.get(pk=1)

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

        return self.filter(Q(groups__user=user) | Q(trustees=user), **kwargs)

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


class Trust(models.Model):
    id = models.AutoField(primary_key=True)
    trust = models.ForeignKey('self', related_name='content', default=1, null=False, blank=False)
    title = models.CharField(max_length=40, null=False, blank=False, verbose_name=_('title'))
    settlor = models.ForeignKey(User, null=True, blank=False)
    trustees = models.ManyToManyField(User,
                related_name="trusts", blank=True, verbose_name=_('trustees'),
                help_text=_('Specific trustees for this trust.')
    )
    groups = models.ManyToManyField(Group,
                related_name='trusts', blank=True, verbose_name=_('groups'),
                help_text=_('The groups this trust grants permissions to. A user will'
                            'get all permissions granted to each of his/her group.'),
    )

    objects = TrustManager()

    class Meta:
        unique_together = ('settlor', 'title')
        default_permissions = ('add', 'change', 'delete', 'read')

    def __str__(self):
        settlor_str = ' of %s' % str(self.settlor) if self.settlor is not None else ''
        return 'Trust[%s]: "%s"' % (self.id, self.title)


class ContentMixin(models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='content', null=False, blank=False)

    class Meta:
        abstract = True
        default_permissions = ('add', 'change', 'delete', 'read')


class Junction(models.Model):
    trust = models.ForeignKey('trusts.Trust', null=False, blank=False)

    class Meta:
        abstract = True
