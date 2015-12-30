# Django Trusts

##### Django authorization add-on for multiple organizations and per object permission settings

### Introduction 
`django-trusts` strives to be a **minimal** add-on to Django's (>= 1.7) builtin<sup>[1](#footnote1)</sup> authorization implementation. It adds a single concept, `trust`, to enable maintainable per-object permission settings for a django project that hosts users of multiple organizations<sup>[2](#footnote2)</sup> with a single user namespace.

A `trust` is a relationship whereby content access is permitted by the creator [settlor] to specific user(s) [trustee(s)] or group(s). Content can be an instance of a ContentMixin subclass, or of an existing model via a junction table. Access to multiple content can be permitted by a single `trust` for maintainable permssion settings. Django's builtin model, group, is supported and can be used to define reusuable permissions for a group of users.

`django-trusts` also strives to be a **scalable** solution. Permissions checking is offloaded to the database by design, and the implementation minimizes database hits. Permissions are cached per trust for the lifecycle of request user. If a project's request lifecycle resolves most checked content to one or few `trusts`, which should be very typically the case, this design should be a winner in term of performance. Currently, permissions checking is done against an individual content. In the future, we would like to add permissions checking against a QuerySet of content.

`django-trusts` supports Django's builtins User models `has_perms()` / `has_perms()` and does not provides any in-addition.

---

### Usages

#####  Installation
Run this command from the command prompt:

```bash
>>> python setup.py install
```

or put it in PYTHONPATH.

Replace `AUTHENTICATION_BACKENDS` in `settings.py`

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
```


Alternative 2, use `Junction`

```python
# app/models.py 

from django.db import models
from django.contrib.auth.models import Group
from trusts.models import Junction

# Your Object
class Receipt(models.Model):
    account = models.ForeignKey(Account, null=True)
    merchant = models.ForeignKey(Merchant, null=True)
    # ... other field

# New Junction to existing model
class ReceiptContent(Junction, models.Model):
    content = models.ForeignKey(Receipt, null=False, blank=False)
    
# New Junction to model that is not under your control
class GroupContent(Junction, models.Model):
    content = models.ForeignKey(django.contrib.auth.models.Group, null=False, blank=False)
```

#### Permission Assigments

```python
from django.contrib.auth.models import User, Group, Permission
from trusts.models import Trust

def add_user_to_a_new_trust(request, name):
  perm_change = Permission.objects.get_by_natural_key('change_xyz', 'app', 'xyz')

  trust = Trust(settlor=request.user, name=trust_name)
  trust.save()
  trust.trustees.add(

  tup = TrustUserPermission(user=request.user, permission=perm_change)
  tup.save()
  
def add_group_to_a_new_trust(request, trust_name, group_name):
  # get perm by name
  perm_change = Permission.objects.get_by_natural_key('change_xyz', 'app', 'xyz')

  # get group
  group = Group.objects.get(name=group_name)
  
  # new trust
  trust = Trust(settlor=request.user, name=trust_name)
  trust.save()
  
  # connect them all
  request.user.groups.add(group)
  trust.groups.add(group)
  perm_change.group_set.add(group)

```


#### Use decorators (not implemented)

```python
from trusts.decorators import permission_required
from app import Xyz

def get_xyz(request, user_id, xyz_id):
  return Xyz.objects.get(xyz_id)

@permission_required('can_edit_xyz', obj_func=get_xyz)
def edit_xyz_view(request, user_id, xyz_id):
  # ...
  pass

@permission_required('can_read_xyz', model_obj=(Xyz, 'xyz_id'))
def delete_xyz_view(request, user_id, xyz_id):
  # ...
  pass
```

---

<sup id="footnote1">[1] See, [Django Object Permissions](https://github.com/djangoadvent/djangoadvent-articles/blob/master/1.2/06_object-permissions.rst)</sup>

<sup id="footnote2">[2] Even `django-trusts` is incepted to support multiple organizations in a single project, it does not define or restrict oraganization model design. One natural approach is to model an organization as a special user. With this arrangment, an organization can be the settlor of trusts. Alternative approach is to create another model for organization. With this arrangment, the settler of trusts can simple be the creating user and one might or might not have all permissions of organization's content.</sup>
