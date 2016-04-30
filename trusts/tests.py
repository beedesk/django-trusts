import os
import json
import unittest

from decimal import Decimal
from urllib import urlencode
from urlparse import urlparse
from datetime import date, datetime, timedelta
from mock import Mock

from django.apps import apps
from django.db import models, connection, IntegrityError
from django.db.models import F
from django.db.models.base import ModelBase
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.color import no_style
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.decorators import login_required
from django.contrib.auth.management import create_permissions
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.management import update_contenttypes
from django.test import TestCase, TransactionTestCase
from django.test.client import MULTIPART_CONTENT, Client
from django.http.request import HttpRequest

from trusts.models import Trust, TrustManager, Content, Junction, \
                          Role, RolePermission, TrustUserPermission
from trusts.backends import TrustModelBackend
from trusts.decorators import permission_required, P, K, G, O


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

def get_or_create_root_user(test):
    # Create a user.

    pk = getattr(settings, 'TRUSTS_ROOT_SETTLOR', 1)
    test.user_root, created = User.objects.get_or_create(pk=pk)

def reload_test_users(self):
    # reloading user to purge the _trust_perm_cache
    self.user_root = User._default_manager.get(pk=self.user_root.pk)
    self.user = User._default_manager.get(pk=self.user.pk)
    self.user1 = User._default_manager.get(pk=self.user1.pk)


class TrustTest(TestCase):
    ROOT_PK = getattr(settings, 'TRUSTS_ROOT_PK', 1)
    SETTLOR_PK = getattr(settings, 'TRUSTS_ROOT_SETTLOR', None)

    def setUp(self):
        super(TrustTest, self).setUp()

        call_command('create_trust_root')

        get_or_create_root_user(self)

        create_test_users(self)

    def get_perm_code(self, perm):
        return '%s.%s' % (
            perm.content_type.app_label, perm.codename
         )

    def test_root(self):
        root = Trust.objects.get_root()
        self.assertEqual(root.pk, self.ROOT_PK)
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

    def test_filter_by_user_perm(self):
        self.trust1, created = Trust.objects.get_or_create_settlor_default(self.user)

        self.trust2 = Trust(settlor=self.user, title='Title 0A', trust=Trust.objects.get_root())
        self.trust2.save()
        tup = TrustUserPermission(trust=self.trust2, entity=self.user, permission=Permission.objects.first())
        tup.save()

        self.trust3 = Trust(settlor=self.user, title='Title 0B', trust=Trust.objects.get_root())
        self.trust3.save()

        self.trust4 = Trust(settlor=self.user1, title='Title 1A', trust=Trust.objects.get_root())
        self.trust4.save()
        tup = TrustUserPermission(trust=self.trust4, entity=self.user, permission=Permission.objects.first())
        tup.save()

        self.trust5 = Trust(settlor=self.user1, title='Title 1B', trust=Trust.objects.get_root())
        self.trust5.save()
        self.group = Group(name='Group A')
        self.group.save()
        self.user.groups.add(self.group)

        self.trust5.groups.add(self.group)

        self.trust6 = Trust(settlor=self.user1, title='Title 1C', trust=Trust.objects.get_root())
        self.trust6.save()

        trusts = Trust.objects.filter_by_user_perm(self.user)
        trust_pks = [t.pk for t in trusts]
        self.assertEqual(trusts.count(), 3)
        self.assertTrue(self.trust2.id in trust_pks)
        self.assertTrue(self.trust4.id in trust_pks)
        self.assertTrue(self.trust5.id in trust_pks)

    def test_change_trust(self):
        self.trust1 = Trust(settlor=self.user, title='Title 0A', trust=Trust.objects.get_root())
        self.trust1.save()

        self.trust2 = Trust(settlor=self.user1, title='Title 1A', trust=Trust.objects.get_root())
        self.trust2.save()

        try:
            self.trust2.trust = self.trust1
            self.trust2.full_clean()
            self.fail('Expected ValidationError not raised.')
        except ValidationError as ve:
            pass

