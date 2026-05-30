from app.agent.state import AgentState, CartItem

def test_cart_item_total():
    item = CartItem(ps_number="PS123", name="Part", price=10.50, quantity=2)
    assert item.total == 21.00

def test_agent_state_defaults():
    state = AgentState(session_id="s1")
    assert state.cart == {}
    assert state.appliance_model is None
    assert state.messages == []
