from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from money import services as money_services


@transaction.atomic
def sign_up(*, username: str, password: str, first_name: str = ""):
    """Create an account with starter wallets and categories, ready to use."""
    User = get_user_model()
    user = User(username=username, first_name=first_name)
    validate_password(password, user)
    user.set_password(password)
    user.save()
    money_services.create_starter_set(user)
    return user
