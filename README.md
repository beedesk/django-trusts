# Django Trusts

##### Django authorization add-on for multiple organizations and object-level permission settings

### Introduction
`django-trusts` is a add-on to Django's (>= 1.7) builtin<sup>[1](#footnote1)</sup> authorization. It strives to be a **minimal** implementation, adding only a single concept, `trust`, to enable maintainable per-object permission settings for a django project that hosts users of multiple organizations<sup>[2](#footnote2)</sup> with a single user namespace.

A `trust` is a relationship whereby content access is permitted by the creator [`settlor`] to specific user(s) [`trustee`(s)] or `group`(s). Content can be an instance of a `ContentMixin` subclass, or of an existing model via a junction table. Access to multiple content can be permitted by a single `trust` for maintainable permssion settings. Django's builtin model, `group`, is supported and can be used to define reusuable permissions for a `group` of `user`s.

`django-trusts` also strives to be a **scalable** solution. Permissions checking is offloaded to the database by design, and the implementation minimizes database hits. Permissions are cached per `trust` for the lifecycle of `request user`. If a project's request lifecycle resolves most checked content to one or few `trusts`, which should be very typically the case, this design should be a winner in term of performance. Permissions checking is done against an individual content or a `QuerySet`.

`django-trusts` supports Django's builtins User models `has_perms()` / `has_perms()` and does not provides any in-addition.


<sup id="footnote1">[1] See, [Django Object Permissions](https://github.com/djangoadvent/djangoadvent-articles/blob/master/1.2/06_object-permissions.rst)</sup>

<sup id="footnote2">[2] Even `django-trusts` is incepted to support multiple organizations in a single project, it does not define or restrict oraganization model design. One natural approach is to model an organization as a special user. With this arrangment, an organization can be the `settlor` of `trusts`. Alternative approach is to create another model for organization. With this arrangment, the `settlor` of `trust`s can simple be the creating user and one might or might not have all permissions of organization's content.</sup>

---

### Usages

#####  Installation
1. Put `django-trusts` in PYTHONPATH.

2. Replace `AUTHENTICATION_BACKENDS` in `settings.py`

```python
AUTHENTICATION_BACKENDS = (
    'trusts.backends.TrustModelBackend',
)
```

#####  Implementation

Alternative 1, use `ContentMixin`

```python
# app/models.py

from django.db import models
from trusts.models import ContentMixin

class Receipt(ContentMixin, models.Model):
    account = models.ForeignKey(Account, null=True)
    merchant = models.ForeignKey(Merchant, null=True)
    # ... other field

Trust.objects.register_content(Receipt)
```


Alternative 2, use `Junction`

```python
# app/models.py

from django.db import models
from django.contrib.auth.models import Group
from trusts.models import Junction

# New Junction to model that is not under your control
class GroupJunction(Junction, models.Model):
    # field name must be named as `content` and unique=True, null=False, blank=False
    content = models.ForeignKey(django.contrib.auth.models.Group, unique=True, null=False, blank=False)

Trust.objects.register_junction(Group, GroupJunction)
```

##### Permission Assignments

```python
from django.contrib.auth.models import User, Group, Permission
from trusts.models import Trust

# Helper function
def grant_user_group_permssion_to_model(user, group_name, model_name, code='change', app='app'):
    # Django's auth permission mechanism, nothing specific to `django-trust`

    # get perm by name
    perm = Permission.objects.get_by_natural_key('change_%s' % model_name, app, model_name)
    group = Group.objects.get(name=group_name)

    # connect them
    user.groups.add(group)
    perm.group_set.add(group)

    # user.has_perm('%s.change_%s' % (app, model_name)) ==> True
    # user.has_perm('%s.change_%s' % (app, model_name), obj) ==> False

# View
def create_receipt_object_for_user(request, title, details):
    trust = Trust.objects.get_or_create_settlor_default(settlor=request.user) 

    content = Receipt(trust=trust, title=title, details=details)
    content.save()

    model_name = receipt.__class__.__name__.lower()
    perm = Permission.objects.get_by_natural_key('%_%' % ('change', model_name), 'app', model_name)

    tup = TrustUserPermission(trust=trust, entity=request.user, permission=perm)
    tup.save()

    # request.user.has_perm('%s.change_%s' % ('app', model_name), content) ==> True

# View
def give_user_change_permission_on_existing_group(request, user, group_name):
    grant_user_permssion_to_model(request.user, group_name, code='change', app='auth')

    group = Group.objects.get(name=group_name)
    junction = GroupJunction(trust=trust, content=group)
    junction.save()

    # request.user.has_perm('auth.change_group', group) ==> True
```

##### Permissions Checking

```python
def check_permission_to_a_specific_receipt(request, receipt_id):
  return request.user.has_perm('app.change_receipt', Receipt.objects.get(id=receipt_id))

def check_permission_to_a_specific_group(request, group_id):
  return request.user.has_perm('app.change_group', Group.objects.get(id=group_id))
```

##### Use decorators

```python
from trusts.decorators import permission_required
from app.models import Xyz

@permission_required('app.change_xyz', fieldlookups_kwargs={'pk': 'xyz_id'})
def edit_xyz_view(request, xyz_id):
  # ...
  pass

@permission_required('app.change_xyz', fieldlookups_kwargs={'pk': 'xyz_id'})
@permission_required('app.read_project', fieldlookups_kwargs={'pk': 'project_id'})
def move_xyz_to_project_view(request, xyz_id, project_id):
  # ...
  pass

```

##### Customization

The folllowing settings (django.conf) allow for customization and adaptation.


###### Initial options

    Warning: Changing the options below affects the construction of foreign keys and many-to-many
    relationships. If you intend to set these options, you should set it before creating any
    migrations or running `manage.py migrate` for the first time, and should not be changed afterward.

    Changing this setting after you have tables created is not supported by `makemigrations` and
    will result in you having to manually fix your schema, port your data from the old user table,
    and possibly manually reapply some migrations.

* TRUSTS_ENTITY_MODEL -- The model name for `settlors` and `trustees` field. Must be specified in contenttypes format, ie, 'app_label.model_name'. (default: `settings.AUTH_USER_MODEL`.)
* TRUSTS_GROUP_MODEL -- The model name for `groups` field. (default: `auth.Group`)
* TRUSTS_PERMISSION_MODEL -- The model name for `Permission`. (default: `auth.Permission`)
* TRUSTS_CREATE_ROOT -- A boolean set to True indicates root Trust model object to be created during the initial migration. (default: True)
* TRUSTS_ROOT_PK -- The `pk` of the root trust model object. (default: 1)
* TRUSTS_ROOT_SETTLOR -- The `pk` of settlor of the root trust object. (default: None)
* TRUSTS_DEFAULT_SETTLOR -- The default value for `settlor` field on Trust model. (default: None)
* TRUSTS_ROOT_TITLE -- The title of root rust object. (default: "In Trust We Trust")
