from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CartItem:
    ps_number: str
    name: str
    price: float
    quantity: int = 1

    @property
    def total(self) -> float:
        return round(self.price * self.quantity, 2)

    def to_dict(self) -> dict:
        return {
            "ps_number": self.ps_number,
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "total": self.total,
        }


@dataclass
class AgentState:
    session_id: str
    messages: list[Any] = field(default_factory=list)
    cart: dict[str, CartItem] = field(default_factory=dict)
    appliance_model: str | None = None
