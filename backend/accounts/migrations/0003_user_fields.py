"""
USER v2 (docs/api-decisions.md D1.1, D1.7, D2.1, D2.3, D2.5, db/diagram/v2.md):
- thumbnail -> avatar (rename only, files stay where they are)
- new: nickname (public), bio, recovery_code_hash
- username max 32; username and nickname unique ignoring letter case
- UserManager: signing in ignores the case of the username

Existing users get nickname = their username (made URL-safe and unique; reserved or too short
names become `user_<id>`), because the column must be filled before it can be NOT NULL + UNIQUE.
They can change it in their profile. Usernames are never changed: if two differ only in letter
case (or one is longer than 32), the migration stops before changing anything and names them.
"""

import re

import accounts.models
import accounts.validators
import django.contrib.auth.validators
import django.db.models.functions.text
from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Length, Lower

NICKNAME_MAX_LENGTH = 32
# A frozen copy of accounts.validators.RESERVED_NICKNAMES (2026-11-12). Migrations must not import
# values that change later: this migration has to behave the same whenever it runs.
RESERVED_NICKNAMES = frozenset({
    'me', 'admin', 'administrator', 'root', 'system', 'staff', 'support',
    'moderator', 'mod', 'help', 'api', 'null', 'undefined', 'onbeat', 'dancingbuddy',
})


def check_usernames_fit(apps, schema_editor):
    """Fail with a readable message instead of a raw IntegrityError / DataError below.

    Usernames are sign-in names, so the migration can't rename them on its own: fix such
    users in the admin or the shell first, then run the migration again.
    """
    User = apps.get_model('accounts', 'User')
    clashes = (User.objects.annotate(ci=Lower('username')).values('ci')
               .annotate(n=Count('id')).filter(n__gt=1).values_list('ci', flat=True))
    too_long = (User.objects.annotate(length=Length('username')).filter(length__gt=32)
                .values_list('username', flat=True))
    problems = []
    if clashes:
        problems.append(f'usernames that differ only in letter case: {sorted(clashes)}')
    if too_long:
        problems.append(f'usernames longer than 32 characters: {sorted(too_long)}')
    if problems:
        raise RuntimeError('Cannot apply accounts.0003_user_fields, rename these users first: ' + '; '.join(problems))


def fill_nicknames(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    taken = set()
    for user in User.objects.order_by('pk'):
        base = re.sub(r'[^A-Za-z0-9_.-]', '_', user.username)[:NICKNAME_MAX_LENGTH] or 'user'
        if len(base) < 3 or base.lower() in RESERVED_NICKNAMES:
            base = f'user_{user.pk}'
        nickname = base
        if nickname.lower() in taken:   # e.g. `Ana` and `ana`, or two names that became the same after `_`
            suffix = f'_{user.pk}'
            nickname = base[:NICKNAME_MAX_LENGTH - len(suffix)] + suffix
        taken.add(nickname.lower())
        user.nickname = nickname
        user.save(update_fields=['nickname'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_thumbnail'),
    ]

    operations = [
        migrations.RunPython(check_usernames_fit, migrations.RunPython.noop),
        migrations.RenameField(
            model_name='user',
            old_name='thumbnail',
            new_name='avatar',
        ),
        migrations.AlterField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to=accounts.models.user_avatar_upload_path),
        ),
        migrations.AddField(
            model_name='user',
            name='bio',
            field=models.CharField(blank=True, default='', max_length=300),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='user',
            name='recovery_code_hash',
            field=models.CharField(blank=True, default='', max_length=128),
            preserve_default=False,
        ),
        # nickname in three steps: add as nullable, fill, then NOT NULL + UNIQUE (below).
        migrations.AddField(
            model_name='user',
            name='nickname',
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.RunPython(fill_nicknames, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='nickname',
            field=models.CharField(
                error_messages={'unique': 'A user with that nickname already exists.'},
                help_text='Public name shown everywhere. 3-32 characters: letters, digits and ./-/_.',
                max_length=32,
                unique=True,
                validators=[
                    accounts.validators.nickname_characters,
                    accounts.validators.nickname_min_length,
                    accounts.validators.validate_nickname_not_reserved,
                ],
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(
                error_messages={'unique': 'A user with that username already exists.'},
                help_text='Private, used only to sign in. 6-32 characters: letters, digits and @/./+/-/_.',
                max_length=32,
                unique=True,
                validators=[
                    django.contrib.auth.validators.UnicodeUsernameValidator(),
                    accounts.validators.username_min_length,
                ],
            ),
        ),
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', accounts.models.UserManager()),
            ],
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower('username'), name='user_username_ci_unique',
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower('nickname'), name='user_nickname_ci_unique',
            ),
        ),
    ]
