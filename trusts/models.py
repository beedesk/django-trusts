from datetime import datetime

from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.utils.translation import ugettext_lazy as _


class TrustManager(models.Manager):
    contents = set()
    junctions = dict()

    def is_content(self, obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False

        if klass in self.contents:
            if is_qs or hasattr(obj, 'trust'):
                return True
        elif klass in self.junctions:
            return True

        return False

    def get_by_content(self, obj):
        if isinstance(obj, models.QuerySet):
            klass = obj.model
            is_qs = True
        else:
            klass = obj.__class__
            is_qs = False

        if klass in self.contents:
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

    def register_content(self, klass):
        self.contents.add(klass)

    def register_junction(self, content_klass, junction_klass):
        self.junctions[content_klass] = junction_klass


class Trust(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=40, default='', verbose_name='Title',
                null=False, blank=False)
    settlor = models.ForeignKey(User, null=False, blank=False)
    trustees = models.ManyToManyField(User,
            related_name="trusts", blank=True, verbose_name=_('trustees'),
            help_text=_('Specific trustees for this trust.')
    )
    groups = models.ManyToManyField(Group,
            related_name='trusts', blank=True, verbose_name=_('groups'),
            help_text=_('The groups this trust grants permissions to. A user will',
                        'get all permissions granted to each of his/her group.'),
    )

    objects = TrustManager()

    class Meta:
        unique_together = ('settlor', 'title')

    def __str__(self):
        return 'Trust[%s]: "%s" of "%s"' % (self.id, self.title, self.settlor)


class ContentMixin(models.Model):
    trust = models.ForeignKey('trusts.Trust', related_name='content', null=False, blank=False)

    class Meta:
        default_permissions = ('add', 'change', 'delete', 'read')
        abstract = True


class Junction(models.Model):
    trust = models.ForeignKey('trusts.Trust', null=False, blank=False)

    class Meta:
        abstract = True
