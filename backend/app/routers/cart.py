from fastapi import APIRouter
from app.services.cart_service import get_cart, remove_from_cart

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("/{session_id}")
def read_cart(session_id: str):
    return get_cart(session_id)


@router.delete("/{session_id}/item/{ps_number}")
def delete_cart_item(session_id: str, ps_number: str):
    return remove_from_cart(session_id, ps_number)
