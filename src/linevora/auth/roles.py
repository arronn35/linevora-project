"""Rol modeli (veri modelindeki Kullanıcı.roll karşılığı)."""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SPECIALIST = "specialist"
    VIEWER = "viewer"
