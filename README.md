decorators

```python
from trusts.decorators import permission_required
from app.models import Xyz

@permission_required('xyz.can_change', fieldlookups_kwargs={'pk': 'xyz_id'})
def edit_xyz_view(request, xyz_id):
  # ...
  pass

@permission_required('xyz.can_change', fieldlookups_kwargs={'pk': 'xyz_id'})
@permission_required('project.can_read', fieldlookups_kwargs={'pk': 'project_id'})
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
