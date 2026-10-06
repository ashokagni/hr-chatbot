# Demo recording

Aim for four to six minutes. Sign in as two different employees so it is obvious the tools read the signed-in record.

Before recording:

1. `docker compose up -d`
2. `python manage.py runserver`
3. Confirm the chat badge shows a real model, for example `CrewAI · ollama · ollama/llama3.2`.
4. Open the terminal where `runserver` is running. CrewAI prints its reasoning there as well as in the page.

## Shot list

1. Sign in as `priya.sharma` / `Northstar#2026`. Point out the badge that names CrewAI and the model.
2. Ask: `What is my leave balance?` Open "How this answer was produced" and show `get_my_leave_balances`. Priya's earned leave remaining is 11.
3. Ask: `Am I eligible for earned leave from 10 November 2026 to 13 November 2026?` Show `check_leave_eligibility`. She is eligible, and 4 days would be deducted.
4. Ask: `How many earned leave days are deducted from 22 December 2026 to 2 January 2027?` The answer should be 10, with the sandwich days visible in the tool result. This matches the example in the leave policy.
5. Ask: `What if I book that as sick leave instead?` The agent should reuse 22 December and 2 January from the conversation and return 7 days, because sick leave has no sandwich rule.
6. Ask: `What is the work from home policy?` Show `search_hr_policies` and the Work From Home citation. The limit is two days a week for a confirmed employee.
7. Sign out. Sign in as `arjun.mehta` with the same password. Ask the same earned-leave eligibility question. The answer should refuse it because he is still in probation and has no earned-leave balance.
8. Optional: sign in as `neha.iyer` at http://127.0.0.1:8000/admin/ and show the Postgres leave rows and access log.

If the badge says no model is configured, start Ollama or add a Groq or OpenAI key before recording. The page will say so instead of inventing a balance.
