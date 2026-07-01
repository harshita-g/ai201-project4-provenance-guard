import os
import json
import re
from groq import Groq


AI_PHRASES = [
    "it is important to note",
    "in today's world",
    "in conclusion",
    "furthermore",
    "moreover",
    "this highlights",
    "plays a crucial role",
    "transformative",
    "various sectors",
    "responsible deployment",
]


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def groq_signal(text):
    """
    Returns a score from 0 to 1.
    0 = strongly human-like
    1 = strongly AI-like
    """

    client = get_groq_client()

    if client is None:
        # Fallback so the project still runs locally without an API key.
        return {
            "score": 0.5,
            "reasoning": "Groq API key not found. Using neutral fallback score."
        }

    prompt = f"""
You are part of a content provenance system. Analyze the text and estimate whether it appears AI-generated or human-written.

Return ONLY valid JSON in this exact format:
{{
  "score": 0.0,
  "reasoning": "brief explanation"
}}

The score must be between 0 and 1:
- 0 means strongly human-written
- 0.5 means uncertain
- 1 means strongly AI-generated

Text:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You classify text provenance and return only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)

        score = float(parsed.get("score", 0.5))
        score = max(0.0, min(1.0, score))

        return {
            "score": score,
            "reasoning": parsed.get("reasoning", "No reasoning provided.")
        }

    except Exception as e:
        return {
            "score": 0.5,
            "reasoning": f"Groq signal failed, using neutral fallback. Error: {str(e)}"
        }


def split_sentences(text):
    sentences = re.split(r"[.!?]+", text)
    return [s.strip() for s in sentences if s.strip()]


def type_token_ratio(words):
    if not words:
        return 0
    return len(set(words)) / len(words)


def sentence_length_variance(sentences):
    if len(sentences) < 2:
        return 0

    lengths = [len(sentence.split()) for sentence in sentences]
    avg = sum(lengths) / len(lengths)
    variance = sum((length - avg) ** 2 for length in lengths) / len(lengths)

    return variance


def stylometric_signal(text):
    """
    Returns a score from 0 to 1.
    0 = structurally human-like
    1 = structurally AI-like
    """

    lower_text = text.lower()
    words = re.findall(r"\b\w+\b", lower_text)
    sentences = split_sentences(text)

    ttr = type_token_ratio(words)
    variance = sentence_length_variance(sentences)

    punctuation_count = sum(1 for char in text if char in ",;:!?")
    punctuation_density = punctuation_count / max(len(words), 1)

    ai_phrase_hits = sum(1 for phrase in AI_PHRASES if phrase in lower_text)

    # Lower vocabulary diversity can suggest generic or repetitive text.
    if ttr < 0.45:
        vocab_score = 0.8
    elif ttr < 0.65:
        vocab_score = 0.5
    else:
        vocab_score = 0.2

    # Very low sentence length variance can suggest uniform AI-style writing.
    if variance < 8:
        variance_score = 0.8
    elif variance < 25:
        variance_score = 0.5
    else:
        variance_score = 0.2

    # Many generic AI-like phrases increase the AI-likelihood score.
    phrase_score = min(ai_phrase_hits / 3, 1.0)

    # Extremely clean punctuation patterns can be AI-like, but this is weak.
    if 0.03 <= punctuation_density <= 0.09:
        punctuation_score = 0.6
    else:
        punctuation_score = 0.3

    heuristic_score = (
        0.35 * vocab_score +
        0.35 * variance_score +
        0.20 * phrase_score +
        0.10 * punctuation_score
    )

    return {
        "score": round(heuristic_score, 3),
        "metrics": {
            "type_token_ratio": round(ttr, 3),
            "sentence_length_variance": round(variance, 3),
            "punctuation_density": round(punctuation_density, 3),
            "ai_phrase_hits": ai_phrase_hits,
            "vocab_score": round(vocab_score, 3),
            "variance_score": round(variance_score, 3),
            "phrase_score": round(phrase_score, 3),
            "punctuation_score": round(punctuation_score, 3),
        }
    }


def generate_label(attribution, confidence):
    if attribution == "likely_ai":
        return (
            "This content appears likely to be AI-generated. "
            "Our system found multiple signals associated with AI-written text, "
            "but this decision may be appealed by the creator."
        )

    if attribution == "likely_human":
        return (
            "This content appears likely to be human-written. "
            "Our system found stronger signals of original human authorship, "
            "though automated detection is not perfect."
        )

    return (
        "We could not confidently determine whether this content was human-written "
        "or AI-generated. This label is intentionally cautious because automated "
        "detection can be wrong."
    )


def combine_scores(llm_score, heuristic_score):
    combined = (0.60 * llm_score) + (0.40 * heuristic_score)
    combined = round(combined, 3)

    if combined >= 0.70:
        attribution = "likely_ai"
        confidence = combined
    elif combined <= 0.25:
        attribution = "likely_human"
        confidence = round(1 - combined, 3)
    else:
        attribution = "uncertain"
        confidence = round(1 - abs(combined - 0.5), 3)

    label = generate_label(attribution, confidence)

    return {
        "combined_score": combined,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    }


def analyze_text(text):
    llm = groq_signal(text)
    heuristic = stylometric_signal(text)

    combined = combine_scores(
        llm_score=llm["score"],
        heuristic_score=heuristic["score"]
    )

    return {
        "attribution": combined["attribution"],
        "confidence": combined["confidence"],
        "label": combined["label"],
        "signals": {
            "llm": {
                "score": llm["score"],
                "reasoning": llm["reasoning"]
            },
            "stylometric": heuristic,
            "combined_score": combined["combined_score"]
        }
    }