class DecoratorsTest(TestCase):
    def setUp(self):
        super(DecoratorsTest, self).setUp()

        call_command('create_trust_root')

        get_or_create_root_user(self)

        create_test_users(self)

        self.request = HttpRequest()
        setattr(self.request, 'user', self.user)
        self.request.META['SERVER_NAME'] = 'beedesk.com'
        self.request.META['SERVER_PORT'] = 80

    def test_permission_required(self):
        self.group = Group(name='Group A')
        self.group.save()

        # test a) has_perms() == False
        mock = Mock(return_value='Response')
        has_perms = Mock(return_value=False)
        self.user.has_perms = has_perms

        decorated_func = permission_required(
            'auth.read_group',
            fieldlookups_kwargs={'pk': 'pk'},
            raise_exception=False
        )(mock)
        response = decorated_func(self.request, pk=self.group.pk)

        self.assertFalse(mock.called)
        self.assertTrue(response.status_code, 403)
        self.assertTrue(has_perms.called)
        self.assertEqual(has_perms.call_args[0][0], ('auth.read_group',))
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.group.pk)

        # test b) has_perms() == True
        mock = Mock(return_value='Response')
        has_perms = Mock(return_value=True)
        self.user.has_perms = has_perms

        decorated_func = permission_required(
            'auth.read_group',
            fieldlookups_kwargs={'pk': 'pk'}
        )(mock)
        response = decorated_func(self.request, pk=self.group.pk)

        self.assertTrue(mock.called)
        mock.assert_called_with(self.request, pk=self.group.pk)
        self.assertEqual(response, 'Response')
        self.assertEqual(has_perms.call_args[0][0], ('auth.read_group',))
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.group.pk)

    def test_permission_required_P(self):
        self.group = Group(name='Group B')
        self.group.save()

        # test a) has_perms() == False, single P used
        mock = Mock(return_value='Response')
        has_perms = Mock(return_value=False)
        self.user.has_perms = has_perms

        decorated_func = permission_required(
            P('auth.read_group', fieldlookups_kwargs={'pk': 'pk'}),
            raise_exception=False
        )(mock)
        response = decorated_func(self.request, pk=self.group.pk)

        self.assertFalse(mock.called)
        self.assertTrue(response.status_code, 403)
        self.assertTrue(has_perms.called)
        self.assertEqual(has_perms.call_args[0][0], ('auth.read_group',))
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.group.pk)

        # test d) has_perms() == True, P & P used
        mock = Mock(return_value='Response')
        has_perms = Mock(return_value=True)
        self.user.has_perms = has_perms

        decorated_func = permission_required(
            P('auth.read_group', fieldlookups_kwargs={'pk': 'pk'}) &
            P('auth.add_group', fieldlookups_kwargs={'pk': 'pk'}),
            raise_exception=False
        )(mock)
        response = decorated_func(self.request, pk=self.group.pk)

        self.assertTrue(mock.called)
        mock.assert_called_with(self.request, pk=self.group.pk)
        self.assertEqual(response, 'Response')
        self.assertEqual(has_perms.call_args[0][0], ('auth.add_group',))
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.group.pk)


class RuntimeModel(object):
    """
    Base class for tests of runtime model mixins.
    """

    def setUp(self):
        # Create the schema for our test model
        self._style = no_style()
        sql, _ = connection.creation.sql_create_model(self.model, self._style)

        with connection.cursor() as c:
            for statement in sql:
                c.execute(statement)

        content_model = self.content_model if hasattr(self, 'content_model') else self.model
        app_config = apps.get_app_config(content_model._meta.app_label)
        update_contenttypes(app_config, verbosity=1, interactive=False)
        create_permissions(app_config, verbosity=1, interactive=False)

        super(RuntimeModel, self).setUp()

    def workaround_contenttype_cache_bug(self):
        # workaround bug: https://code.djangoproject.com/ticket/10827
        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.clear_cache()

    def tearDown(self):
        # Delete the schema for the test model
        content_model = self.content_model if hasattr(self, 'content_model') else self.model
        sql = connection.creation.sql_destroy_model(self.model, (), self._style)

        with connection.cursor() as c:
            for statement in sql:
                c.execute(statement)

        self.workaround_contenttype_cache_bug()

        super(RuntimeModel, self).tearDown()

        apps.get_app_config('trusts').models.pop(self.model._meta.model_name.lower())


class ContentModel(object):
    def create_test_fixtures(self):
        self.group = Group(name="Test Group")
        self.group.save()

    def get_perm_code(self, perm):
        return '%s.%s' % (
            perm.content_type.app_label, perm.codename
         )

    def set_perms(self):
        for codename in ['change', 'add', 'delete', 'read']:
            setattr(self, 'perm_%s' % codename,
                Permission.objects.get_by_natural_key('%s_%s' % (codename, self.model_name), self.app_label, self.model_name)
            )

    def setUp(self):
        super(ContentModel, self).setUp()

        get_or_create_root_user(self)

        call_command('create_trust_root')

        create_test_users(self)

        self.create_test_fixtures()

        content_model = self.content_model if hasattr(self, 'content_model') else self.model
        self.app_label = content_model._meta.app_label
        self.model_name = content_model._meta.model_name

        self.set_perms()


