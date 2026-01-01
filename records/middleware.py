from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from datetime import timedelta

class SessionTimeoutMiddleware:
    """
    Logs out user after 5 minutes of inactivity.
    Resets timer on every request (activity).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply to authenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Get last activity time from session
        last_activity = request.session.get('last_activity')

        # If first visit or no last_activity, set now
        if last_activity is None:
            request.session['last_activity'] = timezone.now().isoformat()
            return self.get_response(request)

        # Convert back to datetime
        last_activity = timezone.datetime.fromisoformat(last_activity)

        # Check if idle for more than 5 minutes
        idle_time = timezone.now() - last_activity
        if idle_time > timedelta(minutes=5):
            # Log out the user
            messages.warning(request, "You have been logged out due to 5 minutes of inactivity.")
            # Clear session
            request.session.flush()
            # Redirect to login
            login_url = reverse('login') + '?next=' + request.path
            return redirect(login_url)

        # Update last activity time on every request
        request.session['last_activity'] = timezone.now().isoformat()

        # Continue with normal request
        response = self.get_response(request)
        return response