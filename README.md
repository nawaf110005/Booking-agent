# Tazkara (Booking-Agent)

Tazkara is a chat-first conversational ticket booking agent for live events in Saudi Arabia. It collapses the entire booking funnel—event search, membership verification, price quoting, visual seat selection, payment processing, and ticket generation—into a single chat interface.

This project was built as a Capstone for the **Agentic AI Bootcamp**.

---

## 🛠️ Technology Stack
*   **Backend**: Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic
*   **Database**: SQLite (default local) / PostgreSQL-compatible
*   **Frontend**: Next.js 14 + Tailwind CSS (primary UI) · FastAPI Static Server (fallback UI)
*   **NLU / AI**: Multi-agent specialists driven by an LLM (provider-agnostic — Anthropic / OpenAI / Gemini / nano-gpt; active: nano-gpt serving `gemini-2.5-flash-preview-04-17`), with a deterministic Offline Brain fallback when no key is set
*   **Utilities**: Pillow (dynamic seatmap rendering) · HMAC (secure ticket QR signing)

---

## 🚀 Quickstart

### Prerequisites
Make sure you have the following installed:
*   Python 3.11+
*   [uv](https://github.com/astral-sh/uv) (fast Python package manager)
*   Node.js 18+ (for the Next.js frontend)

### Run Backend + Frontend (Recommended)
You can launch both the backend and Next.js frontend with a single command:

```bash
./run.sh full
```
*(On Windows, use `.\run.ps1 full`)*

Once started, open your browser and navigate to **http://localhost:3000** (or http://localhost:3001).

### Manual Setup

1.  **Initialize Environment & Dependencies**:
    ```bash
    uv venv --python 3.11
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    uv pip install -e ".[dev,api,ui,llm]"
    ```
2.  **Initialize and Seed the Database**:
    ```bash
    uv run booking-agent init-db
    uv run booking-agent seed
    ```
3.  **Start Backend API Server**:
    ```bash
    uv run uvicorn booking_agent.api.app:app --reload --port 8000
    ```
4.  **Start Frontend Dev Server**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

---

## 📐 Architecture & Flow

Tazkara is structured as a modular 4-tier system:

1.  **Frontend (Next.js / HTML)**: Handles chat renders, interactive seatmaps, and ticket display.
2.  **API Layer (FastAPI)**: Routes chats, manages session IDs, and translates domain-level errors to standard HTTP response codes.
3.  **Agent Layer (Multi-Agent Orchestrator)**: An orchestrator routes each turn through role-based specialists — catalog → membership → pricing → seating — each an LLM tool-calling loop over its own tools (`multi_agent` mode, default; `tool_agent` runs a single full-tool loop instead). With no provider key the specialists run on a deterministic offline brain, so the demo and tests work offline.
4.  **Tools Layer (Python Functions)**: Pure, isolated business logic for bookings, holds, pricing calculations, and seat releases.

### The Booking Lifecycle
Every conversation advances through the same phases (the orchestrator hands off a specialist per phase):
```
GREETING ➔ EVENT_SELECTION ➔ NEED_EMAIL ➔ CATEGORY_SELECTION ➔ NEED_QUANTITY ➔ SEAT_SELECTION ➔ AWAITING_CONFIRMATION ➔ PAYMENT ➔ CONFIRMED
```

---

## 🔒 Constitutional Principles
Tazkara follows a strict set of 8 governing rules defined in [.specify/memory/constitution.md](.specify/memory/constitution.md):
*   **I. Confirmation Before Payment**: Explicit HITL invoice gate before any payment session is initialized.
*   **II. Atomic Holds**: All-or-nothing seat holds with a strict 10-minute timeout to prevent double-booking.
*   **III. Repos-as-Tools**: No external ticketing APIs; all capabilities are native Python functions.
*   **IV. Exact Money**: Calculations are done strictly in minor units (halalas) using integer arithmetic.
*   **V. Tamper-Proof Tickets**: QR codes include cryptographic HMAC signatures.
*   **VI. Test-First**: Data/Mutating tools require complete unit test coverage before integration.
*   **VII. Observability**: Audit trails log state transitions, sentiment ratings, and tool queries.
*   **VIII. MVP First**: Started from a single-agent core, then grew it into the implemented multi-agent orchestrator + role specialists (the early state-machine MVP has since been retired).

---

## 🧪 Testing & Quality Assurance

To execute tests, check test coverage, or lint the codebase:

```bash
# Run full offline test suite (~161 tests)
./run.sh test

# View test coverage (target gate: 85%+)
uv run pytest --cov

# Lint the codebase
uv run ruff check src tests
```

---

## 👥 Team
*   **Nawaf Almufarej** (Lead)
*   **Dana**
*   **Hessa**
*   **Refal**

*Agentic AI Bootcamp Capstone 2026.*