class ContentModelMixin(RuntimeModel, ContentModel):
    class CategoryMixin(Content):
        name = models.CharField(max_length=40, null=False, blank=False)

        class Meta:
            abstract = True
            default_permissions = ('add', 'read', 'change', 'delete')
            permissions = (
                ('add_topic_to_category', 'Add topic to a category'),
            )
            roles = (
                ('public', ('read_category', 'add_topic_to_category')),
                ('admin', ('read_category', 'add_category', 'change_category', 'add_topic_to_category')),
                ('write', ('read_category', 'change_category', 'add_topic_to_category')),
            )

    def setUp(self):
        mixin = self.CategoryMixin

        # Create a dummy model which extends the mixin
        self.model = ModelBase('Category', (mixin, models.Model),
            {'__module__': mixin.__module__})

        super(ContentModelMixin, self).setUp()

    def create_content(self, trust):
        content = self.model(trust=trust)
        content.save()

        return content

    def append_model_roles(self, rolename, perms):
        self.model._meta.roles += ((rolename, perms, ), )

    def remove_model_roles(self, rolename):
        self.model._meta.roles = [row for row in self.model._meta.roles if row[0] != rolename]

    def get_model_roles(self):
        return self.model._meta.roles


class JunctionModelMixin(RuntimeModel, ContentModel):
    class GroupJunctionMixin(Junction):
        content = models.ForeignKey(Group, unique=True, null=False, blank=False)
        name = models.CharField(max_length=40, null=False, blank=False)

        class Meta:
            abstract = True
            content_roles = (
                ('public', ('read_group', 'add_topic_to_group')),
                ('admin', ('read_group', 'add_group', 'change_group', 'add_topic_to_group')),
                ('write', ('read_group', 'change_group', 'add_topic_to_group')),
            )

    def setUp(self):
        mixin = self.GroupJunctionMixin
        self.model = ModelBase('TestGroupJunction', (mixin, models.Model),
            {'__module__': mixin.__module__})

        self.content_model = Group

        ctype = ContentType.objects.get_for_model(Group)
        Permission.objects.get_or_create(codename='read_group', content_type=ctype)
        Permission.objects.get_or_create(codename='add_topic_to_group', content_type=ctype)

        super(JunctionModelMixin, self).setUp()

    def append_model_roles(self, rolename, perms):
        self.model._meta.content_roles += ((rolename, perms, ), )

    def remove_model_roles(self, rolename):
        self.model._meta.content_roles = [row for row in self.model._meta.content_roles if row[0] != rolename]

    def get_model_roles(self):
        return self.model._meta.content_roles

    def create_content(self, trust):
        import uuid

        content = self.content_model(name=str(uuid.uuid4()))
        content.save()

        junction = self.model(content=content, trust=trust)
        junction.save()

        return content


class TrustAsContentMixin(ContentModel):
    serialized_rollback = True
    count = 0

    def setUp(self):
        self.model = Trust
        self.content_model = Trust

        super(TrustAsContentMixin, self).setUp()

    def create_content(self, trust):
        self.count += 1
        content = Trust(title='Test Trust as Content %s' % self.count, trust=trust)
        content.save()
        return content


