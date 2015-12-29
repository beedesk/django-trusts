from datetime import datetime

from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.utils.translation import ugettext_lazy as _


class TrustManager(models.Manager):
    contents = set()
    junctions = set()

    def is_content(self, obj):
        klass = obj.__class__
        if klass in self.contents and hasattr(obj, 'trust'):
            return True
        if klass in self.junctions and hasattr(obj, 'trust'):
            return True
        return False

    def get_by_content(self, obj):
        klass = obj.__class__
        if klass in self.contents and hasattr(obj, 'trust'):
            return getattr(obj, 'trust')
        return None

    def register_content(self, klass):
        self.contents.add(klass)

    def register_junction(self, klass):
        self.junctions.add(klass)


class Trust(models.Model):
    id = models.AutoField(primary_key=True)
    settlor = models.ForeignKey(User, null=False, blank=False)
    ''' TODO -- Support trustees, similar to user_permissions in PermissionMixin
    trustees = models.ManyToManyField(Permission,
            related_name="trusts", blank=True, verbose_name=_('trustees'),
            help_text=_('Specific trustees for this trust.')
    )
    '''
    groups = models.ManyToManyField(Group,
            related_name='trusts', blank=True, verbose_name=_('groups'),
            help_text=_('The groups this trust grants permissions to. A user will',
                        'get all permissions granted to each of his/her group.'),
    )

    objects = TrustManager()

    def __str__(self):
        return 'Trust (%s)' % (self.id)


class ContentMixin(models.Model):
    trust = models.ForeignKey(Trust, null=False, blank=False)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(ContentMixin, self).__init__(*args, **kwargs)
        Trust.objects.register_content(self.__class__)


class Junction(models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        if not self.hasattr('trust'):
            raise 'Expect `trust` ForeignKey field.'

        super(Junction, self).__init__(*args, **kwargs)
        manager.register_junction(self.__class__)
