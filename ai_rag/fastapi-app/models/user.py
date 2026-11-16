from tortoise import fields
from tortoise.models import Model


class User(Model):
    """User Table. Administrators and regular users are stored here, distinguished by the role field."""

    id = fields.IntField(primary_key=True)
    # Unique=True is the only index on the table
    username = fields.CharField(max_length=100, unique=True)
    password = fields.CharField(max_length=255)
    name = fields.CharField(max_length=100)
    # Null=True indicates that these fields are allowed to be empty, not filled in at registration and then added to the personal data page
    avatar = fields.CharField(max_length=500, null=True)
    # Only effective when the field is not mentioned in code
    role = fields.CharField(max_length=30, default="USER")
    phone = fields.CharField(max_length=30, null=True)
    email = fields.CharField(max_length=100, null=True)
    status = fields.CharField(max_length=20, default="NORMAL")
    # Autoload the current time when inserted, auto-renewed every update
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        # Specifies the name of the watch that maps to the database, if not specified, Tortoise will lower it in class.
        table = "user"
