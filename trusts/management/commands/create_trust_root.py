# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.conf import settings

def create_root_trust(Trust, pk, settlor, title):
    kwargs = {'id': pk, 'title': title}
    if settlor is not None:
        kwargs.update({'settlor_id': settlor})

    trust = Trust(**kwargs)
    trust.trust = trust
    trust.save()


class Command(BaseCommand):
    help = "Create a self-referencing trust as the root of all trust."

    def handle(self, **options):
        self.verbosity = int(options.get('verbosity', 1))

        pk = getattr(settings, 'TRUSTS_ROOT_PK', 1)
        settlor = getattr(settings, 'TRUSTS_ROOT_SETTLOR', None)
        title = getattr(settings, 'TRUSTS_ROOT_TITLE', 'In Trust We Trust')

        if 'apps' in options:
            apps = options['apps']
            Trust = apps.get_model('trusts', 'trust')
        else:
            from trusts.models import Trust
        create_root_trust(Trust, pk, settlor, title)