class TrustContentTestMixin(ContentModel):
    def assertIsIterable(self, obj, msg='Not an iterable'):
        return self.assertTrue(hasattr(obj, '__iter__'))

    def test_unknown_content(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust.save()

        perm = TrustModelBackend().get_group_permissions(self.user, {})
        self.assertIsNotNone(perm)
        self.assertIsIterable(perm)
        self.assertEqual(len(perm), 0)

        trusts = Trust.objects.filter_by_content(self.user)
        self.assertEqual(trusts.count(), 0)

    def test_user_not_in_group_has_no_perm(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root(), title='trust 1')
        self.trust.save()

        self.content = self.create_content(self.trust)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)

        reload_test_users(self)

        self.perm_change.group_set.add(self.group)
        self.perm_change.save()

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

    def test_user_in_group_has_no_perm(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust.save()

        self.content = self.create_content(self.trust)

        self.test_user_not_in_group_has_no_perm()

        reload_test_users(self)

        self.user.groups.add(self.group)

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

    def test_user_in_group_has_perm(self):
        self.trust = Trust(settlor=self.user, trust=Trust.objects.get_root(), title='a title')
        self.trust.save()
        self.content = self.create_content(self.trust)

        self.trust1 = Trust(settlor=self.user1, trust=Trust.objects.get_root())
        self.trust1.save()

        self.test_user_in_group_has_no_perm()

        reload_test_users(self)

        self.trust.groups.add(self.group)

        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertTrue(had)

        had = self.user.has_perm(self.get_perm_code(self.perm_add), self.content)
        self.assertFalse(had)

    def test_has_perm(self):
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

        reload_test_users(self)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertFalse(had)

        tup = TrustUserPermission(trust=self.trust, entity=self.user, permission=self.perm_change)
        tup.save()

        reload_test_users(self)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content)
        self.assertTrue(had)

    def test_has_perm_disallow_no_perm_content(self):
        self.test_has_perm()

        self.content1 = self.create_content(self.trust1)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), self.content1)
        self.assertFalse(had)

    def test_has_perm_disallow_no_perm_perm(self):
        self.test_has_perm()

        had = self.user.has_perm(self.get_perm_code(self.perm_add), self.content)
        self.assertFalse(had)

    def test_get_or_create_default_trust(self):
        trust, created = Trust.objects.get_or_create_settlor_default(self.user)
        content = self.create_content(trust)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), content)
        self.assertFalse(had)

        tup = TrustUserPermission(trust=trust, entity=self.user, permission=self.perm_change)
        tup.save()

        reload_test_users(self)
        had = self.user.has_perm(self.get_perm_code(self.perm_change), content)
        self.assertTrue(had)

    def test_has_perm_queryset(self):
        self.test_has_perm()

        self.content1 = self.create_content(self.trust)

        reload_test_users(self)
        content_model = self.content_model if hasattr(self, 'content_model') else self.model
        qs = content_model.objects.filter(pk__in=[self.content.pk, self.content1.pk])
        had = self.user.has_perm(self.get_perm_code(self.perm_change), qs)
        self.assertTrue(had)

    def test_mixed_trust_queryset(self):
        self.test_has_perm()

        self.content1 = self.create_content(self.trust1)
        self.content2 = self.create_content(self.trust)

        reload_test_users(self)
        qs = self.model.objects.all()
        had = self.user.has_perm(self.get_perm_code(self.perm_change), qs)

        self.assertFalse(had)

    def test_read_permissions_added(self):
        ct = ContentType.objects.get_for_model(self.model)
        self.assertIsNotNone(Permission.objects.get(
            content_type=ct,
            codename='%s_%s' % ('read', ct.model)
        ))


