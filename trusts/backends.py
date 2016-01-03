from __future__ import unicode_literals

from django.db.models import Q, QuerySet
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission, Group

from trusts.models import Trust


class TrustModelBackendMixin(object):
    def get_group_permissions(self, user_obj, obj=None):
        """
        Returns a set of permission strings that this user has through his/her
        groups.
        """

        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_group_permissions(user_obj, obj)

        if not Trust.objects.is_content(obj):
            return set()

        return Permission.objects.filter(group__trusts=obj.trust, group__user=user_obj)

    def get_all_permissions(self, user_obj, obj=None):
        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_all_permissions(user_obj, obj)

        trusts = Trust.objects.get_by_content(obj)

        if trusts is None:
            return set()

        if not hasattr(trusts, '__iter__'):
            trusts = [trusts]

        if not hasattr(user_obj, '_trust_perm_cache'):
            setattr(user_obj, '_trust_perm_cache', dict())
        perm_cache = getattr(user_obj, '_trust_perm_cache')

        all_perms = []
        for trust in trusts:
            if isinstance(trust, Trust):
                pk = trust.pk
            else:
                pk = trust['trust']
            if pk not in perm_cache:
                trust_perm = set(Permission.objects.filter(
                    Q(group__trusts=pk, group__user=user_obj) |
                    Q(user__trusts=pk, user=user_obj)
                ).order_by('group__trusts', 'user__trusts'))

                perm_cache[pk] = trust_perm
            else:
                trust_perm = perm_cache[pk]

            all_perms.append(trust_perm)

        return set.intersection(*all_perms)


class TrustModelBackend(TrustModelBackendMixin, ModelBackend):
    pass
