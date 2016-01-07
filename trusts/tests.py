import os
import json
import settings
import unittest

from decimal import Decimal
from urllib import urlencode
from urlparse import urlparse
from datetime import date, datetime, timedelta

from django.apps import apps
from django.db import models, connection, IntegrityError
from django.db.models import F
from django.db.models.base import ModelBase
from django.core.management.color import no_style
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.management import create_permissions
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.management import update_all_contenttypes, update_contenttypes
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT, Client

from trusts.models import Trust, TrustManager, ContentMixin, Junction
from trusts.backends import TrustModelBackend


def create_test_users(test):
    # Create a user.
    test.username = 'daniel'
    test.password = 'pass'
    test.user = User.objects.create_user(test.username, 'daniel@example.com', test.password)
    test.user.is_active = True
    test.user.save()

    # Create another
    test.name1 = 'anotheruser'
    test.pass1 = 'pass'
    test.user1 = User.objects.create_user(test.name1, 'another@example.com', test.pass1)
    test.user1.is_active = True
    test.user1.save()

def delete_test_users(test):
    test.user.delete()
    test.user1.delete()


class TrustTest(TestCase):
    fixtures = ['0000_add_root_trust.json']

    def setUp(self):
        super(TrustTest, self).setUp()

        create_test_users(self)

    def tearDown(self):
        super(TrustTest, self).tearDown()

    def test_root(self):
        root = Trust.objects.get_root()
        self.assertEqual(root.pk, 1)
        self.assertEqual(root.pk, root.trust.pk)
        self.assertEqual(Trust.objects.filter(trust=F('id')).count(), 1)

    def test_trust_unique_together_title_settlor(self):
        # Create `Title A` for user
        self.trust = Trust(settlor=self.user, title='Title A', trust=Trust.objects.get_root())
        self.trust.save()

        # Create `Title A` for user1
        self.trust1 = Trust(settlor=self.user1, title='Title A', trust=Trust.objects.get_root())
        self.trust1.save()

        # Empty string title should be allowed (reserved for settlor_default)
        self.trust = Trust(settlor=self.user, title='', trust=Trust.objects.get_root())
        self.trust.save()

        # Create `Title A` for user, again (should fail)
        try:
            self.trust2 = Trust(settlor=self.user, title='Title A', trust=Trust.objects.get_root())
            self.trust2.save()
            self.fail('Expected IntegrityError not raised.')
        except IntegrityError as ie:
            pass

    def test_read_permissions_added(self):
        ct = ContentType.objects.get_for_model(Trust)
        self.assertIsNotNone(Permission.objects.get(
            content_type=ct,
            codename='%s_%s' % ('read', ct.model)
        ))


class RuntimeModel(object):
    """
    Base class for tests of model mixins. To use, subclass and specify
    the mixin class variable. A model using the mixin will be made
    available in self.model.
    """

    def create_test_model(self):
        # Create the schema for our test model
        self._style = no_style()
        sql, _ = connection.creation.sql_create_model(self.model, self._style)

        with connection.cursor() as c:
            for statement in sql:
                c.execute(statement)

        app_config = apps.get_app_config(self.model._meta.app_label)
        update_contenttypes(app_config, verbosity=1, interactive=False)
        create_permissions(app_config, verbosity=1, interactive=False)

    def destroy_test_model(self):
        # Delete the schema for the test model
        sql = connection.creation.sql_destroy_model(self.model, (), self._style)

        with connection.cursor() as c:
            for statement in sql:
                c.execute(statement)


