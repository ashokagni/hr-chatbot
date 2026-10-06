from django.contrib import admin
from django.urls import path

from apps.accounts.views import login_view, logout_view
from apps.assistant.views import chat_api, chat_page

admin.site.site_header = "Northstar People Desk"
admin.site.site_title = "People Desk"
admin.site.index_title = "Employee and leave records"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("chat/", chat_page, name="chat"),
    path("api/chat/", chat_api, name="chat_api"),
]
