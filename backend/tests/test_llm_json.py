import pytest

from app.llm import LLMJSONError, Usage, parse_json_loose


@pytest.mark.parametrize("reply, expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('```\n[1, 2]\n```', [1, 2]),
    ('Sure! Here is the JSON:\n{"title": "X", "year": 2017}\nHope this helps.', {"title": "X", "year": 2017}),
    ('[{"t": "a"}, {"t": "b"}] trailing words', [{"t": "a"}, {"t": "b"}]),
])
def test_parse_json_loose(reply, expected):
    assert parse_json_loose(reply) == expected


@pytest.mark.parametrize("reply", ["no json here", '{"a": 1', ""])
def test_parse_json_loose_rejects(reply):
    with pytest.raises(LLMJSONError):
        parse_json_loose(reply)


def test_usage_cost():
    u = Usage()
    u.add("m", 1_000_000, 1_000_000)
    assert u.calls == 1 and u.tokens_in == 1_000_000
    assert u.cost_usd == pytest.approx(0.55 + 2.75)
