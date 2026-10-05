-- Synthetic benchmark only. Run exclusively in the isolated benchmark container.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE TABLE customers (
  id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE,
  password TEXT NOT NULL, first_name TEXT, last_name TEXT
);
CREATE TABLE carts (
  id SERIAL PRIMARY KEY, customer_id INTEGER UNIQUE NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  total_price NUMERIC NOT NULL
);
CREATE TABLE restaurants (
  id SERIAL PRIMARY KEY, name TEXT NOT NULL, address TEXT, image_url TEXT, phone TEXT
);
CREATE TABLE menu_items (
  id SERIAL PRIMARY KEY, restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  name TEXT NOT NULL, price NUMERIC NOT NULL, description TEXT, image_url TEXT
);
CREATE TABLE order_items (
  id SERIAL PRIMARY KEY, menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
  cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE, price NUMERIC NOT NULL, quantity INTEGER NOT NULL
);
CREATE TABLE authorities (
  id SERIAL PRIMARY KEY, email TEXT NOT NULL REFERENCES customers(email) ON DELETE CASCADE, authority TEXT NOT NULL
);
INSERT INTO restaurants(id,name,address,image_url,phone)
SELECT i, 'Restaurant '||i, i||' Benchmark Street', '/images/restaurant-'||i||'.jpg', '555-0100'
FROM generate_series(1,100) i;
INSERT INTO menu_items(id,restaurant_id,name,price,description,image_url)
SELECT i, ((i-1)/100)+1, 'Menu item '||i, 10.25,
       repeat('Synthetic menu description for reproducible transfer measurements. ',3),
       '/images/menu-'||i||'.jpg'
FROM generate_series(1,10000) i;
INSERT INTO customers(id,email,password,first_name,last_name)
SELECT i, 'bench'||i||'@example.test', '{noop}benchmark-pass', 'Benchmark', i::text
FROM generate_series(1,10100) i;
INSERT INTO authorities(email,authority)
SELECT email,'ROLE_USER' FROM customers;
INSERT INTO carts(id,customer_id,total_price)
SELECT id,id,CASE WHEN id<=100 THEN 512.50 ELSE 102.50 END FROM customers;
INSERT INTO order_items(menu_item_id,cart_id,price,quantity)
SELECT ((c-1)%100)*100+j,c,10.25,1
FROM generate_series(1,10100) c
CROSS JOIN LATERAL generate_series(1,CASE WHEN c<=100 THEN 50 ELSE 10 END) j;
SELECT setval(pg_get_serial_sequence('customers','id'),max(id)) FROM customers;
SELECT setval(pg_get_serial_sequence('restaurants','id'),max(id)) FROM restaurants;
SELECT setval(pg_get_serial_sequence('menu_items','id'),max(id)) FROM menu_items;
SELECT setval(pg_get_serial_sequence('carts','id'),max(id)) FROM carts;
ANALYZE;
