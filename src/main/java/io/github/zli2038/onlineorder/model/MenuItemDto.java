package io.github.zli2038.onlineorder.model;

import java.math.BigDecimal;
import io.github.zli2038.onlineorder.entity.MenuItemEntity;

public record MenuItemDto(
        Long id,
        String name,
        String description,
        BigDecimal price,
        String imageUrl
) {
    public MenuItemDto(MenuItemEntity entity) {
        this(entity.id(), entity.name(), entity.description(), entity.price(), entity.imageUrl());
    }
}
