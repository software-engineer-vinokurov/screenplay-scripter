def test_all_dsl_importable():
    from scripter import click, right_click, drag, scroll, key, type_text, sleep
    assert all(callable(f) for f in [click, right_click, drag, scroll, key, type_text, sleep])


def test_star_import():
    import scripter
    for name in ['click', 'right_click', 'drag', 'scroll', 'key', 'type_text', 'sleep']:
        assert name in scripter.__all__
