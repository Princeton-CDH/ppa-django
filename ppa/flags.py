from django.core.exceptions import ImproperlyConfigured

try:
    from waffle import switch_is_active, flag_is_active
except Exception as e:
    raise ImproperlyConfigured(
        "django-waffle must be installed and configured to use feature flags"
    ) from e


def is_flag_enabled(setting_name, request=None):
    """
    Waffle-only flag lookup.

    - Interprets the flag name as the lowercase of the setting_name
      (e.g., "ENABLE_HATHI" -> "enable_hathi").
    - Checks waffle Switch first (global toggle).
    - If a request is provided, checks per-request Flag targeting.
    - Raises ImproperlyConfigured if waffle is not properly available.
    """
    waffle_flag_name = setting_name.lower()

    # global switch check
    try:
        if switch_is_active(waffle_flag_name):
            return True
    except Exception as e:
        raise ImproperlyConfigured(
            f"Waffle switch lookup failed for '{waffle_flag_name}': {e}"
        ) from e

    # per-request flag check
    if request is not None:
        try:
            if flag_is_active(request, waffle_flag_name):
                return True
        except Exception as e:
            raise ImproperlyConfigured(
                f"Waffle flag lookup failed for '{waffle_flag_name}' (request): {e}"
            ) from e

    return False
