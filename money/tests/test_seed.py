import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from money import selectors
from money.models import Transaction

pytestmark = pytest.mark.django_db


def test_seed_demo_builds_a_believable_history_and_resets_only_the_demo(make_user, settings):
    other = make_user("someone")
    call_command("seed_demo")
    demo = get_user_model().objects.get(username=settings.DEMO_USERNAME)
    assert demo.check_password(settings.DEMO_PASSWORD)
    first = Transaction.objects.filter(owner=demo).count()
    assert first > 50
    assert all(b >= 0 for b in selectors.balances(demo).values()), "no wallet goes negative"

    call_command("seed_demo")  # idempotent without --reset
    assert Transaction.objects.filter(owner=demo).count() == first
    call_command("seed_demo", "--reset")
    demo = get_user_model().objects.get(username=settings.DEMO_USERNAME)  # a fresh user
    assert Transaction.objects.filter(owner=demo).count() == first  # same fake data again
    assert get_user_model().objects.filter(pk=other.pk).exists()
