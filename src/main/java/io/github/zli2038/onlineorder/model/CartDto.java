package io.github.zli2038.onlineorder.model;

import java.math.BigDecimal;
import io.github.zli2038.onlineorder.entity.CartEntity;

import java.util.List;

public record CartDto(
        Long id,
        BigDecimal totalPrice,
        List<OrderItemDto> orderItems
) {
    public CartDto(CartEntity entity, List<OrderItemDto> orderItems) {
        this(entity.id(), entity.totalPrice(), orderItems);
    }
}
