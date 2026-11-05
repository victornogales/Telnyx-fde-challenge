# Use case: RefillLine

A phone line that handles prescription refill and "is my order ready?" calls for a small pharmacy, end to end. It hands off to a pharmacist whenever a person is needed.

> All patient data in this project is synthetic. RefillLine never gives medical advice.

---

## 1. The problem

### Who has it
Independent and small-chain community pharmacies: one or two pharmacists, a couple of technicians, no call centre.

### What goes wrong today
- **The phone competes with the counter.** The same staff who fill prescriptions and serve walk-in patients also answer the phone. Every call interrupts dispensing work, which needs concentration.
- **Most calls are routine and repetitive.** "Can I refill my blood-pressure medication?", "Is my prescription ready?", "What time do you close?". Each takes a few minutes and almost never needs a pharmacist's judgement.
- **But they can't be handled carelessly.** Before discussing a prescription, staff must confirm who they're talking to. Calls may need a recording or automation disclosure. Getting either wrong is a privacy and compliance problem, not just a bad experience.
- **Callers wait.** Callers put on hold during busy periods hang up and call back, which adds to the load, or walk in to ask in person.
- **After hours, nothing happens.** A patient who realises at 9 pm that they're out of medication can't even start a refill until the next day.

### Why existing fixes fall short
| Option | Shortcoming |
|---|---|
| Touch-tone IVR ("press 1 for refills…") | Rigid menus, poor with older callers, can't handle "I need my Lipitor, and also are you open Saturday?" |
| Patient app / web portal | Many patients, especially older ones on regular medication, prefer to phone |
| Hiring more staff | Expensive for a small pharmacy, and the volume is spiky |
| A free-form LLM voice bot | Natural, but unpredictable: it might skip identity checks, paraphrase a required disclosure, or try to answer a clinical question |

**What this means:** the job needs a natural voice conversation, but one held inside **strict structure**. There's a required script, verification before anything sensitive, and a guaranteed path to a human.

---

## 2. The approach

### What a caller experiences
1. **Disclosure, word for word:** "Thanks for calling Maple Pharmacy, Maria. This call may be recorded for quality and safety. I'm an automated assistant; say 'pharmacist' at any time to reach a person."
2. **Recognised before the first question.** The number is looked up when the call connects, so known callers are greeted by name. The assistant already knows whether they called recently and whether their account is locked.
3. **Says what they need**, in their own words: a refill, an order status, hours or a general question, or a person.
4. **Verifies identity** by date of birth before anything account-specific. After three wrong attempts, verification is locked for 15 minutes, **including on later calls**, and the caller is offered a pharmacist.
5. **Refill:** hears which of their prescriptions can be refilled, picks one, hears it read back, confirms with an explicit "yes", and gets a pickup estimate.
6. **Status:** hears whether open refills are "submitted" or "ready". A refill becomes "ready" on its own about two minutes after submission in the demo. That's done with a scheduled actor alarm.
7. **General questions:** opening hours, location, and a medication's label purpose ("what is this for?"). The purpose text comes from the public openFDA drug-label API. Anything clinical goes to a pharmacist.
8. **Escalation, always available:** asking for a person, being locked out, or a call running past 5 minutes routes to a warm transfer. If nobody answers, the caller hears the opening hours and the call ends politely.

### How it's built, briefly
| Need | Telnyx feature | Why it fits |
|---|---|---|
| A natural but controlled conversation | **AI Assistant + Conversation Workflow** | One focused node per step, with clear edges between them; tools scoped per node |
| Exact wording for disclosures | **Speak nodes** | Delivered verbatim, with no model involved |
| Routing on facts (locked out? after hours? call too long?) | **Variable-comparison edges** | Deterministic, checked before the model speaks |
| Routing on what the caller means | **LLM-condition edges** | Human intent is fuzzy; this is what the model is good at |
| Personalisation at call start | **Dynamic webhook variables** served by an **Edge Function** (Python) | Name, call history, lockout and feature flags reach the conversation before the first word |
| Account actions during the call | **Custom MCP server** on an Edge Function (Python), 6 tools | Verification, prescriptions, refills, status, medication info, pharmacy info |
| Per-caller state that must be exactly right | **Stateful Actor** `CallerSession` (behind a small TypeScript gateway) | Attempt counter, lockout, refill list and the "ready" alarm. Everything is read-modify-write on one caller, safe without locks |
| Global, read-mostly data | **KV** | Feature flags (toggle after-hours mode with no redeploy) and a TTL cache of openFDA results |
| Knowing it works | **Structured logs, metrics and a trace ID** across webhook → gateway/actor → MCP | Any call can be reconstructed from one ID |

