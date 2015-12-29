# Django Trusts

## Authorization add-on for multiple organizations and per object permission settings

`django-trusts` strives to be a *minimal* add-on to Django's (>= 1.7) builtin authorization implementation. It adds a single concept, `trust`, to enable maintainable per-object permission settings for a django project that hosts users of multiple organizations* with a single user namespace.

A `trust` is a relationship whereby content access is permitted by the creator [settlor] to specific user(s) [trustee(s)] or group(s). Content can be an instance of a ContentMixin subclass, or of an existing model via a junction table. Access to multiple content can be permitted by a single `trust` for maintainable permssion settings. Django's builtin model, group, is supported and can be used to define reusuable permissions for a group of users.

`django-trusts` also strives to be a *scalable* solution. Permissions checking is offloaded to the database by design, and the implementation minimizes database hits. Currently, permissions checking is done against an individual object. Permissions are cached per trust for the lifecycle of request user. If a project's request lifecycle resolves most checked content to one or few `trusts`, which should be very typically the case, this design should be a winner in term of performance. In the future, we would like to add permissions checking against a QuerySet of content.

`django-trusts` supports Django's builtins decorators: `permission_required` and User models `has_perms()` / `has_perms()` and does not provides any in-addition.

> * Even `django-trusts` is incepted to support multiple organizations in a single project, it does not define or restrict oraganization model design. One natural approach is to model an organization as a special user. With this arrangment, an organization can be the settlor of trusts. Alternative approach is to create another model for organization. With this arrangment, the settler of trusts can simple be the creating user and one might or might not have all permissions of organization's content.
