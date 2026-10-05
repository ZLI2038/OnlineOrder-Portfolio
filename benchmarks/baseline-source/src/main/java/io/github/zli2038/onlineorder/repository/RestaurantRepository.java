package io.github.zli2038.onlineorder.repository;

import io.github.zli2038.onlineorder.entity.RestaurantEntity;
import org.springframework.data.repository.ListCrudRepository;

public interface RestaurantRepository extends ListCrudRepository<RestaurantEntity, Long> {
}
