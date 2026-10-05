# OnlineOrder — Full-Stack Online Food Ordering System

A full-stack Java and React application for browsing restaurant menus, managing a shopping cart, and completing a checkout flow. The backend includes relational data modeling, session-based authentication, batched database reads, caching, and transactional cart updates.

## Features

- Register and sign in with Spring Security and database-backed user accounts.
- Browse restaurants and menus in a React / Ant Design interface.
- Add menu items to a user-specific cart and calculate totals with `BigDecimal`.
- Reuse menu data in the frontend and cache cart reads with Caffeine.
- Protect cart writes with transactions, PostgreSQL row locks, and a unique cart/item index.
- Checkout clears the current cart. Payment processing and persistent order history are not implemented.

## Technology

| Area | Stack |
| --- | --- |
| Backend | Java 21, Spring Boot, Spring Security, Spring Data JDBC |
| Database and cache | PostgreSQL, Caffeine |
| Frontend | React, Ant Design |
| Build and local environment | Gradle Wrapper, npm, Docker Compose |
| Testing | JUnit, Mockito, PostgreSQL integration tests, React/Jest comparison test |

The database has six tables: `customers`, `authorities`, `restaurants`, `menu_items`, `carts`, and `order_items`. In this implementation, `order_items` stores cart lines.

## Run locally

Requirements: Java 21, Node.js/npm, and Docker with Docker Compose. Gradle is provided by the wrapper.

### 1. Start the local database

From the repository root:

```sh
docker compose up -d db
```

The included Compose file creates an `onlineorder` database on port `5432`. The `postgres` / `secret` credentials are local development defaults.

### 2. Start the backend

For a **new, disposable local database**, initialize the schema and sample restaurant/menu data:

```sh
INIT_DB=always ./gradlew bootRun
```

The API listens on `http://localhost:8080`. The initialization script drops and recreates the application's tables. After the initial setup, stop the backend and use the following command on subsequent starts to retain data:

```sh
INIT_DB=never ./gradlew bootRun
```

Always set `INIT_DB` explicitly: the current application configuration defaults to `always`. Database connection settings can be overridden with `DATABASE_URL` (hostname), `DATABASE_PORT`, `DATABASE_USERNAME`, and `DATABASE_PASSWORD`. The database name is `onlineorder`.

### 3. Start the frontend

In another terminal:

```sh
cd doordash-app
npm ci
npm start
```

Open `http://localhost:3000`, register an account, and sign in. The frontend development server forwards API requests to port `8080`.

### 4. Stop the database

```sh
docker compose down
```

The named database volume remains available for the next run.

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/signup` | Register a customer and provision a cart |
| POST | `/login` | Start an authenticated session |
| POST | `/logout` | End the session |
| GET | `/restaurants/menu` | Retrieve restaurants with their menus |
| GET | `/restaurant/{restaurantId}/menu` | Retrieve one restaurant's menu |
| GET | `/cart` | Retrieve the authenticated customer's cart |
| POST | `/cart` | Add a menu item to the cart |
| POST | `/cart/checkout` | Clear the authenticated customer's cart |

## Tests and measurements

Run the cart service unit tests:

```sh
./gradlew test --tests 'io.github.zli2038.onlineorder.CartServiceTests'
```

Database integration tests require the separate benchmark database and are skipped unless `ONLINEORDER_TEST_DB_URL` is supplied. Follow the [benchmark reproduction guide](benchmarks/README.md) to provision it, run all 14 database scenarios, and repeat the HTTP and frontend measurements.

Recorded results from **local synthetic data**, with the workload and limitations documented in the [measurement report](benchmarks/REPORT.md):

| Change | Before | After | Measurement scope |
| --- | ---: | ---: | --- |
| Batched cart reads: SQL calls per request | 53 | 4 | 50 cart lines, caching disabled |
| Batched cart reads: HTTP P95 | 158.3 ms | 23.7 ms | 20 concurrent clients; median of three round P95s |
| Warm cart cache: SQL calls per request | 4 | 1 | Same optimized application, 100 synthetic users |
| Warm cart cache: HTTP P95 | 23.7 ms | 11.4 ms | 20 concurrent clients, prewarmed read-only workload |
| Indexed cart/item lookup: median SQL execution time | 3.13 ms | 0.016 ms | 105,000 cart lines, 90 samples per configuration |
| Menu requests while browsing 10 restaurants | 11 | 1 | Actual React components calling local HTTP APIs |

The recorded run validated 9,000 measured HTTP requests, four unit tests, 14 PostgreSQL integration test cases, and one frontend comparison test. Raw HTTP samples, query plans, and measurement scripts are included under `benchmarks/`. Machine-specific JUnit logs and personal documents are excluded from version control.

## Project layout

```text
src/main/java/       Backend controllers, services, repositories, and models
src/main/resources/ Application settings, schema, sample data, and indexes
src/test/java/       Unit tests and PostgreSQL integration tests
doordash-app/        React frontend
benchmarks/         Baseline source, synthetic fixtures, scripts, and results
```

This is a local learning/demo application. The current authentication setup disables CSRF protection and the frontend login helper puts credentials in the request URL; these need changes before an internet-facing deployment. Publishing this source repository does not deploy a running service.
