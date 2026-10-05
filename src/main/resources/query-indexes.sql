-- Applicable to an existing schema. Resolve any duplicate cart/menu pairs before migrating.
CREATE INDEX IF NOT EXISTS idx_menu_items_restaurant ON menu_items (restaurant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_order_items_cart_menu ON order_items (cart_id, menu_item_id);
