# Project Evaluation Prep & Critical Audit Sheet

This sheet prepares you for your evaluation by outlining the real, honest limitations of the current codebase and how to address them constructively when asked by evaluators. Acknowledging technical debt and showing a clear mitigation roadmap demonstrates senior engineering maturity.

---

## 1. Critical Gaps & Talking Points for Evaluators

When evaluators review the five core criteria, be prepared to answer questions on these specific architectural and technical issues:

### A. Technical Choices (Rubric: 1–5 Scale)
*   **The Flaw**: The application currently has **zero authentication** for email identification. A user can type any email (e.g. `nawaf@example.com`) and claim member discounts or view bookings.
*   **Defense/Roadmap**: *“For this MVP Capstone, we prioritised conversation state flow. However, in a production release, we would integrate an SMS/email OTP (One-Time Password) verification gate right after the email is provided, before advancing the state past `NEED_EMAIL`.”*
*   **The Flaw**: SQLite is used for database writes. High concurrency (peak sales) will lock the database.
*   **Defense/Roadmap**: *“SQLite is ideal for zero-configuration testing and offline grading. However, our database models use SQLAlchemy 2.0 ORM, meaning we can switch the dialect to PostgreSQL in production with zero code changes, allowing us to implement row-level locks (`FOR UPDATE`) for concurrent seat selections.”*

### B. Architectural Choices (Rubric: 1–5 Scale)
*   **The Flaw**: The conversation state and seat-holds are stored entirely in an in-memory dictionary (`SESSION_STORE`). If the FastAPI server restarts or scales out, session memory is lost.
*   **Defense/Roadmap**: *“We decoupled the state definitions from the logic. The next step is to swap the raw in-memory store in `store.py` with a **Redis cache** using the same key-value retrieval interface, ensuring horizontal scale-out safety.”*
*   **The Flaw**: Brittle regex-based fallback extraction if the LLM provider fails.
*   **Defense/Roadmap**: *“The rule-based extractor handles clean inputs. For production, we would replace simple regex splits with fuzzy matching libraries (like `RapidFuzz`) and a lightweight local grammar-based model (e.g. using Llama.cpp with JSON schemas) to parse slot values reliably without an internet connection.”*

---

## 2. Dynamic Demo Flow under Time Constraints

If the evaluators give you a strict time limit (e.g. 3 minutes):

1.  **Do NOT do a slow multi-turn chat**. 
2.  Type: `"I want to book 4 Gold tickets for Coldplay in Riyadh, nawaf@example.com"`
3.  Explain: *“Our natural language parser extracts all slots (event, email, category, quantity) in one turn and takes us directly to seat selection. This showcases the efficiency of our hybrid NLU engine.”*
4.  Run `./run.sh test` in the terminal to immediately show 161 passing unit and integration tests under 2 seconds.

---

## 3. Reference Documentation

For a comprehensive analysis of all technical debt and security concerns, refer to:
*   [CRITICAL_EVALUATION.md](file:///Users/nawaf/Desktop/dev/Booking-agent/docs/CRITICAL_EVALUATION.md) (Detailed security and performance gap analysis).
*   [README.md](file:///Users/nawaf/Desktop/dev/Booking-agent/README.md) (Updated setup and architecture manual).
