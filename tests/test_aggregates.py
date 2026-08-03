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
    for order_idx, price in enumerate((1, 3, 5), 1):
        models.Topping.objects.create(
            sandwich=sandwich, price=price, order=order_idx
        )
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


def test_reserved_keyword_column(sandwich):
    """Verify that SQL keywords in column names don't crash.

    The 'order' column is a SQL reserved keyword; without F() aliasing,
    this would crash with OperationalError at query time.
    """
    annotated = models.Sandwich.objects.annotate(
        order_sum=aggregates.SubquerySum(_toppings_for_outer(), 'order'),
    ).get(pk=sandwich.pk)
    assert annotated.order_sum == 6


def test_sliced_top_n_max(sandwich):
    """Max of top 2 cheapest toppings (prices 1, 3) is 3."""
    annotated = models.Sandwich.objects.annotate(
        top_two_max=aggregates.SubqueryMax(
            _toppings_for_outer().order_by('price')[:2], 'price'
        ),
    ).get(pk=sandwich.pk)
    assert annotated.top_two_max == 3


def test_sliced_count(sandwich):
    """Count of top 2 most expensive toppings is 2."""
    annotated = models.Sandwich.objects.annotate(
        top_two_count=aggregates.SubqueryCount(
            _toppings_for_outer().order_by('-price')[:2]
        ),
    ).get(pk=sandwich.pk)
    assert annotated.top_two_count == 2


def test_relation_name_count_matches_queryset_form(sandwich):
    by_name = models.Sandwich.objects.annotate(
        reviews=aggregates.SubqueryCount('review'),
        toppings=aggregates.SubqueryCount('topping'),
    ).get(pk=sandwich.pk)
    assert by_name.reviews == 2
    assert by_name.toppings == 3


def test_relation_name_column_aggregates(sandwich):
    annotated = models.Sandwich.objects.annotate(
        total=aggregates.SubquerySum('topping', 'price'),
        avg_rating=aggregates.SubqueryAvg('review', 'rating'),
    ).get(pk=sandwich.pk)
    assert annotated.total == 9
    assert annotated.avg_rating == pytest.approx(3.0)


def test_relation_name_forward_m2m(sandwich):
    for name in ('spicy', 'vegan'):
        sandwich.tags.create(name=name)
    annotated = models.Sandwich.objects.annotate(
        tag_count=aggregates.SubqueryCount('tags'),
    ).get(pk=sandwich.pk)
    assert annotated.tag_count == 2


def test_relation_name_reverse_m2m(sandwich):
    tag = models.Tag.objects.create(name='classic')
    tag.sandwiches.add(sandwich)
    annotated = models.Tag.objects.annotate(
        sandwich_count=aggregates.SubqueryCount('sandwiches'),
    ).get(pk=tag.pk)
    assert annotated.sandwich_count == 1


def test_relation_name_unknown_raises(sandwich):
    with pytest.raises(ValueError, match='unknown relation'):
        list(
            models.Sandwich.objects.annotate(
                n=aggregates.SubqueryCount('nonexistent'),
            )
        )


def test_relation_name_non_relation_raises(sandwich):
    with pytest.raises(ValueError, match='not a reverse or many-to-many'):
        list(
            models.Sandwich.objects.annotate(
                n=aggregates.SubqueryCount('data'),
            )
        )


def test_relation_name_respects_avg_default_output_field(sandwich):
    annotated = models.Sandwich.objects.annotate(
        avg_rating=aggregates.SubqueryAvg('review', 'rating'),
    ).get(pk=sandwich.pk)
    assert isinstance(annotated.avg_rating, float)
