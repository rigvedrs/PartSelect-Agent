import { useState, useCallback } from "react";
import { getCart, removeCartItem } from "../lib/api";

export function useCart(sessionId) {
  const [cart, setCart] = useState({ items: [], total: 0, count: 0 });

  const refreshCart = useCallback(async () => {
    if (!sessionId) return;
    const data = await getCart(sessionId);
    setCart(data);
  }, [sessionId]);

  const removeItem = useCallback(async (psNumber) => {
    if (!sessionId) return;
    const data = await removeCartItem(sessionId, psNumber);
    setCart(data);
  }, [sessionId]);

  return { cart, setCart, refreshCart, removeItem };
}