class RoleTestMixin(object):
    def get_perm_codename(self, action):
        return '%s_%s' % (action, self.model_name.lower())

    def test_roles_in_meta(self):
        self.assertIsNotNone(self.get_model_roles())

    def test_roles_unique(self):
        self.role = Role(name='abc')
        self.role.save()
        rp = RolePermission(role=self.role, permission=self.perm_change)
        rp.save()

        rp = RolePermission(role=self.role, permission=self.perm_delete)
        rp.save()

        try:
            rp = RolePermission(role=role, permission=self.perm_change)
            rp.save()

            fail('Duplicate is not detected')
        except:
            pass

    def test_has_perm(self):
        get_or_create_root_user(self)
        reload_test_users(self)

        self.trust, created = Trust.objects.get_or_create_settlor_default(settlor=self.user)

        call_command('update_roles_permissions')

        self.content1 = self.create_content(self.trust)
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change)))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_read)))

        self.group.user_set.add(self.user)
        self.trust.groups.add(self.group)
        Role.objects.get(name='public').groups.add(self.group)

        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

    def test_has_perm_diff_roles_on_contents(self):
        self.test_has_perm()

        content2 = self.create_content(self.trust)
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), content2))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), content2))

        # diff trust, same group, same role
        trust3 = Trust(settlor=self.user, title='trust 3')
        trust3.save()
        content3 = self.create_content(trust3)

        reload_test_users(self)
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_read), content3))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), content3))
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

        trust3.groups.add(self.group)

        reload_test_users(self)
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), content3))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), content3))

        # make sure trust does not affect one another
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

        # diff trust, diff group, stronger role, not in group
        trust4 = Trust(settlor=self.user, title='trust 4')
        trust4.save()
        content4 = self.create_content(trust4)
        group4 = Group(name='admin group')
        group4.save()
        Role.objects.get(name='admin').groups.add(group4)

        reload_test_users(self)
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), content3))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), content3))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_read), content4))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), content4))

        # make sure trust does not affect one another
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

    def test_has_perm_diff_group_on_contents(self):
        self.test_has_perm()

        # same trust, diff role, in different group
        group3 = Group(name='write group')
        group3.save()
        Role.objects.get(name='write').groups.add(group3)
        self.trust.groups.add(group3)

        reload_test_users(self)
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertFalse(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

        group3.user_set.add(self.user)

        reload_test_users(self)
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

        content3 = self.create_content(self.trust)

        reload_test_users(self)

        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), content3))
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_change), content3))
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_read), self.content1))
        self.assertTrue(self.user.has_perm(self.get_perm_code(self.perm_change), self.content1))

    def test_management_command_create_roles(self):
        self.assertEqual(Role.objects.count(), 0)
        self.assertEqual(RolePermission.objects.count(), 0)

        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 3)
        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 9)

        rp = Role.objects.get(name='public')
        ra = Role.objects.get(name='admin')
        rw = Role.objects.get(name='write')

        self.assertEqual(rp.permissions.filter(content_type__app_label=self.app_label).count(), 2)
        self.assertEqual(ra.permissions.filter(content_type__app_label=self.app_label).count(), 4)

        ra.permissions.filter(content_type__app_label=self.app_label).get(codename=self.get_perm_codename('add_topic_to'))
        ra.permissions.filter(content_type__app_label=self.app_label).get(codename=self.get_perm_codename('read'))
        ra.permissions.filter(content_type__app_label=self.app_label).get(codename=self.get_perm_codename('add'))
        ra.permissions.filter(content_type__app_label=self.app_label).get(codename=self.get_perm_codename('change'))

        self.assertEqual(rp.permissions.filter(content_type__app_label=self.app_label).filter(codename=self.get_perm_codename('add_topic_to')).count(), 1)
        self.assertEqual(rp.permissions.filter(content_type__app_label=self.app_label).filter(codename=self.get_perm_codename('add')).count(), 0)
        self.assertEqual(rp.permissions.filter(content_type__app_label=self.app_label).filter(codename=self.get_perm_codename('change')).count(), 0)

        # Make change and ensure we add items
        self.append_model_roles('read', (self.get_perm_codename('read'),))
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 4)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 10)

        rr = Role.objects.get(name='read')
        self.assertEqual(rr.permissions.filter(content_type__app_label=self.app_label).count(), 1)
        self.assertEqual(rr.permissions.filter(content_type__app_label=self.app_label).filter(codename=self.get_perm_codename('read')).count(), 1)

        # Add
        self.remove_model_roles('write')
        self.append_model_roles('write', (self.get_perm_codename('change'), self.get_perm_codename('add'), self.get_perm_codename('add_topic_to'), self.get_perm_codename('read'),))
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 4)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 11)

        # Remove
        self.remove_model_roles('write')
        self.append_model_roles('write', (self.get_perm_codename('change'), self.get_perm_codename('read'), ))
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 4)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 9)

        # Remove 2
        self.remove_model_roles('write')
        self.remove_model_roles('read')
        self.append_model_roles('write', (self.get_perm_codename('change'), ))
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 3)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 7)

        # Run again
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 3)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 7)

        # Add empty
        self.append_model_roles('read', ())
        call_command('update_roles_permissions')

        rs = Role.objects.all()
        self.assertEqual(rs.count(), 4)

        rp = RolePermission.objects.filter(permission__content_type__app_label=self.app_label)
        self.assertEqual(rp.count(), 7)


class TrustJunctionTestCase(TrustContentTestMixin, JunctionModelMixin, TransactionTestCase):
    @unittest.expectedFailure
    def test_read_permissions_added(self):
        super(JunctionTestCase, self).test_read_permissions_added()


class TrustContentTestCase(TrustContentTestMixin, ContentModelMixin, TransactionTestCase):
    pass


class TrustAsContentTestCase(TrustContentTestMixin, TrustAsContentMixin, TestCase):
    pass


class RoleContentTestCase(RoleTestMixin, ContentModelMixin, TransactionTestCase):
    pass


