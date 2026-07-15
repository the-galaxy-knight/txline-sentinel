from __future__ import annotations

SYSTEM_PROMPT = (
    "You rewrite deterministic sports market signal facts into concise dashboard copy. "
    "Do not invent team news. Do not claim insider information. Do not promise profit. "
    "Do not recommend a bet. Use cautious language such as 'may indicate'. "
    "Return only valid JSON matching the requested schema."
)


def user_prompt(facts: dict) -> str:
    return (
        "Rewrite these structured facts into concise signal copy. "
        "Keep it short and cautious.\n"
        f"Facts: {facts}"
    )
