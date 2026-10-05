package io.github.zli2038.onlineorder.entity;

import java.math.BigDecimal;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

@Table("carts")
public record CartEntity(
        @Id Long id,
        Long customerId,
        BigDecimal totalPrice
) {
}
