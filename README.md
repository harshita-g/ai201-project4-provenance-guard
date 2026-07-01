# Provenance Guard

Provenance Guard is a Flask backend API that analyzes text submissions and classifies them as likely human-written, likely AI-generated, or uncertain. It is designed for creative sharing platforms that want to give readers transparent attribution context while avoiding overconfident automated decisions.

The system uses a multi-signal detection pipeline, confidence scoring, plain-language transparency labels, an appeals workflow, rate limiting, and structured audit logging.

---

## Architecture Overview

A submitted piece of text moves through the system in this order:

```text
User submits text + creator_id
        ↓
POST /submit
        ↓
Validate request body
        ↓
Signal 1: Groq LLM classification
        ↓
Signal 2: Stylometric heuristic scoring
        ↓
Combined confidence scoring
        ↓
Transparency label generation
        ↓
Structured audit log entry
        ↓
JSON response returned to user
```

Appeals follow a separate flow:

```text
Creator submits content_id + appeal reasoning
        ↓
POST /appeal
        ↓
Find original classification decision
        ↓
Update content status to under_review
        ↓
Write appeal event to audit log
        ↓
JSON confirmation returned to creator
```

The submission flow is intentionally cautious. The system does not force every result into a binary human-or-AI label. If the two detection signals do not provide strong enough evidence, the content is labeled as uncertain.

---

## Features

- Content submission endpoint for text attribution analysis
- Multi-signal detection pipeline
- Confidence scoring with an explicit uncertainty band
- User-facing transparency labels
- Creator appeals workflow
- Rate limiting on the submission endpoint
- Structured audit logging for classifications and appeals

---

## API Endpoints

### GET `/health`

Checks whether the API is running.

Example response:

```json
{
  "status": "ok"
}
```

### POST `/submit`

Accepts a text submission and returns an attribution decision.

Example request:

```json
{
  "text": "Example text to classify.",
  "creator_id": "test-user-1"
}
```

Example response fields:

```json
{
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_id": "clean-human-1",
  "attribution": "likely_human",
  "confidence": 0.812,
  "label": "This content appears likely to be human-written. Our system found stronger signals of original human authorship, though automated detection is not perfect.",
  "signals": {
    "combined_score": 0.188,
    "llm": {
      "score": 0.2,
      "reasoning": "The text features informal language, personal opinions, and a conversational tone, which are characteristic of human-written reviews. The use of colloquial expressions and emotional responses also suggest a human author."
    },
    "stylometric": {
      "score": 0.17
    }
  },
  "status": "classified"
}

```

### POST `/appeal`

Allows a creator to contest a classification.

Example request:

```json
{
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_reasoning": "I wrote this myself. I am appealing because the system may have interpreted my formal wording or repeated phrasing as AI-generated."
}
```

Example response:

```json
{
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "message": "Appeal received. This content is now under review.",
  "status": "under_review"
}
```

### GET `/log`

Returns recent structured audit log entries.

---

## Detection Signals

The system uses two distinct signals. One signal is semantic and model-based, while the other is structural and statistics-based. This makes the pipeline more informative than relying on one signal alone.

### Signal 1: Groq LLM Classification

The first signal uses Groq with `llama-3.3-70b-versatile` to evaluate whether a text appears human-written, AI-generated, or ambiguous. It returns a score from `0` to `1`:

- `0` means strongly human-like
- `0.5` means uncertain
- `1` means strongly AI-like

This signal captures semantic and stylistic patterns such as generic phrasing, overly polished tone, lack of personal detail, and repetitive explanation structure.

**Why I chose it:** An LLM can evaluate the overall style and meaning of a passage more holistically than simple rules.

**What it misses:** The LLM may incorrectly treat polished human writing, academic writing, or non-native English writing as AI-generated. It can also be sensitive to prompt wording and may not be fully consistent across similar examples.

### Signal 2: Stylometric Heuristics

The second signal uses measurable properties of the text:

- Type-token ratio / vocabulary diversity
- Sentence length variance
- Punctuation density
- AI-like phrase count

This signal also returns a score from `0` to `1`:

- `0` means structurally human-like
- `1` means structurally AI-like

**Why I chose it:** Stylometric features capture structural patterns that are different from the LLM's semantic judgment. For example, AI-generated writing can be unusually uniform, generic, and phrase-heavy.

**What it misses:** Stylometric rules can misread poems, formal essays, short texts, repetitive creative writing, or writing from non-native English speakers. These cases may have low sentence variance or repeated phrasing for valid human reasons.

---

