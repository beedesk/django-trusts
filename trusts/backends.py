from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission, Group

from trusts.models import Trust, TrustManager


class TrustModelBackendMixin(object):
    manager = TrustManager()

    def get_group_permissions(self, user_obj, obj=None):
        """
        Returns a set of permission strings that this user has through his/her
        groups.
        """

        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_group_permissions(user_obj, obj)

        if not Trust.objects.is_content(obj):
            return set()

        perm = Permission.objects.filter(group__trusts=obj.trust, group__user=user_obj)
        return perm


    def get_all_permissions(self, user_obj, obj=None):
        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_all_permissions(user_obj, obj)

        trust = Trust.objects.get_by_content(obj)
        if trust is None:
            return set()

        if not hasattr(user_obj, '_trust_perm_cache'):
            setattr(user_obj, '_trust_perm_cache', dict())
        perm_cache = getattr(user_obj, '_trust_perm_cache')

        if trust.pk not in perm_cache:
            # TODO -- Support Trust.trustees
            trust_perm = self.get_group_permissions(user_obj, obj)
            perm_cache[trust.pk] = trust_perm
        return perm_cache[trust.pk]

        # return self.get_group_permissions(user_obj, obj)


class TrustModelBackend(TrustModelBackendMixin, ModelBackend):
    pass
