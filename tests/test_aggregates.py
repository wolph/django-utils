"""Tests for django_utils.aggregates.

The double-count test asserts the WRONG value from plain ``Count`` on
purpose: it documents the JOIN fan-out footgun these helpers exist to
avoid, and fails loudly if a future Django version fixes it (at which
point the README pitch needs rewording).
"""

import pytest
from django.db import models as dj_models
from django.db.models import Count, OuterRef
from django_utils import aggregates

from tests.test_app import models

pytestmark = pytest.mark.django_db


@pytest.fixture
def sandwich():
    sandwich = models.Sandwich.objects.create(data={'name': 'blt'})
    for rating in (2, 4):
        models.Review.objects.create(sandwich=sandwich, rating=rating)
    for price in (1, 3, 5):
        models.Topping.objects.create(sandwich=sandwich, price=price)
    return sandwich


def _reviews_for_outer():
    return models.Review.objects.filter(sandwich=OuterRef('pk'))


def _toppings_for_outer():
    return models.Topping.objects.filter(sandwich=OuterRef('pk'))


def test_plain_count_double_counts(sandwich):
    """The footgun: two JOINed relations multiply (2 reviews x 3
    toppings = 6 rows), so both counts read 6."""
    annotated = models.Sandwich.objects.annotate(
        reviews=Count('review'), toppings=Count('topping')
    ).get(pk=sandwich.pk)
    assert annotated.reviews == 6
    assert annotated.toppings == 6


def test_subquery_count_is_immune(sandwich):
    annotated = models.Sandwich.objects.annotate(
        reviews=aggregates.SubqueryCount(_reviews_for_outer()),
        toppings=aggregates.SubqueryCount(_toppings_for_outer()),
    ).get(pk=sandwich.pk)
    assert annotated.reviews == 2
    assert annotated.toppings == 3


def test_subquery_count_respects_inner_filter(sandwich):
    annotated = models.Sandwich.objects.annotate(
        good=aggregates.SubqueryCount(
            _reviews_for_outer().filter(rating__gte=4)
        ),
    ).get(pk=sandwich.pk)
    assert annotated.good == 1


def test_subquery_count_empty_is_zero():
    empty = models.Sandwich.objects.create(data={})
    annotated = models.Sandwich.objects.annotate(
        reviews=aggregates.SubqueryCount(_reviews_for_outer()),
    ).get(pk=empty.pk)
    assert annotated.reviews == 0


def test_subquery_sum(sandwich):
    annotated = models.Sandwich.objects.annotate(
        total=aggregates.SubquerySum(_toppings_for_outer(), 'price'),
    ).get(pk=sandwich.pk)
    assert annotated.total == 9


def test_subquery_sum_empty_is_none():
    empty = models.Sandwich.objects.create(data={})
    annotated = models.Sandwich.objects.annotate(
        total=aggregates.SubquerySum(_toppings_for_outer(), 'price'),
    ).get(pk=empty.pk)
    assert annotated.total is None


def test_subquery_min_max(sandwich):
    annotated = models.Sandwich.objects.annotate(
        cheapest=aggregates.SubqueryMin(_toppings_for_outer(), 'price'),
        dearest=aggregates.SubqueryMax(_toppings_for_outer(), 'price'),
    ).get(pk=sandwich.pk)
    assert annotated.cheapest == 1
    assert annotated.dearest == 5


def test_subquery_avg_defaults_to_float(sandwich):
    annotated = models.Sandwich.objects.annotate(
        avg_rating=aggregates.SubqueryAvg(_reviews_for_outer(), 'rating'),
    ).get(pk=sandwich.pk)
    assert annotated.avg_rating == pytest.approx(3.0)
    assert isinstance(annotated.avg_rating, float)


def test_annotation_filter_and_order(sandwich):
    models.Sandwich.objects.create(data={})  # zero reviews
    ordered = list(
        models.Sandwich.objects.annotate(
            reviews=aggregates.SubqueryCount(_reviews_for_outer()),
        )
        .filter(reviews__gte=1)
        .order_by('-reviews')
        .values_list('reviews', flat=True)
    )
    assert ordered == [2]


def test_rejects_non_identifier_column():
    with pytest.raises(ValueError):
        aggregates.SubquerySum(models.Topping.objects.all(), 'price; DROP')


def test_explicit_output_field(sandwich):
    annotated = models.Sandwich.objects.annotate(
        total=aggregates.SubquerySum(
            _toppings_for_outer(),
            'price',
            output_field=dj_models.FloatField(),
        ),
    ).get(pk=sandwich.pk)
    assert annotated.total == pytest.approx(9.0)


def test_subquery_count_with_explicit_output_field(sandwich):
    annotated = models.Sandwich.objects.annotate(
        reviews=aggregates.SubqueryCount(
            _reviews_for_outer(), output_field=dj_models.BigIntegerField()
        ),
    ).get(pk=sandwich.pk)
    assert annotated.reviews == 2


def test_subquery_avg_with_explicit_output_field(sandwich):
    annotated = models.Sandwich.objects.annotate(
        avg_rating=aggregates.SubqueryAvg(
            _reviews_for_outer(),
            'rating',
            output_field=dj_models.DecimalField(
                max_digits=10, decimal_places=2
            ),
        ),
    ).get(pk=sandwich.pk)
    assert float(annotated.avg_rating) == pytest.approx(3.0)
