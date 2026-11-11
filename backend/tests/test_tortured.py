from app.pipeline.tortured import fingerprints, scan


def test_fingerprints_loaded():
    assert len(fingerprints()) >= 60


def test_counterfeit_consciousness_flagged():
    text = "In recent years, counterfeit\nconsciousness and profound learning have changed how bosom peril is detected."
    hits = scan(text)
    found = {h.expected for h in hits}
    assert {"artificial intelligence", "deep learning", "breast cancer"} <= found
    assert all("…" in h.snippet or h.snippet for h in hits)


def test_clean_text_not_flagged():
    text = ("Artificial intelligence and deep learning are used for breast cancer screening; "
            "a random forest and a support vector machine serve as baselines on big data.")
    assert scan(text) == []
