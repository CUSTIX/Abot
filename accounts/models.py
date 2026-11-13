from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user from the first migration, so it can grow without a painful swap later."""
