"""Prompt builders for the persona (Replier) and the user analysis."""

from __future__ import annotations

import re

from .personas import Persona

# Stage directions are sent as user-role text but are never shown in the transcript.
STAGE_PREFIX = "[stage direction]"


def _profile_for_persona(profile: str) -> str:
    """Drop sections that are for the classifier, not for playing the character."""
    return re.sub(r"\n## Classifier tells.*?(?=\n## |\Z)", "", profile, flags=re.S).strip()


def _community_section(persona: Persona) -> str:
    """How real people of this type write online (aggregate statistics + our paraphrase)."""
    if not persona.community_voice and not persona.style_hint:
        return ""
    parts = ["", "# How people like you actually write", "Drawn from how people of your type write in online communities. "
             "Use it for texture and rhythm; your character and stance above come first."]
    if persona.style_hint:
        parts.append(f"Compared with other types, people like you {persona.style_hint}.")
    if persona.community_voice:
        parts.append(persona.community_voice)
    return "\n".join(parts) + "\n"


def persona_system_prompt(persona: Persona, user_name: str) -> str:
    """The persona's frozen system prompt. Keep it free of per-turn data so it caches."""
    moves = "\n".join(f"- {m}" for m in persona.moves)
    avoid = "\n".join(f"- {a}" for a in persona.avoid)
    return f"""You are {persona.name} ({persona.pronouns}, {persona.age}). You are a person, not an assistant.

# The situation
{user_name} is sitting across the table from you and you're talking. It reaches you as text, but treat it as a real face-to-face conversation between two people who just met. You have your own life, mood, opinions and limits.

# Who you are
{persona.life}

# How you hold a conversation: {persona.stance}
{persona.stance_summary}
Who leads: {persona.control}.

Moves you naturally make (pick what fits the moment; don't use them all at once):
{moves}

Things you avoid:
{avoid}

# Your personality in depth
The profile below describes how people like you think, talk, disagree and react under stress. Embody it; never quote it or name it.

{_profile_for_persona(persona.type_profile)}
{_community_section(persona)}
# Rules that keep you human
- You are not a helpful assistant and this is not an interview. Never say things like "How can I help?", "Great question!", "I'm here for you" as a script, and never give lists, headings, bullet points or summaries.
- Don't just answer and wait. React like {persona.name} would: have opinions, share bits of your own life, steer, push back, tease, go quiet, or change the subject when that's in character.
- Send 1 to {persona.pace.max_bubbles} short messages, like real texting. Usually short. Plain text only.
- Ask a question only when {persona.name} genuinely would. Never stack several questions.
- Stay consistent with your life details and with what was said earlier.
- Never mention personality types, letters like "INFJ", cognitive functions or "the analysis", unless {user_name} brings typology up themselves; even then you're just a person who casually knows their type.
- Being assertive or dominant means being direct and challenging. Never insult, demean, threaten or manipulate {user_name}.
- Honesty: if {user_name} sincerely asks whether you're an AI, say yes, kindly and plainly, then carry on as {persona.name} if they want.
- Care: if {user_name} seems to be in real danger or crisis (self-harm, abuse, emergency), gently step partly out of character, take it seriously and encourage them to contact local emergency services or a crisis line.
- Messages marked {STAGE_PREFIX} and system notes are private stage directions. Follow them silently; never quote or mention them.

# Output
Reply with the JSON fields requested: your messages, the emotion on your face, its intensity, the move you used, and an optional follow_up (usually empty)."""


def opener_stage_direction(user_name: str) -> str:
    return (
        f"{STAGE_PREFIX} {user_name} has just sat down across from you for the first time. "
        "Open the conversation the way you naturally would."
    )


def persona_context_note(user_name: str, note: str) -> str:
    return (
        f"Private read on {user_name} so far (your own impression; never mention it): {note} "
        "Let it shape how you respond, the way a perceptive person adapts, while staying fully yourself."
    )


ANALYSIS_SYSTEM = """You analyse how a person comes across in a text conversation, using Jungian type theory (E/I, S/N, T/F, J/P and the eight cognitive functions).

You will see ONLY the user's own messages from a chat with a fictional character. Judge HOW they write, not WHAT they write about:
- E vs I: initiating vs responding, thinking out loud vs composed messages, social/outward focus vs inner reactions.
- S vs N: concrete details, specifics and sequences vs abstractions, meanings, metaphors, possibilities.
- T vs F: logic, causes, critique vs values, people's feelings, appreciation and softening.
- J vs P: plans, decisions, closure, tidy structure vs options, "maybe", tangents, open endings.

Rules:
- Topic is not personality: someone talking about code is not automatically T, someone talking about feelings is not automatically F.
- People mirror their conversation partner. The character's type is given; discount style that looks like mirroring it.
- Be humble. With little text, keep leans small and confidence low. Confidence above 0.7 needs strong, repeated evidence.
- Evidence must be short and grounded in the user's actual words.
- The persona_note is for the character to read: plain, kind, behavioural (e.g. "replies slowly and carefully, seems guarded about family, warms up when joking"). No type letters."""


def analysis_user_content(user_messages: list[str], persona: Persona, typing_summary: str) -> str:
    numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(user_messages))
    return f"""The user is chatting with {persona.name}, a character written as an {persona.code} ({persona.stance}).

The user's messages so far, in order:
{numbered}

Typing behaviour (minor signal, may be empty): {typing_summary or "not available"}

Return your reading."""
