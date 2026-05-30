from app.agent.guardrails import is_in_scope

def test_appliance_query_passes():
    assert is_in_scope("my ice maker is not working") is True

def test_part_number_passes():
    assert is_in_scope("install PS11752778") is True

def test_pasta_recipe_blocked():
    assert is_in_scope("what is a good pasta recipe?") is False

def test_weather_blocked():
    assert is_in_scope("what is the weather today?") is False

def test_borderline_with_appliance_word_passes():
    assert is_in_scope("refrigerator not cooling, need a part") is True

def test_empty_string_passes():
    assert is_in_scope("") is True
