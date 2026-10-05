package io.github.zli2038.onlineorder.model;

import java.math.BigDecimal;
import io.github.zli2038.onlineorder.entity.MenuItemEntity;
import io.github.zli2038.onlineorder.entity.OrderItemEntity;

public record OrderItemDto(
        Long orderItemId,
        Long menuItemId,
        Long restaurantId,
        BigDecimal price,
        Integer quantity,
        String menuItemName,
        String menuItemDescription,
        String menuItemImageUrl
) {
    public OrderItemDto(OrderItemEntity orderItemEntity, MenuItemEntity menuItemEntity) {
        this(
                orderItemEntity.id(),
                orderItemEntity.menuItemId(),
                menuItemEntity.restaurantId(),
                orderItemEntity.price(),
                orderItemEntity.quantity(),
                menuItemEntity.name(),
                menuItemEntity.description(),
                menuItemEntity.imageUrl()
        );
    }
}
