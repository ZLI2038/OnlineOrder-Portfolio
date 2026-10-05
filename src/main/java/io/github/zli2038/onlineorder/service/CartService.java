package io.github.zli2038.onlineorder.service;

import io.github.zli2038.onlineorder.entity.CartEntity;
import io.github.zli2038.onlineorder.entity.MenuItemEntity;
import io.github.zli2038.onlineorder.entity.OrderItemEntity;
import io.github.zli2038.onlineorder.model.CartDto;
import io.github.zli2038.onlineorder.model.OrderItemDto;
import io.github.zli2038.onlineorder.repository.CartRepository;
import io.github.zli2038.onlineorder.repository.MenuItemRepository;
import io.github.zli2038.onlineorder.repository.OrderItemRepository;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.math.BigDecimal;

@Service
public class CartService {

    private final CartRepository cartRepository;
    private final MenuItemRepository menuItemRepository;
    private final OrderItemRepository orderItemRepository;

    public CartService(
            CartRepository cartRepository,
            MenuItemRepository menuItemRepository,
            OrderItemRepository orderItemRepository) {
        this.cartRepository = cartRepository;
        this.menuItemRepository = menuItemRepository;
        this.orderItemRepository = orderItemRepository;
    }

    @CacheEvict(cacheNames = "cart", key = "#customerId")
    @Transactional
    public void addMenuItemToCart(long customerId, long menuItemId) {
        CartEntity cart = cartRepository.getByCustomerIdForUpdate(customerId);
        MenuItemEntity menuItem = menuItemRepository.findById(menuItemId).get();
        OrderItemEntity orderItem = orderItemRepository.findByCartIdAndMenuItemId(cart.id(), menuItem.id());

        Long orderItemId;
        int quantity;

        if (orderItem == null) {
            orderItemId = null;
            quantity = 1;
        } else {
            orderItemId = orderItem.id();
            quantity = orderItem.quantity() + 1;
        }
        OrderItemEntity newOrderItem = new OrderItemEntity(orderItemId, menuItemId, cart.id(), menuItem.price(), quantity);
        orderItemRepository.save(newOrderItem);
        cartRepository.updateTotalPrice(cart.id(), cart.totalPrice().add(menuItem.price()));
    }

    @Cacheable("cart")
    public CartDto getCart(Long customerId) {
        CartEntity cart = cartRepository.getByCustomerId(customerId);
        List<OrderItemEntity> orderItems = orderItemRepository.getAllByCartId(cart.id());
        List<OrderItemDto> orderItemDtos = getOrderItemDtos(orderItems);
        return new CartDto(cart, orderItemDtos);
    }

    @CacheEvict(cacheNames = "cart", key = "#customerId")
    @Transactional
    public void clearCart(Long customerId) {
        CartEntity cartEntity = cartRepository.getByCustomerIdForUpdate(customerId);
        orderItemRepository.deleteByCartId(cartEntity.id());
        cartRepository.updateTotalPrice(cartEntity.id(), BigDecimal.ZERO);
    }

    private List<OrderItemDto> getOrderItemDtos(List<OrderItemEntity> orderItems) {
        if (orderItems.isEmpty()) {
            return List.of();
        }
        List<Long> menuItemIds = orderItems.stream().map(OrderItemEntity::menuItemId).distinct().toList();
        Map<Long, MenuItemEntity> menuItems = menuItemRepository.findAllById(menuItemIds).stream()
                .collect(Collectors.toMap(MenuItemEntity::id, Function.identity()));
        return orderItems.stream()
                .map(item -> new OrderItemDto(item, menuItems.get(item.menuItemId())))
                .toList();
    }
}
