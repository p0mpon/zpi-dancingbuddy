from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model.

    Empty for now, but having our own class from day one lets us add fields
    later with a normal migration (swapping AUTH_USER_MODEL mid-project is painful).
    """
