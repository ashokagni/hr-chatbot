# Northstar People Desk

Proof of concept for an authenticated HR chat agent.

An employee signs in, asks a question, and a [CrewAI](https://docs.crewai.com/) agent answers it. Policy questions are retrieved from a Chroma vector index. Leave balances, eligibility, and day counts come from Postgres through tools. The language model can be a free local Llama, a free Groq-hosted open model, or a paid OpenAI model.

The policies in `policies/` are fictional Northstar Labs documents written for this proof of concept. Replace those markdown files and run `python manage.py index_policies` to point the assistant at another policy set.

## Stack

| Piece | Choice |
| --- | --- |
| Agent framework | CrewAI, one agent, tool calling, planning enabled |
| Policy retrieval | Chroma persistent vector database, local MiniLM embeddings |
| Employee and leave data | Postgres 16 |
| Application | Django |
| Free model | Ollama `llama3.2` (local), or Groq `openai/gpt-oss-120b` (hosted) |
| Paid model | OpenAI `gpt-4o-mini` |

## Run it

Docker Desktop is required for the proof-of-concept Postgres. The container is published on host port **5433** so it does not collide with a Postgres already listening on 5432. `.env` sets `POSTGRES_PORT=5433`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
python manage.py migrate
python manage.py seed_demo
python manage.py index_policies
python manage.py runserver
```

Open http://127.0.0.1:8000/

Demo password for every account: `Northstar#2026`

| Username | Who |
| --- | --- |
| `priya.sharma` | Confirmed engineer. Earned leave is available. |
| `arjun.mehta` | Still in probation. Earned leave is refused. |
| `neha.iyer` | People team. Also signs in to http://127.0.0.1:8000/admin/ to view Postgres. |

## Language model

`LLM_PROVIDER=auto` uses a Groq key if `GROQ_API_KEY` is set, then an OpenAI key, and only then a local Ollama model. Set `LLM_PROVIDER=groq`, `openai`, or `ollama` to force one.

Free local Llama:

```powershell
# Install Ollama from https://ollama.com/download, then:
ollama pull llama3.2
```

Or start the optional container and pull the model there:

```powershell
docker compose --profile llama up -d
docker exec -it hr-chat-ollama ollama pull llama3.2
```

Free hosted model: create a Groq key and set `GROQ_API_KEY` in `.env`. Groq's model list changes; `GROQ_MODEL` must be a chat model your key can use (list them at `https://api.groq.com/openai/v1/models`).

Paid: set `OPENAI_API_KEY`. The chat page badge shows which model CrewAI is using.

The first `index_policies` run downloads the small local embedding model used by Chroma.

## Tests

```powershell
python manage.py test
```

Tests use an in-memory SQLite database. The running app uses Postgres.

## What to show

See `DEMO_SCRIPT.md` for a short recording plan and `ARCHITECTURE.md` for the submission write-up.