class TrustContentMixin(object):
    fixtures = ['0000_add_root_trust.json']

    def reload_test_users(self):
        # reloading user to purge the _trust_perm_cache
        self.user = User._default_manager.get(pk=self.user.pk)
        self.user1 = User._default_manager.get(pk=self.user1.pk)

    def create_test_fixtures(self):
        self.group = Group(name="Test Group")
        self.group.save()

    def delete_test_fixtures(self):
        # We need to delete those fixtures that has foreign key constraints on
        # the ModelBase() we created, otherwise we would fail at ModelBase() deletion

        if hasattr(self, 'trust1') and self.trust1 is not None and self.trust.pk is not None:
            self.trust1.delete()

        if hasattr(self, 'trust') and self.trust is not None and self.trust.pk is not None:
            self.trust.delete()

        if hasattr(self, 'group') and self.group is not None and self.group.pk is not None:
            self.group.delete()

    def set_perms(self):
        for codename in ['change', 'add', 'delete']:
            setattr(self, 'perm_%s' % codename,
                '%s.%s_%s' % (self.app_label, codename, self.model_name)
            )

    def get_perm_code(self, perm):
        return '%s.%s' % (
            perm.content_type.app_label, perm.codename
         )

    def set_perms(self):
        for codename in ['change', 'add', 'delete']:
            setattr(self, 'perm_%s' % codename,
                Permission.objects.get_by_natural_key('%s_%s' % (codename, self.model_name), self.app_label, self.model_name)
            )

    def setUp(self):
        super(TrustContentMixin, self).setUp()

        self.prepare_test_model()

        create_test_users(self)

        self.create_test_fixtures()

        self.app_label = self.model._meta.app_label
        self.model_name = self.model._meta.model_name

        self.set_perms()

    def tearDown(self):
        super(TrustContentMixin, self).tearDown()

        self.delete_test_fixtures()

        delete_test_users(self)

        self.unprepare_test_model()

    def assertIsIterable(self, obj, msg='Not an iterable'):
        return self.assertTrue(hasattr(obj, '__iter__'))

    def test_unknown_content(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust.save()

        perm = TrustModelBackend().get_group_permissions(self.user, {})
        self.assertIsNotNone(perm)
        self.assertIsIterable(perm)
        self.assertEqual(len(perm), 0)

        trust = Trust.objects.get_by_content(self.user)
        self.assertIsNone(trust)

    def test_user_not_in_group_has_no_perm(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root(), title='trust 1')
        self.trust.save()

        self.content = self.create_content(self.trust)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)

        self.reload_test_users()

        self.perm_change.group_set.add(self.group)
        self.perm_change.save()

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

    def test_user_in_group_has_no_perm(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust.save()

        self.content = self.create_content(self.trust)

        self.test_user_not_in_group_has_no_perm()

        self.reload_test_users()

        self.user.groups.add(self.group)

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

    def test_user_in_group_has_trust(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root(), title='a title')
        self.trust.save()
        self.content = self.create_content(self.trust)

        self.trust1 = Trust(settlor=self.user1, trust=Trust.objects.get_root())
        self.trust1.save()

        self.test_user_in_group_has_no_perm()

        self.reload_test_users()

        self.trust.groups.add(self.group)

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertTrue(had)

        had = self.user.has_perm(self.get_perm_code(self.perm_add), self.content)
        self.assertFalse(had)

    def test_has_trust(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust.save()
        self.content = self.create_content(self.trust)

        self.trust1 = Trust(settlor=self.user1, trust=Trust.objects.get_root())
        self.trust1.save()

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)
        had = self.user.has_perm(self.get_perm_code(self.perm_add), self.content)
        self.assertFalse(had)

        trust = Trust(settlor=self.user, title='Test trusts')
        trust.save()

        self.reload_test_users()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

        self.user.user_permissions.add(self.perm_change)

        self.reload_test_users()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

        self.trust.trustees.add(self.user)

        self.reload_test_users()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertTrue(had)

    def test_has_trust_disallow_no_perm_content(self):
        self.test_has_trust()

        self.content1 = self.create_content(self.trust1)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content1)
        self.assertFalse(had)

    def test_has_trust_disallow_no_perm_perm(self):
        self.test_has_trust()

        had = self.user.has_perm(self.perm_add, self.content)
        self.assertFalse(had)

    def test_get_or_create_default_trust(self):
        trust, created = Trust.objects.get_or_create_settlor_default(self.user)
        content = self.create_content(trust)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), content)
        self.assertFalse(had)

        self.user.user_permissions.add(self.perm_change)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), content)

        self.reload_test_users()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), content)
        self.assertTrue(had)

    def test_has_trust_queryset(self):
        self.test_has_trust()

        self.content1 = self.create_content(self.trust)

        self.reload_test_users()
        qs = self.model.objects.filter(pk__in=[self.content.pk, self.content1.pk])
        had = self.user.has_perm(self.get_perm_code(self.perm_change), qs)
        self.assertTrue(had)

    def test_mixed_trust_queryset(self):
        self.test_has_trust()

        self.content1 = self.create_content(self.trust1)
        self.content2 = self.create_content(self.trust)

        self.reload_test_users()
        qs = self.model.objects.all()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), qs)

        self.assertFalse(had)

    def test_read_permissions_added(self):
        ct = ContentType.objects.get_for_model(self.model)
        self.assertIsNotNone(Permission.objects.get(
            content_type=ct,
            codename='%s_%s' % ('read', ct.model)
        ))


class ContentMixinTrustTestCase(TrustContentMixin, RuntimeModel, TestCase):
    mixin = ContentMixin
    contents = []

    def prepare_test_model(self):
        # Create a dummy model which extends the mixin
        self.model = ModelBase('TestModel' + self.mixin.__name__, (self.mixin,),
            {'__module__': self.mixin.__module__})
        self.model.id = models.AutoField(primary_key=True)

        self.create_test_model()

        Trust.objects.register_content(self.model)

    def unprepare_test_model(self):
        self.destroy_test_model()

    def create_content(self, trust):
        content = self.model(trust=trust)
        content.save()

        self.contents.insert(0, content)

        return content

    def delete_contents(self):
        pass

class JunctionTrustTestCase(TrustContentMixin, TestCase):
    class GroupJunction(Junction):
        content = models.ForeignKey(Group, unique=True, null=False, blank=False)

    def prepare_test_model(self):
        self.model = Group
        self.junction = self.GroupJunction
        Trust.objects.register_junction(self.model, self.junction)

    def unprepare_test_model(self):
        pass

    def create_content(self, trust):
        import uuid

        content = self.model(name=str(uuid.uuid4()))
        content.save()

        junction = self.junction(content=content, trust=trust)
        junction.save()

        return content

    def delete_contents(self):
        pass

    @unittest.expectedFailure
    def test_read_permissions_added(self):
        super(JunctionTrustTestCase, self).test_read_permissions_added()


class TrustTrustTestCase(TrustContentMixin, TestCase):
    def prepare_test_model(self):
        self.model = Trust

    def unprepare_test_model(self):
        pass

    def create_content(self, trust):
        content = Trust(title='Test Trust as Content', trust=trust)
        content.save()

        return content

    def delete_contents(self):
        pass
