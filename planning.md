# Provenance Guard Planning

## Architecture

```text
Submission Flow:

POST /submit
    ↓ raw text + creator_id
Validate request
    ↓
Groq LLM Signal
    ↓ llm_score
Stylometric Heuristic Signal
    ↓ heuristic_score
Confidence Scoring
    ↓ combined score + attribution result
Transparency Label Generator
    ↓ user-facing label
Audit Log
    ↓ structured log entry
JSON Response

Appeal Flow:

POST /appeal
    ↓ content_id + creator_reasoning
Find original content decision
    ↓
Update status to under_review
    ↓
Write appeal event to audit log
    ↓
JSON confirmation response
The submission flow accepts a creator's text and routes it through two independent detection signals: an LLM-based semantic signal and a stylometric structural signal. The results are combined into one confidence score, mapped to a plain-language transparency label, saved in the audit log, and returned to the caller.

The appeal flow lets a creator contest a classification by submitting reasoning tied to a content ID. The system updates that content status to under_review and records the appeal in the structured audit log.

Detection Signals
Signal 1: Groq LLM Classification

This signal asks an LLM to assess whether the submitted text appears human-written, AI-generated, or uncertain. It captures semantic and stylistic patterns such as generic phrasing, over-polished tone, unnatural consistency, and lack of lived detail.

Output:

llm_score: float from 0 to 1
0 means strongly human-like
1 means strongly AI-like

Blind spot:
The LLM can be biased toward labeling polished formal writing as AI-generated, even when it is human-written.

Signal 2: Stylometric Heuristics

This signal computes measurable writing statistics:

sentence length variance
vocabulary diversity/type-token ratio
punctuation density
generic AI phrase count

It captures structural patterns in the text rather than meaning.

Output:

heuristic_score: float from 0 to 1
0 means structurally human-like
1 means structurally AI-like

Blind spot:
Poems, formal essays, non-native English writing, and intentionally repetitive creative writing may be scored incorrectly.

Confidence Scoring

The final AI-likelihood score is calculated as:

combined_score = (0.60 * llm_score) + (0.40 * heuristic_score)

The LLM gets slightly more weight because it captures broader semantic patterns, but the heuristic signal prevents the system from relying only on one model.

Thresholds:

combined_score >= 0.75: likely AI-generated
combined_score <= 0.35: likely human-written
0.36 to 0.74: uncertain

A score near 0.5 means the system does not have enough evidence to make a confident attribution. Because false positives are harmful for creators, borderline scores should produce an uncertain label instead of accusing the creator of using AI.

Transparency Label Design

High-confidence AI label:

"This content appears likely to be AI-generated. Our system found multiple signals associated with AI-written text, but this decision may be appealed by the creator."

High-confidence human label:

"This content appears likely to be human-written. Our system found stronger signals of original human authorship, though automated detection is not perfect."

Uncertain label:

"We could not confidently determine whether this content was human-written or AI-generated. This label is intentionally cautious because automated detection can be wrong."

Appeals Workflow

A creator can submit an appeal by providing:

content_id
creator_reasoning

When an appeal is received, the system:

Finds the original content decision.
Updates the content status to under_review.
Stores the creator's reasoning.
Writes an appeal event to the audit log.
Returns confirmation to the creator.

A human reviewer would see:

original text or content ID
original classification
confidence score
individual signal scores
creator reasoning
current status
Anticipated Edge Cases
A poem with repeated phrases may be incorrectly scored as AI-generated because the stylometric signal may treat repetition and low vocabulary diversity as suspicious.
A formal essay written by a human may be scored as AI-generated because both the LLM and heuristics may associate polished, structured writing with AI output.
A lightly edited AI-generated text may fall into the uncertain range because human edits can add irregularity and specificity.
AI Tool Plan
M3: Submission endpoint + first signal

I will provide the detection signals section and architecture diagram to the AI tool. I will ask it to generate a Flask app skeleton with a POST /submit route and a Groq-based signal function. I will verify the output by testing the signal function independently before wiring it into the endpoint.

M4: Second signal + confidence scoring

I will provide the detection signals, confidence scoring, and architecture sections. I will ask the AI tool to generate stylometric scoring functions and combined scoring logic. I will verify that clearly AI-like, clearly human-like, and borderline inputs produce meaningfully different scores.

M5: Production layer

I will provide the transparency label, appeals workflow, and architecture sections. I will ask the AI tool to generate label mapping logic, the /appeal endpoint, and audit log updates. I will verify that all three labels are reachable and that an appeal updates the content status to under_review.