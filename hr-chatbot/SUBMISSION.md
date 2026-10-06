# HR Chat Agent: Submission Notes

Northstar People Desk is a proof of concept for an HR chat agent. An authenticated employee asks a question in plain English. A CrewAI agent decides which tools to use: a vector search over the HR policy documents, and tools that read that employee's leave record from Postgres or calculate leave by company rules. It then answers from what the tools returned and shows how the answer was produced.

## Stack

| Layer | Choice |
| --- | --- |
| Agent framework | CrewAI 1.15: one agent, one task, sequential process |
| Language model | Groq `openai/gpt-oss-120b` (free tier). Local Llama 3.2 through Ollama and paid OpenAI are configurable alternatives |
| Policy knowledge (RAG) | Chroma vector database, local MiniLM embeddings, cosine similarity |
| Employee data | Postgres 16: employees, leave balances, leave requests, holidays, chat history, audit log |
| Application | Django: session login, chat page, JSON chat API, admin |

## 1. Tool usage

The agent has seven tools. Each one closes over the signed-in employee when the request starts. No tool accepts an employee ID, so the model cannot ask for anyone else's record.

| Tool | What it does | Source |
| --- | --- | --- |
| `search_hr_policies` | Semantic search over the policy library; returns document, section, and excerpt | Chroma |
| `get_my_leave_balances` | Entitled, used, pending, and remaining days for each leave type | Postgres |
| `get_my_profile` | Department, joining date, confirmation or probation status, parental-leave track. Work email only when asked | Postgres |
| `get_my_leave_history` | Recent leave requests and their status | Postgres |
| `list_company_holidays` | Upcoming holidays, or every holiday in a given year | Postgres |
| `calculate_leave_days` | Deductible days for a date range, using weekends, holidays, and the sandwich rule | Rules engine plus Postgres holidays |
| `check_leave_eligibility` | Probation, notice period, per-request limits, parental track, and remaining balance | Rules engine plus Postgres |

Leave arithmetic is deterministic Python in `apps/directory/leave_rules.py`. The language model never does the calculation. For example, earned leave from 22 December 2026 to 2 January 2027 deducts 10 days: 7 working days plus 3 sandwiched days (Christmas and the weekend). The same dates as sick leave deduct 7, because sick leave has no sandwich rule. This matches the worked example in the leave policy document.

Every tool call writes an `AccessAuditLog` row recording the employee and the tool name.

## 2. Agent reasoning and workflow

1. **Authentication.** Django session login. Chat and the API require an account linked to an employee record.
2. **Access guard, before any model call.** A question asking for another employee's leave or profile, a list of everyone's records, or medical details is refused immediately with an explanation.
3. **Planning.** With a hosted model, CrewAI planning is on. The agent first writes a step-by-step plan naming the tool for each step. For "What is my leave balance?" the plan was: step 1, call `get_my_leave_balances`; step 2, answer from that data.
4. **Tool loop.** The agent calls tools, reads the JSON results, and decides whether it needs another tool, for example a policy search followed by an eligibility check. It is capped at 6 iterations and 120 seconds.
5. **Grounding rules in the task prompt.** Call a tool before stating any balance, eligibility result, day count, holiday date, or profile fact. Search the policies before explaining a policy. If the tools don't contain the answer, say what is missing instead of guessing.

With local Llama on a CPU, planning is turned off and the time limit is raised, because each extra model pass takes minutes there.

## 3. Context handling

- **Who is asking:** the employee's name, code, job title, department, and location are put into the task.
- **When:** today's date is put into the task, so "next Monday" or "this year" resolve correctly and notice periods are measured from the real date.
- **Conversation memory:** each chat session's messages are stored in Postgres. The last 6 messages, each trimmed to 500 characters, go into the next request. A follow-up such as "What if I book that as sick leave instead?" therefore reuses the dates from the previous question.
- **Reset:** **New chat** starts a new session and drops the earlier context.
- **No hidden memory:** CrewAI's built-in memory is off. Policy knowledge comes only from the Chroma index, and employee facts only from Postgres.

## 4. Response generation

- The model writes the final answer from the tool results only, in short plain sentences, including the numbers and dates the tools returned. It names the policy section when it used policy search.
- Under each answer, **How this answer was produced** lists every tool call with its arguments and result, plus the policy sections retrieved from Chroma as citations.
- When no model is configured or the model fails, the page says so rather than inventing an answer.

## Verified example

The question "What is my leave balance?" was asked as `priya.sharma` against Groq:

- **Plan:** call `get_my_leave_balances`, then answer.
- **Tool called:** `get_my_leave_balances`
- **Answer:** a 2026 balance table dated 2026-10-05 showing casual 5, earned 11, sick 7, optional holiday 1, maternity 182, paternity 0. These match the seeded Postgres records.

The full run took about 20 seconds, including starting the script.

## Demo flows

| Sign in as | Question | Expected result |
| --- | --- | --- |
| `priya.sharma` | What is my leave balance? | Earned leave remaining 11 |
| `priya.sharma` | Am I eligible for earned leave from 10 November 2026 to 13 November 2026? | Eligible, 4 days deducted |
| `priya.sharma` | How many earned leave days are deducted from 22 December 2026 to 2 January 2027? | 10 days, including 3 sandwich days |
| `priya.sharma` | What if I book that as sick leave instead? | 7 days, reusing the dates from the previous question |
| `priya.sharma` | What is the work from home policy? | Two days a week for confirmed employees, with a policy citation |
| `priya.sharma` | What is Arjun Mehta's leave balance? | Refused: only your own record |
| `arjun.mehta` | Same earned-leave question | Not eligible: still in probation |

Demo password for every account: `Northstar#2026`. All employees and policies are fictional.

## Running it

See `README.md` for setup, `ARCHITECTURE.md` for design detail, and `DEMO_SCRIPT.md` for the recording plan.
