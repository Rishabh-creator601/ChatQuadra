"""Engine tests. No API calls: everything runs in mock mode."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from chatquadra.config import load_settings
from chatquadra.inference import UserReader, typing_nudges
from chatquadra.llm import LLM
from chatquadra.personas import load_personas
from chatquadra.prompts import persona_system_prompt
from chatquadra.schemas import AxisReading, ReplierTurn, TextAnalysis, TypingStats
from chatquadra.session import ChatSession, RateLimited
from chatquadra.timing import absorb_latency, plan_delivery
from chatquadra.typedata import TYPES


def mock_settings(**overrides):
    return replace(load_settings(), mock=True, **overrides)


def test_all_sixteen_personas_load_with_sample_lines():
    personas = load_personas()
    assert set(personas) == set(TYPES)
    for p in personas.values():
        assert p.name and p.moves and p.sample_lines, p.code
        assert 1 <= p.pace.max_bubbles <= 4


def test_persona_prompt_hides_classifier_section_and_names_stance():
    infj = load_personas()["INFJ"]
    prompt = persona_system_prompt(infj, "Sam")
    assert "Healer-Counsellor" in prompt
    assert "Classifier tells" not in prompt
    assert "Sam is sitting across the table" in prompt


def test_delivery_plan_shape_and_latency_absorption():
    pace = load_personas()["ENTJ"].pace
    turn = ReplierTurn(messages=["ok.", "what's the goal?"], emotion="confident", intensity="high", move="x", follow_up="well?")
    plan = plan_delivery(turn, pace, "I don't know what to do", rng=random.Random(1))
    assert plan[0]["kind"] == "read"
    messages = [s["text"] for s in plan if s["kind"] == "message"]
    assert messages == ["ok.", "what's the goal?", "well?"]
    assert all(s["ms"] >= 0 for s in plan)
    adjusted = absorb_latency(plan, 10_000)
    assert adjusted[0]["ms"] == 0 and plan[0]["ms"] > 0


def _analysis(e_i=0.6, s_n=0.5, t_f=0.4, j_p=-0.2, conf=0.7, cues=("Ni",)):
    # lean: -1 = first letter (E, S, T, J), +1 = second letter (I, N, F, P)
    def ax(v):
        return AxisReading(lean=v, confidence=conf, evidence=[f"lean {v}"])
    return TextAnalysis(
        e_i=ax(e_i), s_n=ax(s_n), t_f=ax(t_f), j_p=ax(j_p),
        function_cues=list(cues), impression="You come across as reflective.", persona_note="calm",
    )


def test_reader_gates_until_enough_words():
    reader = UserReader(min_words=150)
    reader.apply(_analysis(), words=40, messages=3)
    result = reader.result([], 0.0, pending=False, next_update_in=3)
    assert not result.ready and result.top_types == []


def test_reader_top_two_are_ranked_probabilities():
    reader = UserReader(min_words=50)
    reader.apply(_analysis(), words=400, messages=6)
    result = reader.result([], 0.0, pending=False, next_update_in=3)
    assert result.ready
    a, b = result.top_types
    assert a.confidence >= b.confidence > 0
    assert a.confidence < 0.9  # humble by design
    assert a.type == "INFJ"  # I, N, F, J with an Ni cue
    assert len(result.axes) == 4


def test_typing_nudges_are_small_and_capped():
    stats = [TypingStats(reply_latency_ms=1000, pause_before_send_ms=100, keystrokes=100, backspaces=40, hesitations=3)] * 5
    nudges, notes = typing_nudges(stats, burst_ratio=0.9)
    assert all(abs(v) <= 0.1 for v in nudges.values())
    assert notes


def test_mock_session_flow_runs_analysis_on_cadence():
    s = mock_settings(analysis_every=3, min_words=20, pace=0.1)
    session = ChatSession("ENTJ", "Sam", typing_consent=True, settings=s, llm=LLM(s), seed=7)
    opener = session.open()
    assert opener["turn"]["messages"] and opener["plan"]
    lines = [
        "I think I want to quit my job but I'm not sure, maybe I should plan it first",
        "I feel like my manager doesn't care about people at all and it hurts",
        "what if I started my own thing? imagine the freedom, honestly",
    ]
    started = [session.send(t, TypingStats(reply_latency_ms=9000))["analysis_started"] for t in lines]
    assert started == [False, False, True]
    session.wait_for_analysis()
    result = session.inference()
    assert result.analyses_run == 1 and result.ready
    assert len(result.top_types) == 2
    assert result.next_update_in == 3
    # transcript holds both speakers; the stage direction is never shown
    assert {m["speaker"] for m in session.transcript} == {"user", "replier"}
    assert not any("stage direction" in m["text"] for m in session.transcript)


def test_rate_limit():
    s = mock_settings(max_messages_per_hour=2)
    session = ChatSession("ISTP", "Sam", settings=s, llm=LLM(s), seed=1)
    session.send("hi")
    session.send("you there?")
    with pytest.raises(RateLimited):
        session.send("hello??")


def test_style_model_reads_writing_style_and_blends():
    from chatquadra.style_model import blend, load_model, style_reading

    if load_model() is None:
        pytest.skip("style model not trained")
    warm = ["omg I love this so much!!! 😭💛", "honestly I feel so happy for you, it means a lot to me!",
            "aww thank you, my heart is full haha"]
    cool = ["The logic doesn't hold. The data shows a different pattern.", "Technically the system is efficient, "
            "but the plan needs a clear goal and a deadline.", "Objectively, the analysis is incomplete."]
    warm_read, _ = style_reading(warm)
    cool_read, _ = style_reading(cool)
    assert warm_read.t_f.lean > cool_read.t_f.lean  # F-ish writing reads more F than T-ish writing
    assert 0 <= warm_read.t_f.confidence <= 1
    merged = blend(_analysis(), warm_read)
    assert merged.t_f.confidence == _analysis().t_f.confidence


def test_community_voice_reaches_persona_prompt_when_present():
    from chatquadra.personas import _community_voice

    voice = _community_voice("INFJ")
    if not voice:
        pytest.skip("community profile not written")
    prompt = persona_system_prompt(load_personas()["INFJ"], "Sam")
    assert "How people like you actually write" in prompt
    assert voice.splitlines()[0] in prompt


def test_known_type_skips_analysis_and_reports_it():
    s = mock_settings(analysis_every=3, min_words=20)
    session = ChatSession("ENTJ", "Sam", settings=s, llm=LLM(s), seed=3, known_type="infp")
    session.open()
    started = [session.send(t)["analysis_started"] for t in ["one two three", "four five six", "seven eight nine"]]
    assert started == [False, False, False]
    result = session.inference()
    assert result.self_reported and result.ready
    assert [c.type for c in result.top_types] == ["INFP"]
    with pytest.raises(ValueError):
        ChatSession("ENTJ", "Sam", settings=s, llm=LLM(s), known_type="XYZW")


def test_failed_reply_is_rolled_back_cleanly():
    from chatquadra.llm import LLMError

    s = mock_settings(analysis_every=3, max_messages_per_hour=5)
    session = ChatSession("ISTJ", "Sam", settings=s, llm=LLM(s), seed=2)
    session.open()
    session.send("first message here")
    before = (list(session.user_texts), len(session.transcript), len(session.api_messages), len(session._recent_sends))

    class Down:
        mock = False

        def structured(self, **_):
            raise LLMError("service down")

    real = session.llm
    session.llm = Down()
    with pytest.raises(LLMError):
        session.send("this one fails")
    after = (list(session.user_texts), len(session.transcript), len(session.api_messages), len(session._recent_sends))
    assert after == before  # no ghost message, no extra history, no rate slot used

    session.llm = real
    session.send("this one fails")  # the retry is clean: one user turn, then the reply
    roles = [m["role"] for m in session.api_messages]
    assert roles[-2:] == ["user", "assistant"] and session.user_texts.count("this one fails") == 1