## Confidence Scoring

Each signal produces an AI-likelihood score. The final combined score is calculated as:

```text
combined_score = (0.60 * llm_score) + (0.40 * stylometric_score)
```

The LLM signal gets slightly more weight because it captures broader semantic and stylistic context. The stylometric signal still has significant weight because it gives an independent structural check.

Final thresholds:

| Combined Score Range | Attribution |
|---|---|
| `0.70–1.00` | `likely_ai` |
| `0.26–0.69` | `uncertain` |
| `0.00–0.25` | `likely_human` |

I used a wide uncertainty band because false positives can harm human creators. If the system is not confident enough, it should avoid making a strong attribution claim and instead display an uncertain label.

For `likely_ai` and `likely_human` labels, confidence means confidence in that attribution. For `uncertain` labels, confidence means confidence that the system should remain cautious because the evidence is mixed or not strong enough for a high-confidence attribution.

---

## Example Submissions and Scores

### High-confidence human example

Input summary: Casual personal restaurant review.

Result:

```json
{
  "attribution": "likely_human",
  "confidence": 0.812,
  "combined_score": 0.188,
  "llm_score": 0.2,
  "stylometric_score": 0.17
}
```

The model identified informal language, personal opinions, and conversational tone. The stylometric signal also found high vocabulary diversity and high sentence length variance, which lowered the AI-likelihood score.

### Uncertain example

Input summary: Personal reflection about productivity apps.

