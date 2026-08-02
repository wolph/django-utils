import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from django.db import models
from django.db.models import base
from django.template import defaultfilters
from python_utils import formatters


class ModelBaseMeta(base.ModelBase):
    """
    Model base with more readable naming convention

    Example:
    Assuming the model is called `app.FooBarObject`

    Default Django table name: `app_foobarobject`
    Table name with this base: `app_foo_bar_object`
    """

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        module = attrs['__module__']

        # `meta` is either a user-defined ``Meta`` class or a ``type``
        # synthesized below, so its attribute surface is only known at
        # runtime; ``Any`` keeps the dynamic ``db_table`` assignment valid
        # across every checker (django-stubs' plugin is mypy-only).
        meta: Any
        # Get or create Meta
        if 'Meta' in attrs:
            meta = attrs['Meta']
        else:
            meta = type(
                'Meta',
                (object,),
                dict(
                    __module__=module,
                ),
            )
            attrs['Meta'] = meta

        # Override table name only if not explicitly defined
        if not hasattr(meta, 'db_table'):  # pragma: no cover
            module_name = formatters.camel_to_underscore(name)
            app_label = module.split('.')[-2]
            meta.db_table = f'{app_label}_{module_name}'

        return base.ModelBase.__new__(cls, name, bases, attrs, **kwargs)


class ModelBase(models.Model, metaclass=ModelBaseMeta):
    class Meta:
        abstract = True


class CreatedAtModelBase(ModelBase):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Django's metaclass merges nested ``Meta`` classes from every base at
    # runtime, so redeclaring ``Meta`` here is not really an override;
    # django-stubs' mypy plugin models this, basedpyright cannot.
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True


class NameMixin:
    """Mixin to automatically get a unicode and repr string base on the name

    >>> x = NameMixin()
    >>> x.pk = 123
    >>> x.name = 'test'
    >>> repr(x)
    '<NameMixin[123]: test>'
    >>> str(x)
    'test'
    >>> str(str(x))
    'test'

    """

    if TYPE_CHECKING:
        pk: Any
        name: Any

    def __unicode__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.__unicode__()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.pk or -1:d}]: {self.name}>'


class SlugMixin(NameMixin):
    """Mixin to automatically slugify the name and add both a name and slug to
    the model

    >>> x = NameMixin()
    >>> x.pk = 123
    >>> x.name = 'test'
    >>> repr(x)
    '<NameMixin[123]: test>'
    >>> str(x)
    'test'
    >>> str(str(x))
    'test'

    """

    if TYPE_CHECKING:
        slug: Any
        # Provided by the concrete Model subclass this mixin is combined
        # with at runtime; not visible from SlugMixin's own bases.
        _default_manager: ClassVar[Any]

    slugify_max_attempts: ClassVar[int] = 1000

    def get_unique_slug(self, base: str) -> str:
        """Return ``base``, suffixed with a counter if already taken.

        Note: the uniqueness check and the eventual insert are not
        atomic, so two concurrent saves can still race each other onto
        the same slug. Callers with high write concurrency on the same
        name should still enforce a unique constraint (as ``SlugMixin``
        does) and handle the resulting ``IntegrityError``.
        """
        model = type(self)
        slug = base
        for attempt in itertools.count(2):
            taken = model._default_manager.filter(slug=slug)
            if self.pk is not None:
                taken = taken.exclude(pk=self.pk)

            if not taken.exists():
                return slug

            if attempt > self.slugify_max_attempts:
                raise ValueError(
                    f'Could not find a free slug for {base!r} after '
                    f'{self.slugify_max_attempts} attempts'
                )

            slug = f'{base}-{attempt}'

        raise AssertionError('unreachable')  # pragma: no cover

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug and self.name:
            self.slug = self.get_unique_slug(defaultfilters.slugify(self.name))

        # `save` isn't defined on NameMixin/object; it's provided by the
        # concrete Model subclass this mixin is combined with at runtime
        # (e.g. SlugModelBase). mypy can't see that cooperative-mixin MRO
        # when checking SlugMixin in isolation.
        super().save(  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
            *args, **kwargs
        )

    class Meta:
        unique_together = ('slug',)


class NameModelBase(NameMixin, ModelBase):
    name = models.CharField(max_length=100)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True


class SlugModelBase(SlugMixin, NameModelBase):
    slug = models.SlugField(max_length=50)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True


class NameCreatedAtModelBase(NameModelBase, CreatedAtModelBase):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True


class SlugCreatedAtModelBase(SlugModelBase, CreatedAtModelBase):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True
