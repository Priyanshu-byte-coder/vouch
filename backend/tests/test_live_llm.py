import pytest

from app.llm import Usage, chat_json, current_usage

pytestmark = pytest.mark.live

REF = ("[12] Vaswani A., Shazeer N, Parmar N. et al., Attention is all you need, in: Adv. Neural Inf. "
       "Process. Syst. 30 (NIPS 2017), pp. 5998-6008. arXiv:1706.03762")


async def test_parse_reference_json():
    usage = Usage()
    token = current_usage.set(usage)
    try:
        out = await chat_json(
            "Extract bibliographic fields. Reply with ONLY a JSON object with keys: title, authors "
            "(list of 'Surname, Initials'), year (int), venue, arxiv_id.\n\nReference: " + REF, use_cache=False)
    finally:
        current_usage.reset(token)
    assert out["title"].lower() == "attention is all you need"
    assert out["year"] == 2017 and out["arxiv_id"] == "1706.03762"
    assert usage.calls == 1 and usage.tokens_out > 0 and usage.cost_usd > 0
    print(f"\nLLM usage: {usage}")
