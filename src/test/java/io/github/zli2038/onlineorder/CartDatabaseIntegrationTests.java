package io.github.zli2038.onlineorder;

import io.github.zli2038.onlineorder.service.CartService;
import io.github.zli2038.onlineorder.service.CustomerService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.cache.CacheManager;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named = "ONLINEORDER_TEST_DB_URL", matches = ".+/onlineorder_integration")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.sql.init.mode=never", "onlineorder.seed-demo=false", "spring.cache.type=caffeine",
        "spring.datasource.hikari.maximum-pool-size=32", "logging.level.root=WARN",
        "logging.level.org.springframework.jdbc.core=WARN",
        "logging.level.org.apache.coyote.http11.Http11InputBuffer=WARN"
})
class CartDatabaseIntegrationTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired CartService carts;
    @Autowired CustomerService customers;
    @Autowired CacheManager caches;

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> System.getenv("ONLINEORDER_TEST_DB_URL"));
        registry.add("spring.datasource.username", () -> "postgres");
        registry.add("spring.datasource.password", () -> "benchmark-local-only");
    }

    @BeforeEach
    void reset() {
        assertEquals("onlineorder_integration", jdbc.queryForObject("SELECT current_database()", String.class));
        jdbc.execute("DROP TRIGGER IF EXISTS fail_cart_update ON carts");
        jdbc.execute("DROP TRIGGER IF EXISTS fail_cart_insert ON carts");
        jdbc.execute("DROP FUNCTION IF EXISTS benchmark_failure()");
        jdbc.execute("TRUNCATE customers,authorities,carts,restaurants,menu_items,order_items RESTART IDENTITY CASCADE");
        jdbc.update("INSERT INTO customers(id,email,password) VALUES (1,'one@example.test','{noop}password'),(2,'two@example.test','{noop}password')");
        jdbc.update("INSERT INTO carts(id,customer_id,total_price) VALUES (1,1,0),(2,2,0)");
        jdbc.execute("SELECT setval(pg_get_serial_sequence('customers','id'),2)");
        jdbc.execute("SELECT setval(pg_get_serial_sequence('carts','id'),2)");
        jdbc.update("INSERT INTO restaurants(id,name) VALUES (1,'Test restaurant')");
        jdbc.update("INSERT INTO menu_items(id,restaurant_id,name,price) VALUES (1,1,'First',0.10),(2,1,'Second',0.20)");
        for (String name : caches.getCacheNames()) {
            caches.getCache(name).clear();
        }
    }

    private void assertCart(long id, int quantity, String total) {
        assertEquals(quantity, jdbc.queryForObject("SELECT COALESCE(sum(quantity),0) FROM order_items WHERE cart_id=?", Integer.class, id));
        BigDecimal actual = jdbc.queryForObject("SELECT total_price FROM carts WHERE id=?", BigDecimal.class, id);
        BigDecimal sum = jdbc.queryForObject("SELECT COALESCE(sum(price*quantity),0) FROM order_items WHERE cart_id=?", BigDecimal.class, id);
        assertEquals(0, new BigDecimal(total).compareTo(actual));
        assertEquals(0, actual.compareTo(sum));
    }

    private void failOnCart(String event, String name) {
        jdbc.execute("CREATE FUNCTION benchmark_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected benchmark failure'; END $$");
        jdbc.execute("CREATE TRIGGER " + name + " BEFORE " + event + " ON carts FOR EACH ROW EXECUTE FUNCTION benchmark_failure()");
    }

    @Test void insertsAnItemAndItsTotal() {
        carts.addMenuItemToCart(1,1);
        assertCart(1,1,"0.10");
    }

    @Test void incrementsAnExistingItemWithoutDuplicatingRows() {
        carts.addMenuItemToCart(1,1);
        carts.addMenuItemToCart(1,1);
        assertCart(1,2,"0.20");
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM order_items",Integer.class));
    }

    @Test void keepsDecimalAmountsExactAcrossRepeatedAdditions() {
        for (int i=0;i<100;i++) carts.addMenuItemToCart(1,1);
        assertCart(1,100,"10.00");
    }

    @Test void clearsItemsAndTotalTogether() {
        carts.addMenuItemToCart(1,1);
        carts.addMenuItemToCart(1,2);
        carts.clearCart(1L);
        assertCart(1,0,"0");
    }

    @Test void rollsBackItemInsertionIfUpdatingTotalFails() {
        failOnCart("UPDATE","fail_cart_update");
        assertThrows(RuntimeException.class, () -> carts.addMenuItemToCart(1,1));
        assertCart(1,0,"0");
    }

    @Test void rollsBackItemIncrementIfUpdatingTotalFails() {
        carts.addMenuItemToCart(1,1);
        failOnCart("UPDATE","fail_cart_update");
        assertThrows(RuntimeException.class, () -> carts.addMenuItemToCart(1,1));
        assertCart(1,1,"0.10");
    }

    @Test void rollsBackClearingItemsIfResettingTotalFails() {
        carts.addMenuItemToCart(1,1);
        failOnCart("UPDATE","fail_cart_update");
        assertThrows(RuntimeException.class, () -> carts.clearCart(1L));
        assertCart(1,1,"0.10");
    }

    @Test void rollsBackCredentialsAndAuthoritiesIfCreatingCartFails() {
        failOnCart("INSERT","fail_cart_insert");
        assertThrows(RuntimeException.class, () -> customers.signUp("new@example.test","password","First","Last"));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM customers WHERE email='new@example.test'",Integer.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM authorities WHERE email='new@example.test'",Integer.class));
    }

    @Test void successfulSignupCreatesCredentialsAuthorityAndOneCart() {
        customers.signUp("NEW@example.test","password","First","Last");
        Long id=jdbc.queryForObject("SELECT id FROM customers WHERE email='new@example.test'",Long.class);
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM carts WHERE customer_id=?",Integer.class,id));
        assertEquals("ROLE_USER",jdbc.queryForObject("SELECT authority FROM authorities WHERE email='new@example.test'",String.class));
    }

    @Test void mutationInvalidatesOnlyTheAffectedCustomersCache() {
        carts.getCart(1L);
        carts.getCart(2L);
        assertNotNull(caches.getCache("cart").get(1L));
        carts.addMenuItemToCart(1,1);
        assertNull(caches.getCache("cart").get(1L));
        assertNotNull(caches.getCache("cart").get(2L));
        assertEquals(1,carts.getCart(1L).orderItems().size());
        carts.clearCart(1L);
        assertTrue(carts.getCart(1L).orderItems().isEmpty());
    }

    @ParameterizedTest
    @ValueSource(ints={8,16,32})
    void concurrentAdditionsToTheSameItemPreserveAllWrites(int workers) throws Exception {
        int iterations=10;
        try (var pool=Executors.newFixedThreadPool(workers)) {
            var ready=new CountDownLatch(workers);
            var start=new CountDownLatch(1);
            List<Future<?>> tasks=new ArrayList<>();
            for(int i=0;i<workers;i++) tasks.add(pool.submit(() -> {
                ready.countDown();
                try { assertTrue(start.await(10,TimeUnit.SECONDS)); }
                catch(InterruptedException e) { throw new RuntimeException(e); }
                for(int j=0;j<iterations;j++) carts.addMenuItemToCart(1,1);
            }));
            assertTrue(ready.await(10,TimeUnit.SECONDS));
            start.countDown();
            for(Future<?> task:tasks) task.get(60,TimeUnit.SECONDS);
        }
        assertCart(1,workers*iterations,BigDecimal.valueOf(workers).toPlainString());
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM order_items",Integer.class));
    }

    @Test void concurrentAdditionsToDifferentItemsPreserveTotal() throws Exception {
        try(var pool=Executors.newFixedThreadPool(32)) {
            var ready=new CountDownLatch(32);
            var start=new CountDownLatch(1);
            List<Future<?>> tasks=new ArrayList<>();
            for(int i=0;i<32;i++) {
                long item=i%2+1;
                tasks.add(pool.submit(() -> {
                    ready.countDown();
                    try { assertTrue(start.await(10,TimeUnit.SECONDS)); }
                    catch(InterruptedException e) { throw new RuntimeException(e); }
                    for(int j=0;j<10;j++) carts.addMenuItemToCart(1,item);
                }));
            }
            assertTrue(ready.await(10,TimeUnit.SECONDS));
            start.countDown();
            for(Future<?> task:tasks) task.get(60,TimeUnit.SECONDS);
        }
        assertCart(1,320,"48.00");
        assertEquals(2,jdbc.queryForObject("SELECT count(*) FROM order_items",Integer.class));
    }
}
