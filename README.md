# Django Trusts

##### Django authorization add-on for multiple organizations and object-level permission settings

### Introduction
`django-trusts` is a add-on to Django's (>= 1.7) builtin<sup>[1](#footnote1)</sup> authorization. It strives to be a **minimal** implementation, adding only a single concept, `trust`, to enable maintainable per-object permission settings for a django project that hosts users of multiple organizations<sup>[2](#footnote2)</sup> with a single user namespace.

A `trust` is a relationship whereby content access is permitted by the creator [`settlor`] to specific user(s) [`trustee`(s)] or `group`(s). Content can be an instance of a `Content` subclass, or of an existing model via a junction table. Access to multiple content can be permitted by a single `trust` for maintainable permssion settings. Django's builtin model, `group`, is supported and can be used to define reusuable permissions for a `group` of `user`s.

`django-trusts` also strives to be a **scalable** solution. Permissions checking is offloaded to the database by design, and the implementation minimizes database hits. Permissions are cached per `trust` for the lifecycle of `request user`. If a project's request lifecycle resolves most checked content to one or few `trusts`, which should be very typically the case, this design should be a winner in term of performance. Permissions checking is done against an individual content or a `QuerySet`.

`django-trusts` supports Django's builtins User models `has_perms()` / `has_perms()` and does not provides any in-addition.


<sup id="footnote1">[1] See, [Django Object Permissions](https://github.com/djangoadvent/djangoadvent-articles/blob/master/1.2/06_object-permissions.rst)</sup>

<sup id="footnote2">[2] Even `django-trusts` is incepted to support multiple organizations in a single project, it does not define or restrict oraganization model design. One natural approach is to model an organization as a special user. With this arrangment, an organization can be the `settlor` of `trusts`. Alternative approach is to create another model for organization. With this arrangment, the `settlor` of `trust`s can simple be the creating user and one might or might not have all permissions of organization's content.</sup>

---


Read more: http://django-trusts.readthedocs.org/en/latest/
