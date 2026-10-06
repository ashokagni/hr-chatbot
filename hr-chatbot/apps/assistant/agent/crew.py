from __future__ import annotations

import json
from datetime import date

from apps.assistant.agent.guard import refusal_reason
from apps.assistant.agent.llm import LLMNotConfigured, build_llm, describe_llm, resolve_llm
from apps.assistant.agent.tools import build_tools
from apps.directory.models import Employee


class CrewRunError(RuntimeError):
    pass


def run_hr_crew(employee: Employee, history: list[dict], question: str) -> dict:
    blocked = refusal_reason(employee, question)
    if blocked:
        return {
            "answer": blocked,
            "steps": [{"kind": "reasoning", "title": "Access check", "detail": "The question asked for data this assistant cannot use."}],
            "citations": [],
            "mode": describe_llm(),
        }

    trace: list[dict] = []
    try:
        llm = build_llm()
    except LLMNotConfigured:
        raise
    except Exception as exc:
        raise CrewRunError("The language model client could not be created.") from exc

    # A CPU-bound local Llama generates a few tokens per second, so a separate
    # planning pass adds minutes; hosted models are fast enough to keep it.
    local_model = resolve_llm()[0] == "ollama"

    from crewai import Agent, Crew, Process, Task

    tools = build_tools(employee, trace)
    agent_kwargs = {
        "role": "Northstar HR Assistant",
        "goal": (
            "Answer the signed-in employee using HR policy search and that employee's own Postgres records. "
            "Never invent leave numbers or policy rules."
        ),
        "backstory": (
            "You help Northstar Labs employees with published HR policy and their own leave record. "
            "Tools are already bound to the signed-in employee. You cannot and must not request another employee's data. "
            "You do not ask for symptoms, diagnoses, or medical documents."
        ),
        "tools": tools,
        "llm": llm,
        "verbose": True,
        "allow_delegation": False,
        "max_iter": 4 if local_model else 6,
        "max_execution_time": 900 if local_model else 120,
        "planning": not local_model,
    }
    agent = Agent(**agent_kwargs)

    history_text = _history_text(history)
    task = Task(
        description=(
            f"Today is {date.today().isoformat()}. The signed-in employee is {employee.user.get_full_name()} "
            f"({employee.employee_code}), {employee.job_title} in {employee.department}, {employee.location}.\n\n"
            f"Recent conversation:\n{history_text}\n\n"
            f"Question:\n{question}\n\n"
            "Call a tool before stating any balance, eligibility result, deducted day count, holiday date, or profile fact. "
            "Call Search HR policies before explaining a policy. "
            "If the tools do not contain the answer, say what is missing instead of guessing. "
            "Use dates exactly as the employee stated, in YYYY-MM-DD when you call tools."
        ),
        expected_output=(
            "A short answer in plain sentences. Include numbers and dates returned by tools. "
            "Name the policy section when policy search was used."
        ),
        agent=agent,
    )

    def on_step(step) -> None:
        thought = getattr(step, "thought", None) or getattr(step, "text", None)
        if thought:
            trace.append({"kind": "reasoning", "title": "Agent reasoning", "detail": str(thought)[:1200]})

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        step_callback=on_step,
    )

    try:
        result = crew.kickoff()
    except Exception as exc:
        raise CrewRunError("The HR crew did not finish.") from exc

    answer = getattr(result, "raw", None) or str(result)
    return {
        "answer": answer.strip(),
        "steps": trace,
        "citations": _citations(trace),
        "mode": describe_llm(),
    }


def _history_text(history: list[dict]) -> str:
    if not history:
        return "No earlier messages."
    lines = []
    for item in history[-6:]:
        content = " ".join(item.get("content", "").split())[:500]
        lines.append(f"{item.get('role', 'user')}: {content}")
    return "\n".join(lines)


def _citations(trace: list[dict]) -> list[dict]:
    citations = []
    for step in trace:
        if step.get("title") != "search_hr_policies":
            continue
        try:
            payload = json.loads(step.get("result") or "{}")
        except json.JSONDecodeError:
            continue
        for match in payload.get("matches", []):
            citations.append(
                {
                    "document": match.get("document", ""),
                    "section": match.get("section", ""),
                    "excerpt": (match.get("excerpt") or "")[:400],
                }
            )
    return citations