Result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.784,
  "combined_score": 0.284,
  "llm_score": 0.2,
  "stylometric_score": 0.41
}
```

The LLM saw human-like personal reflection, but the stylometric signal found more uniform sentence structure and punctuation patterns. Since the combined score was above the high-confidence human threshold but below the likely-AI threshold, the system chose the cautious uncertain label.

### High-confidence AI example

Input summary: Highly generic AI-style paragraph with repeated phrases such as “it is important to note,” “rapidly evolving digital landscape,” “transformative paradigm shift,” and “responsible deployment.”

Result:

```json
{
  "attribution": "likely_ai",
  "confidence": 0.772,
  "combined_score": 0.772,
  "llm_score": 0.9,
  "stylometric_score": 0.58
}
```

Both signals leaned AI. The LLM identified overly formal and generic language, and the stylometric signal detected repeated AI-like phrases and low sentence length variance.

---

## Transparency Labels

The exact transparency label text is shown below.

| Case | Exact Label Text |
|---|---|
| High-confidence AI | "This content appears likely to be AI-generated. Our system found multiple signals associated with AI-written text, but this decision may be appealed by the creator." |
| High-confidence human | "This content appears likely to be human-written. Our system found stronger signals of original human authorship, though automated detection is not perfect." |
| Uncertain | "We could not confidently determine whether this content was human-written or AI-generated. This label is intentionally cautious because automated detection can be wrong." |

These labels are written for non-technical readers. They avoid claiming certainty and make clear that automated detection can be wrong.

---

## Appeals Workflow

Creators can appeal a classification by submitting a `content_id` and `creator_reasoning` to the `/appeal` endpoint.

When an appeal is received, the system:

1. Looks up the original decision using the `content_id`.
2. Updates the content status to `under_review`.
3. Stores the creator's appeal reasoning.
4. Writes an appeal event to the audit log.
5. Returns a confirmation response.

Automated re-classification is not required. In a real platform, this appeal would be routed to a human reviewer.

A human reviewer would be able to see:

- Content ID
- Creator ID
- Original attribution
- Original confidence score
- Individual signal scores
- Creator appeal reasoning
- Current status

Example appeal log entry:

```json
{
  "event_type": "appeal",
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_id": "clean-human-1",
  "status": "under_review",
  "original_attribution": "likely_human",
  "original_confidence": 0.812,
  "appeal_reasoning": "I wrote this myself. I am appealing because the system may have interpreted my formal wording or repeated phrasing as AI-generated."
}
```

---

## Rate Limiting

The `/submit` endpoint is rate-limited using Flask-Limiter.

Chosen limit:

```text
10 per minute; 100 per day
```

Reasoning:

A normal creator on a writing platform is unlikely to submit more than ten pieces of content in a single minute. The `10 per minute` limit allows normal testing and real user behavior while blocking automated flooding. The `100 per day` limit provides a broader daily abuse control without being too restrictive for active users.

Rate limit test command:

```powershell
for ($i = 1; $i -le 12; $i++) {
  try {
    $body = @{
      text = "This is a test submission for rate limit testing purposes only."
      creator_id = "ratelimit-test"
    } | ConvertTo-Json

    Invoke-WebRequest `
      -Uri "http://127.0.0.1:5000/submit" `
      -Method POST `
      -ContentType "application/json" `
      -Body $body | Select-Object -ExpandProperty StatusCode
  }
  catch {
    $_.Exception.Response.StatusCode.value__
  }
}
```

Expected output:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

---

## Audit Log Sample

The audit log is structured JSON and records classification and appeal events. Each classification entry includes timestamp, content ID, creator ID, attribution result, confidence score, transparency label, individual signal scores, combined score, and status.

Example entries from `GET /log`:

```json
{
  "event_type": "classification",
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_id": "clean-human-1",
  "attribution": "likely_human",
  "confidence": 0.812,
  "signals": {
    "combined_score": 0.188,
    "llm": {
      "score": 0.2,
      "reasoning": "The text features informal language, personal opinions, and a conversational tone, which are characteristic of human-written reviews."
    },
    "stylometric": {
      "score": 0.17
    }
  },
  "status": "classified"
}
```

```json
{
  "event_type": "classification",
  "content_id": "948f8f32-676d-442b-9beb-5f1d9de59459",
  "creator_id": "clean-uncertain-1",
  "attribution": "uncertain",
  "confidence": 0.784,
  "signals": {
    "combined_score": 0.284,
    "llm": {
      "score": 0.2,
      "reasoning": "The text features a personal anecdote, nuanced reflection, and a relatable conclusion, which are characteristic of human writing."
    },
    "stylometric": {
      "score": 0.41
    }
  },
  "status": "classified"
}
```

```json
{
  "event_type": "classification",
  "content_id": "8463fab9-f056-4496-8da0-8fa9ab2d38ed",
  "creator_id": "clean-ai-1",
  "attribution": "likely_ai",
  "confidence": 0.772,
  "signals": {
    "combined_score": 0.772,
    "llm": {
      "score": 0.9,
      "reasoning": "The text features overly formal and generic language, lacks personal touch, and includes repetitive phrases, which are common characteristics of AI-generated content."
    },
    "stylometric": {
      "score": 0.58
    }
  },
  "status": "classified"
}
```

```json
{
  "event_type": "appeal",
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_id": "clean-human-1",
  "status": "under_review",
  "original_attribution": "likely_human",
  "original_confidence": 0.812,
  "appeal_reasoning": "I wrote this myself. I am appealing because the system may have interpreted my formal wording or repeated phrasing as AI-generated."
}
```

---

## Known Limitations

This system should not be treated as a perfect AI detector. AI detection is inherently uncertain, and this project focuses on designing a cautious safety layer rather than claiming perfect accuracy.

Specific limitations:

1. **Formal human writing may be misclassified.** Academic or professional writing can contain polished structure, technical vocabulary, and low emotional detail. These patterns may look AI-like to both the LLM and stylometric signal.

2. **Creative repetition may be misread.** Poems, song lyrics, speeches, or intentionally repetitive creative writing may trigger the stylometric signal because repetition and low sentence variance are treated as AI-like features.

3. **Short text is difficult to classify.** Very short submissions do not provide enough material for reliable sentence variance, vocabulary diversity, or semantic analysis.

4. **Non-native English writing may be unfairly flagged.** Writers who use formal phrasing or repeated sentence structures may receive a higher AI-likelihood score even when the work is original.

Because of these limitations, the system uses a wide uncertainty band and includes an appeals workflow.

---

## Spec Reflection

One way the spec helped guide the implementation was by forcing the system design before coding. Writing the thresholds, label text, and appeal flow in `planning.md` made the implementation clearer because each endpoint had a specific contract to satisfy.

One way the implementation diverged from the original plan was the threshold tuning. I initially used a narrower uncertainty range, but after testing, some borderline human-like examples were being labeled too confidently. I changed the final thresholds to:

```text
combined_score >= 0.70 → likely_ai
combined_score <= 0.25 → likely_human
0.26–0.69 → uncertain
```

This made the system more cautious and better aligned with the project goal of avoiding harmful false positives against human creators.

---

## AI Usage

I used AI assistance during development, but I reviewed and adjusted the generated output before using it.

### Instance 1: Flask API structure

I asked AI to help design the Flask API structure for the required endpoints: `/health`, `/submit`, `/appeal`, and `/log`. The generated structure helped me organize the project, but I revised the endpoint names, response fields, and audit log fields to match my assignment spec.

### Instance 2: Detection and scoring logic

I used AI assistance to draft the stylometric heuristic functions and confidence scoring logic. I then adjusted the thresholds manually after testing because some examples were too confidently classified. The final uncertainty band was changed to make the system more cautious.

### Instance 3: Documentation support

I used AI assistance to organize the README sections and make sure the documentation included the required assignment evidence, including transparency labels, rate limiting, audit log examples, known limitations, and spec reflection.

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd ai201-project4-provenance-guard
```

