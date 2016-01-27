from __future__ import unicode_literals

from django.db.models import Q, QuerySet
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from trusts.models import Trust, Content
from trusts import get_permission_model


class TrustModelBackendMixin(object):
    perm_model = get_permission_model()

    @staticmethod
    def _get_perm_code(perm):
        return '%s.%s' % (
            perm.content_type.app_label, perm.codename
        )

    def _get_trusts(self, obj):
        if not Content.is_content(obj):
            return []

        trusts = Trust.objects.get_by_content(obj)
        if trusts is None:
            return []

        if not hasattr(trusts, '__iter__'):
            trusts = [trusts]

        return trusts

    def get_group_permissions(self, user_obj, obj=None):
        """
        Returns a set of permission strings that this user has through his/her
        groups.
        """

        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_group_permissions(user_obj, obj)

        if Content.is_content(obj):
            filter = self.perm_model.objects.filter
            return filter(group__trusts=self._get_trusts(obj), group__user=user_obj)

        return []

    def get_all_permissions(self, user_obj, obj=None):
        if user_obj.is_anonymous() or obj is None:
            return super(TrustModelBackendMixin, self).get_all_permissions(user_obj, obj)

        if not hasattr(user_obj, '_trust_perm_cache'):
            setattr(user_obj, '_trust_perm_cache', dict())
        perm_cache = getattr(user_obj, '_trust_perm_cache')

        trusts = self._get_trusts(obj)
        if len(trusts):
            all_perms = []
            for trust in trusts:
                if trust.pk not in perm_cache.keys():
                    trust_perm = set([self._get_perm_code(p) for p in
                        self.perm_model.objects.filter(
                            Q(group__trusts=trust, group__user=user_obj) |
                            Q(trustentities__trust=trust, trustentities__entity=user_obj)
                        )
                        .order_by('group__trusts', 'trustentities__entity')
                    ])

                    perm_cache[trust.pk] = trust_perm
                else:
                    trust_perm = perm_cache[trust.pk]

                all_perms.append(trust_perm)
            return set.intersection(*all_perms)
        return []


class TrustModelBackend(TrustModelBackendMixin, ModelBackend):
    pass
