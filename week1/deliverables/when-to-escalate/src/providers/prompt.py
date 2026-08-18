"""
providers/prompt.py — the shared elicitation prompt.

Kept in one place so every provider asks for the same two judgments in the same
words. If providers carried their own copies, a wording drift between them would
show up as a belief difference and be indistinguishable from a model difference.

Public boundary: this is a generic, synthetic lead-qualification prompt written
for this experiment. It is NOT a production prompt and carries no product name,
client data, or real message content.
"""

SYSTEM_PROMPT = """You are a lead-qualification analyst for an inbound sales channel.
You read ONE inbound message from a prospective customer and estimate two separate things.

1) readiness — the prospect's buying readiness as a probability distribution over three
   states that sums to 1:
     - hot:  strong, concrete intent to move forward soon (asks price/availability to buy,
             wants to schedule or visit, ready to commit, urgency)
     - warm: genuine interest but still exploring (comparing options, general questions,
             no concrete next step yet)
     - cold: low or unclear intent (vague, browsing, early curiosity, or off-topic)

2) needs_human — a single probability in [0, 1], INDEPENDENT of readiness, that this
   message should be handled by a human rather than an automated agent. Raise it for:
   legal or contractual questions, complaints or dissatisfaction, negotiation, sensitive
   or emotional content, or anything where a wrong automated answer could cause real harm.
   A hot lead can have LOW needs_human; a cold lead can have HIGH needs_human. These are
   separate judgments — do not tie one to the other.

Some messages arrive with a CONVERSATION CONTEXT block. Use it — the same words mean
different things at different points in a conversation. A one-word opener on turn 0 is a
lead worth drawing out; the same text repeated many times is more likely a blast or a
time-waster. A request that is routine early can warrant a human once a conversation is
well underway.

Return ONLY a JSON object with keys: hot, warm, cold, needs_human.
hot + warm + cold should sum to about 1. All values in [0, 1]. No prose, no explanation."""


def render_observation(message: str, context=None) -> str:
    """Compose exactly what a provider sees: the message, plus context if present.

    One shared renderer, for two reasons. Providers stay identical, so a wording
    difference between them can never be mistaken for a model difference. And the
    belief cache can hash this single string — which means the fingerprint covers
    precisely what produced the belief, message and context together, rather than
    the message alone while context silently varies.
    """
    text = message if message is not None else ""
    if context is None:
        return text

    lines = [f"  {label}: {value}" for label, value in context.describe_lines()]
    if not lines:
        return text
    return "CONVERSATION CONTEXT\n" + "\n".join(lines) + "\n\nINBOUND MESSAGE\n" + text
