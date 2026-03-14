from django.shortcuts import redirect
from django.urls import reverse


class RoleMiddleware:
    """
    Simple role-based access middleware
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If user is not authenticated, continue
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Example: block inactive users
        if hasattr(request.user, "is_active") and not request.user.is_active:
            return redirect(reverse("login"))

        return self.get_response(request)
