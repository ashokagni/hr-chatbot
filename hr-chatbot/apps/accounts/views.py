from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.directory.demo_data import DEMO_PASSWORD, PEOPLE
from apps.directory.models import Employee


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("chat")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not Employee.objects.filter(user=user).exists():
            form.add_error(None, "This account is not linked to an employee record.")
        else:
            login(request, user)
            return redirect("chat")
    accounts = [
        {
            "username": person["username"],
            "name": f"{person['first_name']} {person['last_name']}",
            "title": person["job_title"],
        }
        for person in PEOPLE
    ]
    return render(
        request,
        "login.html",
        {"form": form, "accounts": accounts, "demo_password": DEMO_PASSWORD or settings.DEMO_PASSWORD},
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
