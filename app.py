import uuid
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from detector import analyze_text
from storage import (
    save_content_decision,
    get_content_decision,
    update_content_with_appeal,
    write_audit_log,
    get_recent_logs,
)

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json() or {}

    text = data.get("text", "").strip()
    creator_id = data.get("creator_id", "").strip()

    if not text:
        return jsonify({"error": "text is required"}), 400

    if not creator_id:
        return jsonify({"error": "creator_id is required"}), 400

    content_id = str(uuid.uuid4())

    analysis = analyze_text(text)

    decision = {
        "content_id": content_id,
        "creator_id": creator_id,
        "text_length": len(text),
        "attribution": analysis["attribution"],
        "confidence": analysis["confidence"],
        "label": analysis["label"],
        "signals": analysis["signals"],
        "status": "classified",
    }

    save_content_decision(content_id, decision)

    write_audit_log({
        "event_type": "classification",
        **decision,
    })

    return jsonify(decision), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json() or {}

    content_id = data.get("content_id", "").strip()
    creator_reasoning = data.get("creator_reasoning", "").strip()

    if not content_id:
        return jsonify({"error": "content_id is required"}), 400

    if not creator_reasoning:
        return jsonify({"error": "creator_reasoning is required"}), 400

    original_decision = get_content_decision(content_id)

    if not original_decision:
        return jsonify({"error": "content_id not found"}), 404

    updated = update_content_with_appeal(content_id, creator_reasoning)

    write_audit_log({
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": updated["creator_id"],
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_attribution": updated["attribution"],
        "original_confidence": updated["confidence"],
        "signals": updated["signals"],
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received. This content is now under review.",
    }), 200


@app.route("/log", methods=["GET"])
def log():
    entries = get_recent_logs()
    return jsonify({"entries": entries}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Provenance Guard API is running",
        "endpoints": ["/health", "/submit", "/appeal", "/log"]
    }), 200


if __name__ == "__main__":
    app.run(debug=True)