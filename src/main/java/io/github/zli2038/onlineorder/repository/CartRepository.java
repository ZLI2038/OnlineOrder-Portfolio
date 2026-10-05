package io.github.zli2038.onlineorder.repository;

import io.github.zli2038.onlineorder.entity.CartEntity;
import org.springframework.data.jdbc.repository.query.Modifying;
import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.ListCrudRepository;
import java.math.BigDecimal;

public interface CartRepository extends ListCrudRepository<CartEntity, Long> {

    CartEntity getByCustomerId(Long customerId);

    @Query("SELECT * FROM carts WHERE customer_id = :customerId FOR UPDATE")
    CartEntity getByCustomerIdForUpdate(Long customerId);

    @Modifying
    @Query("UPDATE carts SET total_price = :totalPrice WHERE id = :cartId")
    void updateTotalPrice(Long cartId, BigDecimal totalPrice);
}
