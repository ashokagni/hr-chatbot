import logging
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.assistant.agent.crew import CrewRunError, run_hr_crew
from apps.assistant.agent.llm import LLMNotConfigured, describe_llm
from apps.assistant.models import ChatMessage, ChatSession
from apps.directory.models import Employee

logger = logging.getLogger("apps.assistant")

PROMPTS = [
    "What is my leave balance?",
    "Am I eligible for earned leave from 10 November 2026 to 13 November 2026?",
    "How many earned leave days are deducted from 22 December 2026 to 2 January 2027?",
    "What is the work from home policy?",
]


@login_required
def chat_page(request):
    employee = _employee(request.user)
    if employee is None:
        return render(request, "no_employee.html", status=403)
    session = employee.chat_sessions.order_by("-created_at").first()
    messages = []
    if session is not None:
        messages = [_message_payload(message) for message in session.messages.all()]
    boot = {
        "sessionId": None if session is None else session.id,
        "modeLabel": describe_llm(),
        "messages": messages,
        "prompts": PROMPTS,
    }
    return render(request, "chat.html", {"employee": employee, "boot": boot})


@login_required
@require_POST
def chat_api(request):
    employee = _employee(request.user)
    if employee is None:
        return JsonResponse({"error": "This account is not linked to an employee record."}, status=403)
    if not _within_rate_limit(request.user.pk):
        return JsonResponse({"error": "Too many questions in a short time. Wait a minute and try again."}, status=429)

    try:
        payload = json_body(request)
    except ValueError:
        return JsonResponse({"error": "Send a JSON message."}, status=400)

    message = str(payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Enter a question."}, status=400)
    if len(message) > 2000:
        return JsonResponse({"error": "Keep the question under 2000 characters."}, status=400)

    if payload.get("new_session") or not payload.get("session_id"):
        session = ChatSession.objects.create(employee=employee)
    else:
        session = get_object_or_404(ChatSession, pk=payload["session_id"], employee=employee)

    prior = list(session.messages.values("role", "content"))
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=message)
    try:
        result = run_hr_crew(employee, prior, message)
    except LLMNotConfigured as exc:
        result = {"answer": str(exc), "steps": [], "citations": [], "mode": describe_llm()}
    except CrewRunError:
        logger.error("crew failed employee=%s", employee.employee_code)
        result = {
            "answer": "I couldn't finish that request. Check that the language model is running, then try again.",
            "steps": [],
            "citations": [],
            "mode": describe_llm(),
        }

    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=result["answer"],
        trace=result["steps"],
        citations=result["citations"],
    )
    result["session_id"] = session.id
    return JsonResponse(result)


def _employee(user):
    try:
        return user.employee
    except Employee.DoesNotExist:
        return None


def _message_payload(message: ChatMessage) -> dict:
    return {
        "role": message.role,
        "content": message.content,
        "steps": message.trace,
        "citations": message.citations,
    }


def _within_rate_limit(user_id: int) -> bool:
    key = f"chat-{user_id}-{int(time.time()) // 60}"
    count = cache.get(key, 0)
    if count >= 20:
        return False
    cache.set(key, count + 1, 70)
    return True


def json_body(request) -> dict:
    import json

    if not request.body:
        return {}
    data = json.loads(request.body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected object")
    return data