### 2. Create and activate a virtual environment

Mac/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

```text
GROQ_API_KEY=your_key_here
```

The `.env` file should not be committed to GitHub.

### 5. Run the app

```bash
python app.py
```

The API will run at:

```text
http://127.0.0.1:5000
```

---

## Example PowerShell Test Commands

### Health check

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method GET
```

### Submit content

```powershell
$body = @{
  text = "Example text to classify."
  creator_id = "test-user"
} | ConvertTo-Json

$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/submit" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$response | ConvertTo-Json -Depth 10
```

### Submit appeal

```powershell
$appealBody = @{
  content_id = "PASTE_CONTENT_ID_HERE"
  creator_reasoning = "I wrote this myself and would like this classification reviewed."
} | ConvertTo-Json

$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/appeal" `
  -Method POST `
  -ContentType "application/json" `
  -Body $appealBody

$response | ConvertTo-Json -Depth 10
```

### View audit log

```powershell
$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/log" `
  -Method GET

$response | ConvertTo-Json -Depth 10
```

# Example Submission Outputs
{
  "attribution": "uncertain",
  "confidence": 0.784,
  "content_id": "948f8f32-676d-442b-9beb-5f1d9de59459",
  "creator_id": "clean-uncertain-1",
  "label": "We could not confidently determine whether this content was human-written or AI-generated. This label is intentionally cautious because automated detection can be wrong.",
  "signals": {
    "combined_score": 0.284,
    "llm": {
      "reasoning": "The text features a personal anecdote, nuanced reflection, and a relatable conclusion, which are characteristic of human writing.",
      "score": 0.2
    },
    "stylometric": {
      "metrics": {
        "ai_phrase_hits": 0,
        "phrase_score": 0.0,
        "punctuation_density": 0.068,
        "punctuation_score": 0.6,
        "sentence_length_variance": 6.889,
        "type_token_ratio": 0.847,
        "variance_score": 0.8,
        "vocab_score": 0.2
      },
      "score": 0.41
    }
  },
  "status": "classified",
  "text_length": 350
}

<!-- for likely_ai -->
{
  "attribution": "likely_ai",
  "confidence": 0.772,
  "content_id": "8463fab9-f056-4496-8da0-8fa9ab2d38ed",
  "creator_id": "clean-ai-1",
  "label": "This content appears likely to be AI-generated. Our system found multiple signals associated with AI-written text, but this decision may be appealed by the creator.",
  "signals": {
    "combined_score": 0.772,
    "llm": {
      "reasoning": "The text features overly formal and generic language, lacks personal touch, and includes repetitive phrases, which are common characteristics of AI-generated content.",
      "score": 0.9
    },
    "stylometric": {
      "metrics": {
        "ai_phrase_hits": 9,
        "phrase_score": 1.0,
        "punctuation_density": 0.109,
        "punctuation_score": 0.3,
        "sentence_length_variance": 6.96,
        "type_token_ratio": 0.837,
        "variance_score": 0.8,
        "vocab_score": 0.2
      },
      "score": 0.58
    }
  },
  "status": "classified",
  "text_length": 715
}

<!-- for likey_human -->
{
  "attribution": "likely_human",
  "confidence": 0.812,
  "content_id": "562a2319-b756-42d4-8aa9-e47803867f31",
  "creator_id": "clean-human-1",
  "label": "This content appears likely to be human-written. Our system found stronger signals of original human authorship, though automated detection is not perfect.",
  "signals": {
    "combined_score": 0.188,
    "llm": {
      "reasoning": "The text features informal language, personal opinions, and a conversational tone, which are characteristic of human-written reviews. The use of colloquial expressions and emotional responses also suggest a human author.",
      "score": 0.2
    },
    "stylometric": {
      "metrics": {
        "ai_phrase_hits": 0,
        "phrase_score": 0.0,
        "punctuation_density": 0.018,
        "punctuation_score": 0.3,
        "sentence_length_variance": 45.2,
        "type_token_ratio": 0.875,
        "variance_score": 0.2,
        "vocab_score": 0.2
      },
      "score": 0.17
    }
  },
  "status": "classified",
  "text_length": 293
}