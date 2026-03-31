from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import FormView

from .forms import LoginForm, RegisterForm


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome, {user.username}! Your account has been created.")
        return redirect("dashboard:index")

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        messages.success(self.request, f"Welcome back, {user.username}!")
        next_url = self.request.GET.get("next", "dashboard:index")
        return redirect(next_url)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "You have been signed out.")
        return redirect("accounts:login")


@login_required
def settings_view(request):
    """User settings page."""
    if request.method == "POST":
        wallet = request.POST.get("wallet_address", "").strip()
        request.user.wallet_address = wallet
        request.user.save(update_fields=["wallet_address"])
        messages.success(request, "Settings saved successfully.")
        return redirect("accounts:settings")

    return render(request, "accounts/settings.html", {"user": request.user})
