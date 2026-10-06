from django.contrib import admin

from apps.assistant.models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("created_at", "role")
    readonly_fields = ("created_at", "role")
    can_delete = False
    show_change_link = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "created_at")
    inlines = [ChatMessageInline]