**Security sits on the server.** The conversation flow guides the caller, but the MCP server is the enforcement point. Prescription and refill tools refuse to run unless the caller's actor records a successful verification in the last 30 minutes. The deliberate tradeoff: a caller who verified and calls back within that window isn't asked again. A mis-routed conversation can't leak data.

---

## 3. Expected results

### What the prototype must show (demo-day acceptance)
| Scenario | Expected outcome |
|---|---|
| Known caller, refill | Greeted by name → verified → chooses → read-back → confirmed → refill recorded; second call shows "ready" |
| Status check | Verified → hears current status of open refills |
| Wrong DOB ×3 | Locked out, offered a pharmacist; **a new call within 15 minutes is routed to a human before the assistant asks anything** |
| Unknown number | Generic greeting; account actions refused politely; FAQ and human still available |
| "Pharmacist, please" at any point | Transfer; if unanswered, hours given and call closed |
| After-hours flag flipped in KV | Next call takes the after-hours path; **no redeploy** |
| Medication question asked twice | First answer from openFDA, second from the KV cache (visible in logs as miss → hit) |
| Webhook or gateway failure | Call still works with safe defaults; account tools fail closed; failure visible in logs within a minute |
| 20 simultaneous updates for one caller | Counter increases by exactly 20 (actor); the same test against plain KV loses updates |

### Engineering targets
- Webhook answers well under its 1.5 s budget: aim for **< 1 s p95**, measured with `telnyx-edge metrics`.
- **Every** request and tool call produces one structured log line carrying the call's `trace_id`.
- **No bare 500s.** Every failure degrades gracefully and is logged.

### What it would mean for a real pharmacy (hypotheses, not measured)
- Most refill and status calls handled without staff involvement, so technicians are interrupted less while dispensing.
- Refill requests captured 24/7, including after hours.
- Consistent compliance: the disclosure is always word for word, and verification always happens before any account detail.
- Staff time goes to the calls that need a pharmacist, with the caller already identified.

A real pilot would measure:
- containment rate (the share of calls finished without a human)
- transfer rate and reasons
- verification failure rate
- average call duration
- caller hang-ups during the call

---

## 4. Why we picked this use case for the challenge

**1. Every required feature has a real job, nothing is forced in.**

| Challenge requirement | Where it's needed for real |
|---|---|
| Multi-step workflow | Disclose → triage → verify → act → confirm → close is a real sequence; skipping steps is a real failure |
| Speak node | A disclosure must be word for word |
| Variable comparisons vs LLM conditions | Lockout, flags and timeout are facts; "I want my refill" is intent. The use case naturally needs **both**, which shows the judgement they're asking about |
| Dynamic webhook variables | Personalisation *and* routing decisions (lockout from a previous call) before the conversation starts |
| MCP with ≥ 3 tools | Six tools with clear, separate purposes, scoped per node |
| Stateful Actor | The verification attempt counter is a textbook read-modify-write race. Two concurrent calls must not both see "attempt 2". This is exactly what actors exist for |
| KV | Flags (global, rarely changed, slight staleness is fine) and a cache in front of a slow external API, both classic KV workloads |
| Actor alarms (stretch) | "Your refill is ready" is genuinely future, scheduled work |
| Observability | Compliance-sensitive flows make "can you prove what happened on that call?" a real requirement, not a checkbox |

**2. It shows judgement about which feature fits which job.** The interviewers explicitly score choosing actor vs KV vs plain function logic. Here the contrast is concrete and demonstrable:
- a counter and lockout that *must* be exact → actor
- flags and a cache that can be a second stale → KV
- static reference data → plain code

**3. It has real fallback paths, not just a happy path.** Wrong answers, lockouts, unknown callers, timeouts, failed transfers and backend outages all occur naturally. The challenge asks for "the happy path AND fallback paths".

**4. Voice is the right medium for these users.** It's a population that phones rather than uses apps, so voice design (short sentences, reading dates back, one question at a time) matters for real.

**5. It's realistic for Telnyx's customers.** Regulated, phone-heavy small businesses are a natural market for Voice AI on Telnyx. The same pattern (disclosure → verify → act → escalate) carries over to clinics, banks and utilities.

**6. It's demonstrable live in 10 minutes.** A few phone calls show the workflow, the MCP tool calls, personalisation, actor state changing (lockout, the "ready" alarm), a KV flag flip and the logs, all observable while the demo runs.

---

## 5. Out of scope (stated honestly)
- Integration with a real pharmacy management system. A bundled synthetic dataset stands in for it.
- Clinical advice, drug interactions, controlled-substance refills (always routed to a pharmacist).
- Real SMS notifications. US SMS needs carrier (10DLC) registration that won't finish within the challenge week.
- Strong identity proofing beyond date of birth (a production system would add more factors or per-caller credentials).
