import functools
from typing import Any, ClassVar


class RecursiveField:
    PREFIX: ClassVar[str] = 'get_'

    def __init__(
        self,
        field_name: str | None = None,
        parent_field: str = 'parent',
        default: Any = None,
    ) -> None:
        self.field_name = field_name
        self.parent_field = parent_field
        self.default = default

    def contribute_to_class(self, cls: type, name: str) -> None:
        if not self.field_name:
            assert name.startswith(self.PREFIX)
            self.field_name = name.replace(self.PREFIX, '', 1)

        setattr(cls, name, self)

    def get(self, instance: Any) -> Any:
        name = self.field_name
        assert name

        value = None
        while instance is not None and value is None:
            value = getattr(instance, name, None)
            instance = getattr(instance, self.parent_field, None)

        if value is None:
            value = self.default

        return value

    def __get__(
        self, instance: Any, owner: type | None = None
    ) -> functools.partial[Any]:
        return functools.partial(self.get, instance)
