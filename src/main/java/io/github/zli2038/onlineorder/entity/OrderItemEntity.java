package io.github.zli2038.onlineorder.entity;

import java.math.BigDecimal;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

@Table("order_items")
public record OrderItemEntity(
        @Id Long id,
        Long menuItemId,
        Long cartId,
        BigDecimal price,
        Integer quantity
) {
}
