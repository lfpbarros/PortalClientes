"""Helpers for permission and role checks used across the customers app."""

from django.conf import settings

# Default names for internal groups in the portal. These can be overridden via
# the PORTAL_INTERNAL_GROUPS setting if needed.
DEFAULT_INTERNAL_GROUPS = {
    "Equipe",
    "Compliance",
    "Financeiro",
    "Trading",
    "Suprimentos",
}
DEFAULT_CLIENT_GROUPS = {
    "Clientes",
}

INTERNAL_GROUP_NAMES = {name.lower() for name in getattr(settings, "PORTAL_INTERNAL_GROUPS", DEFAULT_INTERNAL_GROUPS)}
CLIENT_GROUP_NAMES = {name.lower() for name in getattr(settings, "PORTAL_CLIENT_GROUPS", DEFAULT_CLIENT_GROUPS)}


def is_internal_user(user) -> bool:
    """Return True when the given user should be treated as an internal member."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True

    group_names = {name.lower() for name in user.groups.values_list("name", flat=True)}
    if not group_names:
        return False

    if group_names & INTERNAL_GROUP_NAMES:
        return True

    # Consider the user external when they belong only to explicit client groups.
    if group_names <= CLIENT_GROUP_NAMES:
        return False

    # If the user has any other group, treat as internal by default so we don't
    # accidentally expose restricted areas to clients.
    return True
