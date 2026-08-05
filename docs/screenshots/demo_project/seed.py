"""Photogenic seed data for the screenshot demo project.

Called once per `capture.py` run against a fresh, throwaway sqlite
database (see `settings.DATABASES`), so it doesn't need to guard
against re-running against pre-existing rows.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from tests.test_app import models

SUPERUSER_USERNAME = 'admin'
# Throwaway: lives only in a tempdir sqlite file that's deleted at the
# end of every `capture.py` run.
SUPERUSER_PASSWORD = 'screenshot-admin-password'  # noqa: S105

# (JSON `data` payload for a Sandwich) -- five distinct `filling`
# values so `JSONFieldFilterDropdown`'s sidebar filter renders as a
# real `<select>` (`dropdown_filter.html` only swaps the link list for
# one once there are more than three choices).
SANDWICHES: tuple[dict[str, object], ...] = (
    {
        'filling': 'turkey',
        'price': 650,
        'toasted': True,
        'notes': 'double bacon, extra mayo',
    },
    {'filling': 'bacon', 'price': 550, 'toasted': True},
    {'filling': 'avocado', 'price': 600, 'toasted': False},
    {'filling': 'corned beef', 'price': 700, 'toasted': True},
    {'filling': 'cheddar', 'price': 450, 'toasted': True},
)

# (sandwich index into SANDWICHES, rating, comment) -- uneven counts
# per sandwich so `count-columns.png` has something worth sorting.
REVIEWS: tuple[tuple[int, int, str], ...] = (
    (0, 5, 'Best club sandwich in town.'),
    (0, 4, 'Great but pricey.'),
    (0, 3, 'Would order again, but ask for less mayo.'),
    (1, 4, 'Solid classic BLT.'),
    (3, 5, 'Perfect reuben.'),
    (3, 4, 'Corned beef was a little salty.'),
)

# (sandwich index, price, order)
TOPPINGS: tuple[tuple[int, int, int], ...] = (
    (0, 150, 0),
    (0, 100, 1),
    (1, 50, 0),
    (1, 75, 1),
    (1, 25, 2),
    (2, 80, 0),
)

INGREDIENTS: tuple[tuple[str, int], ...] = (
    ('salt', 42),
    ('pepper', 17),
    ('mayonnaise', 8),
    ('rye bread', 23),
)

TAG_NAME = 'lunch favorites'


def seed() -> dict[str, int]:
    """Populate the database and return the primary keys `capture.py`
    needs to build exact change-view URLs (rather than assuming
    autoincrement starts at a particular value)."""
    sandwiches = [
        models.Sandwich.objects.create(data=dict(data)) for data in SANDWICHES
    ]

    for sandwich_index, rating, comment in REVIEWS:
        models.Review.objects.create(
            sandwich=sandwiches[sandwich_index],
            rating=rating,
            comment=comment,
        )

    for sandwich_index, price, order in TOPPINGS:
        models.Topping.objects.create(
            sandwich=sandwiches[sandwich_index], price=price, order=order
        )

    for name, stock in INGREDIENTS:
        models.Ingredient.objects.create(name=name, stock=stock)

    tag = models.Tag.objects.create(name=TAG_NAME)
    tag.sandwiches.set(sandwiches[:3])

    user_model = get_user_model()
    superuser: AbstractUser = user_model.objects.create_superuser(  # type: ignore[attr-defined]
        username=SUPERUSER_USERNAME,
        email='admin@example.com',
        password=SUPERUSER_PASSWORD,
    )

    return {
        'sandwich_id': sandwiches[0].pk,
        'tag_id': tag.pk,
        'superuser_id': superuser.pk,
    }
