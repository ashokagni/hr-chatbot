const boot = JSON.parse(document.getElementById("chat-boot").textContent);
const messagesEl = document.getElementById("messages");
const promptsEl = document.getElementById("prompts");
const form = document.getElementById("composer");
const question = document.getElementById("question");
const send = document.getElementById("send");
const modeBadge = document.getElementById("mode-badge");
const csrf = document.querySelector('meta[name="csrf-token"]').content;

let sessionId = boot.sessionId;
let newSession = false;
modeBadge.textContent = boot.modeLabel;

boot.prompts.forEach((prompt) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = prompt;
  button.addEventListener("click", () => submit(prompt));
  promptsEl.appendChild(button);
});

boot.messages.forEach((message, index) => renderMessage(message, index === boot.messages.length - 1));
scrollDown();

document.getElementById("new-chat").addEventListener("click", () => {
  newSession = true;
  sessionId = null;
  messagesEl.replaceChildren();
  question.focus();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(question.value);
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

async function submit(text) {
  const message = text.trim();
  if (!message || send.disabled) return;
  question.value = "";
  renderMessage({ role: "user", content: message });
  const pending = renderMessage({ role: "assistant", content: "Checking policy and your leave record…" });
  send.disabled = true;
  try {
    const response = await fetch("/api/chat/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
      },
      body: JSON.stringify({ message, session_id: sessionId, new_session: newSession }),
    });
    const data = await response.json();
    pending.remove();
    if (!response.ok) {
      renderMessage({ role: "assistant", content: data.error || "The assistant could not answer." });
      return;
    }
    sessionId = data.session_id;
    newSession = false;
    if (data.mode) modeBadge.textContent = data.mode;
    renderMessage({
      role: "assistant",
      content: data.answer,
      steps: data.steps,
      citations: data.citations,
    }, true);
  } catch (_error) {
    pending.remove();
    renderMessage({ role: "assistant", content: "The request did not complete. Check that the app is still running." });
  } finally {
    send.disabled = false;
    scrollDown();
  }
}

function renderMessage(message, openTrace = false) {
  const card = document.createElement("article");
  card.className = `message ${message.role}`;
  card.textContent = message.content;
  if (message.role === "assistant" && ((message.steps && message.steps.length) || (message.citations && message.citations.length))) {
    const details = document.createElement("details");
    details.className = "trace";
    details.open = openTrace;
    const summary = document.createElement("summary");
    summary.textContent = "How this answer was produced";
    details.appendChild(summary);
    (message.steps || []).forEach((step) => {
      const row = document.createElement("div");
      row.className = "step";
      const title = document.createElement("strong");
      title.textContent = step.title || step.kind || "Step";
      const detail = document.createElement("p");
      detail.textContent = step.detail || step.result || "";
      row.append(title, detail);
      details.appendChild(row);
    });
    (message.citations || []).forEach((citation) => {
      const row = document.createElement("div");
      row.className = "citation";
      row.textContent = `${citation.document} · ${citation.section}`;
      details.appendChild(row);
    });
    card.appendChild(details);
  }
  messagesEl.appendChild(card);
  scrollDown();
  return card;
}

function scrollDown() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
