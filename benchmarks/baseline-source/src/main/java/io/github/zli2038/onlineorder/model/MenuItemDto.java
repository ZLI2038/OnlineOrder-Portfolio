package io.github.zli2038.onlineorder.model;

import io.github.zli2038.onlineorder.entity.MenuItemEntity;

public record MenuItemDto(
        Long id,
        String name,
        String description,
        Double price,
        String imageUrl
) {
    public MenuItemDto(MenuItemEntity entity) {
        this(entity.id(), entity.name(), entity.description(), entity.price(), entity.imageUrl());
    }
}
