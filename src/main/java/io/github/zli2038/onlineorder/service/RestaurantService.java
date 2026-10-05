package io.github.zli2038.onlineorder.service;

import io.github.zli2038.onlineorder.entity.MenuItemEntity;
import io.github.zli2038.onlineorder.entity.RestaurantEntity;
import io.github.zli2038.onlineorder.model.MenuItemDto;
import io.github.zli2038.onlineorder.model.RestaurantDto;
import io.github.zli2038.onlineorder.repository.MenuItemRepository;
import io.github.zli2038.onlineorder.repository.RestaurantRepository;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.context.annotation.Bean;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.JdbcUserDetailsManager;
import org.springframework.security.provisioning.UserDetailsManager;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class RestaurantService {

    private final MenuItemRepository menuItemRepository;
    private final RestaurantRepository restaurantRepository;

    public RestaurantService(
            RestaurantRepository restaurantRepository,
            MenuItemRepository menuItemRepository) {
        this.restaurantRepository = restaurantRepository;
        this.menuItemRepository = menuItemRepository;
    }

    @Cacheable("restaurants")
    public List<RestaurantDto> getRestaurants() {
        List<RestaurantEntity> restaurantEntities = restaurantRepository.findAll();
        List<MenuItemEntity> menuItemEntities = menuItemRepository.findAll();
        Map<Long, List<MenuItemDto>> groupedMenuItems = new HashMap<>();
        for (MenuItemEntity menuItemEntity : menuItemEntities) {
            List<MenuItemDto> group = groupedMenuItems.computeIfAbsent(menuItemEntity.restaurantId(), k -> new ArrayList<>());
            MenuItemDto menuItemDto = new MenuItemDto(menuItemEntity);
            group.add(menuItemDto);
        }
        List<RestaurantDto> results = new ArrayList<>();
        for (RestaurantEntity restaurantEntity : restaurantEntities) {
            RestaurantDto restaurantDto = new RestaurantDto(restaurantEntity, groupedMenuItems.get(restaurantEntity.id()));
            results.add(restaurantDto);
        }
        return results;
    }
}