class RoleJunctionTestCase(RoleTestMixin, JunctionModelMixin, TransactionTestCase):
    pass


class DecoratorExpressionTest(ContentModelMixin, TestCase):
    def setUp(self):
        super(DecoratorExpressionTest, self).setUp()

        self.trust1 = Trust(settlor=self.user, trust=Trust.objects.get_root())
        self.trust1.save()
        
        self.trust2 = Trust(settlor=self.user1, trust=Trust.objects.get_root())
        self.trust2.save()
        
        self.content1 = self.create_content(self.trust1)
        self.content2 = self.create_content(self.trust2)

        tup = TrustUserPermission(trust=self.trust1, entity=self.user, permission=self.perm_change)
        tup.save()

        tup = TrustUserPermission(trust=self.trust1, entity=self.user, permission=self.perm_delete)
        tup.save()
        
        tup = TrustUserPermission(trust=self.trust2, entity=self.user, permission=self.perm_change)
        tup.save()

        reload_test_users(self)

        request = HttpRequest()
        setattr(request, 'user', self.user)
        request.META['SERVER_NAME'] = 'beedesk.com'
        request.META['SERVER_PORT'] = 80
        self.request = request

    def test_P(self):
        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertTrue(mock.called)

        p = P(self.get_perm_code(self.perm_delete), fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertFalse(mock.called)

    def test_P_K(self):
        p = P(self.get_perm_code(self.perm_change), pk=K('pk'))
        has_perms = Mock(return_value=False)
        self.user.has_perms = has_perms
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)
        self.assertTrue(has_perms.called)
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.content1.pk)

        has_perms = Mock(return_value=True)
        self.user.has_perms = has_perms
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertTrue(mock.called)
        self.assertTrue(has_perms.called)
        obj = has_perms.call_args[0][1]
        self.assertEqual(obj.first().pk, self.content2.pk)

    def test_P_G(self):
        p = P(self.get_perm_code(self.perm_change), pk=G('content'))
        has_perms = Mock(return_value=True)
        self.user.has_perms = has_perms
        self.request.GET = {'content': self.content1.pk}
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request)
        self.assertTrue(mock.called)
        self.assertTrue(has_perms.called)
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.content1.pk)

    def test_P_O(self):
        p = P(self.get_perm_code(self.perm_change), pk=O('content'))
        has_perms = Mock(return_value=True)
        self.user.has_perms = has_perms
        self.request.POST = {'content': self.content1.pk}
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request)
        self.assertTrue(mock.called)
        self.assertTrue(has_perms.called)
        obj = has_perms.call_args[0][1]
        self.assertIsNotNone(obj)
        self.assertEqual(obj.count(), 1)
        self.assertEqual(obj.first().pk, self.content1.pk)

    def test_P_and(self):
        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) & \
            P(self.get_perm_code(self.perm_delete), fieldlookups_kwargs={'pk': 'pk'})

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertFalse(mock.called)

        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) & \
            P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

    def test_P_or(self):
        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) | \
            P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) | \
            P(self.get_perm_code(self.perm_delete), fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertTrue(mock.called)

        p = P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'}) | \
            P('auth.falsefalseperm_group', fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

    def test_P_complex(self):
        p = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) | \
            (P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'}) &
             P('admin.change_all'))
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertTrue(mock.called)

        p = (P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'}) |
             P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'})) & \
            P('admin.change_all')
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content2.pk)
        self.assertFalse(mock.called)

        p1 = P(self.get_perm_code(self.perm_change), fieldlookups_kwargs={'pk': 'pk'})
        p2 = P(self.get_perm_code(self.perm_delete), fieldlookups_kwargs={'pk': 'pk'})
        p3 = P('auth.falseperm_group', fieldlookups_kwargs={'pk': 'pk'})
        p4 = P('auth.falsefalseperm_group', fieldlookups_kwargs={'pk': 'pk'})
        mock = Mock(return_value='Response')
        permission_required(p1, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p2, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p3, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

        mock = Mock(return_value='Response')
        permission_required(p4, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

        p = (p1 | p3) & (p2 | p4)
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        p = (p1 & p3) | (p2 & p4)
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertFalse(mock.called)

        p = (p1 & p2) | (p3 & p4)
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)

        p = (p1 & p3) | (p2 & p4) | p1
        mock = Mock(return_value='Response')
        permission_required(p, raise_exception=False)(mock)(self.request, pk=self.content1.pk)
        self.assertTrue(mock.called)
