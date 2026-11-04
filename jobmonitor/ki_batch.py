"""Message Batches API von Anthropic: viele Anfragen gesammelt zum halben Preis, Ergebnis meist innerhalb einer Stunde.

Genutzt für das Nachbewerten gespeicherter Stellen (nachbewertung.py), das nicht eilt: Ein Lauf schickt den Stapel ab,
ein späterer Lauf holt die Ergebnisse. Nur mit Claude (andere Anbieter: einzeln wie bisher).
"""
from __future__ import annotations

import logging

from . import llm

log = logging.getLogger(__name__)


def erstellen(model: str, anfragen: dict[str, str], system: str, max_tokens: int = 8000) -> str | None:
    """`anfragen`: custom_id → Prompt. Gibt die Batch-ID zurück oder None (dann einzeln weiter)."""
    try:
        import anthropic
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        client = llm._client(None)
        system_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        batch = client.messages.batches.create(requests=[
            Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
                model=model, max_tokens=max_tokens, output_config={"effort": "low"}, system=system_block,
                messages=[{"role": "user", "content": prompt}]))
            for cid, prompt in anfragen.items()])
    except anthropic.AnthropicError as exc:
        log.warning("KI-Stapel nicht angelegt (%s) – einzeln weiter", str(exc)[:200])
        return None
    except Exception as exc:   # z. B. Anmeldung in GitHub Actions nicht möglich
        log.warning("KI-Stapel nicht angelegt (%s)", type(exc).__name__)
        return None
    log.info("KI-Stapel mit %d Anfragen angelegt (%s)", len(anfragen), batch.id)
    return batch.id


def abholen(batch_id: str) -> tuple[str, dict[str, str]]:
    """(Status, custom_id → Antworttext). Status „ended“, wenn fertig; „in_progress“ solange er läuft; „fehler“,
    wenn der Stapel nicht abrufbar ist (dann neu anlegen)."""
    try:
        client = llm._client(None)
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status != "ended":
            return "in_progress", {}
        out = {}
        for r in client.messages.batches.results(batch_id):
            if r.result.type != "succeeded":
                continue
            msg = r.result.message
            if getattr(msg, "usage", None) is not None:
                llm._zaehlen(msg.usage)
            if msg.stop_reason in ("refusal", "max_tokens"):
                continue
            out[r.custom_id] = "".join(b.text for b in msg.content if b.type == "text").strip()
        log.info("KI-Stapel %s: %d Ergebnisse", batch_id, len(out))
        return "ended", out
    except Exception as exc:
        log.warning("KI-Stapel %s nicht abrufbar (%s)", batch_id, str(exc)[:200])
        return "fehler", {}
