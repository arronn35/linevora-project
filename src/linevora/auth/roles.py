"""Role model (the User.roles counterpart in the data model)."""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SPECIALIST = "specialist"
    VIEWER = "viewer"
