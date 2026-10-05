# OnlineOrder reproducible measurements

The retained baseline (`baseline-source/`) is the initial implementation plus three prerequisites: entity imports in `OrderItemDto`, the authority-column typo, and an opt-in flag for `DevRunner`. The baseline's N+1 cart reads and frontend menu requests remain unchanged.

On 2026-10-04 the Java packages were renamed to `io.github.zli2038.onlineorder`. The rename changed identifiers only; identifiers inside recorded artifacts (`results/environment.json`, `results/implementation-changes.diff`) were updated to match, the frontend header title was renamed in both copies (display text only), and the recorded JAR hashes still refer to the builds that were measured.

All data are synthetic. Only the dedicated `onlineorder-resume-benchmark-db` container is used. Ports 15432 and 18080–18082 bind to loopback. The database uses temporary storage and is separate from the application's default database.

## Reproduce

Requirements: Java 21, Gradle 9.4.1 (or the wrapper), Node/npm, Python 3, and Docker. Run from the project root. Preserve `benchmarks/results` before rerunning, since the scripts replace result files.

1. Start and seed the dedicated database:

   ```sh
   docker compose -p onlineorder-resume-bench -f benchmarks/docker-compose.yml up -d
   python3 benchmarks/setup_database.py
   ```

2. Build both versions and run the database tests:

   ```sh
   sh ./gradlew --no-daemon -p benchmarks/baseline-source test bootJar
   ONLINEORDER_TEST_DB_URL=jdbc:postgresql://127.0.0.1:15432/onlineorder_integration sh ./gradlew --no-daemon test bootJar
   ```

3. Start services and run measurements. Do not run builds, tests, or other benchmarks concurrently with latency measurements:

   ```sh
   python3 benchmarks/manage_apps.py start
   python3 benchmarks/run_measurements.py all
   ```

4. Run the actual frontend components against the HTTP services and build the production frontend:

   ```sh
   npm --prefix doordash-app ci
   cd doordash-app
   CI=true ONLINEORDER_HTTP_BENCH=1 npm test -- --watchAll=false --runInBand
   npm run build
   ```

5. From the project root, stop only the benchmark processes and container:

   ```sh
   python3 benchmarks/manage_apps.py stop
   docker compose -p onlineorder-resume-bench -f benchmarks/docker-compose.yml down
   ```

## Measurement boundaries

- `GET /cart`: 100 authenticated synthetic users, 50 lines per cart, 20 concurrent clients, 1,000 measured requests per configuration per round, three rounds with rotated order. Each configuration gets 1,000 warmup requests and each round gets another 200 premeasurement requests. HTTP response bodies and cart contents are validated. The headline P95 is the median of three round P95s, not a confidence bound or a production SLA.
- All three app processes have the same 20-connection pool and JVM limits. Baseline and optimized databases both have the same indexes during cart benchmarking. The cache comparison uses the exact same optimized JAR, with caching disabled versus enabled. This is an already-warm, read-only cache workload; it is not a mixed read/write or cache-expiration test.
- The optimized version also uses BigDecimal for amounts; the retained baseline uses Double. The measured latency comparison therefore compares these two recorded versions, not an isolated microbenchmark of only the batch-fetch method.
- PostgreSQL `pg_stat_statements` supplies measured SQL calls. Customer lookup is included in endpoint counts: baseline 53, batched 4, cached 1. No-op test credentials are used only in synthetic seed data; authentication setup is excluded from timings.
- Index measurements use an independent database with 105,000 order-item rows and 10,000 menu-item rows. Three rounds, 30 samples per configuration per query per round, 10 warmup executions, alternating index state. `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON)` execution time excludes HTTP latency and planning time. PostgreSQL buffers are warm. The SQL query and all 540 plans are retained.
- Frontend measurements mount the actual original and optimized React components, substitute Ant Design's presentation controls, and call the real HTTP APIs. Both flows browse restaurants 1–10 and validate 100 rendered menu items after every selection. Figures count menu API calls and uncompressed JSON body bytes, excluding image requests, HTTP headers, login, browser rendering performance, and development StrictMode's extra mount cycle.
- Integration tests use real PostgreSQL, injected database-trigger failures, Spring transactions/cache proxies, and synchronized thread starts. The 14 cases include 8/16/32-worker same-item updates and a 32-worker mixed-item update. Each worker performs 10 additions. Tests verify quantities, duplicate-row counts, precise totals, rollback, signup provisioning, and per-user cache invalidation. They do not establish production-level availability or linearizable cached reads during overlapping writes.

## Changes outside the benchmark harness

- Batch menu lookup for nonempty carts; empty carts avoid an unnecessary menu query.
- Per-cart PostgreSQL row locks for additions and clearing, plus a unique `(cart_id, menu_item_id)` index.
- BigDecimal monetary values throughout persistence and DTOs.
- Index on `menu_items.restaurant_id`; the cart/menu composite index also supports cart-prefix lookups.
- React reuses menus already returned by `/restaurants/menu`. The first catalog payload is unchanged; fresh menu data is fetched when the component remounts. This optimization does not claim improved first-load transfer size.
- `OrderItemDto` imports, authentication SQL correction, and explicitly enabled demo seeding (`onlineorder.seed-demo=true`).
- `query-indexes.sql` is included for fresh schema initialization. For an existing database, apply that file explicitly after resolving any existing duplicate cart/menu pairs; it does not delete data automatically.

Application database initialization still follows the original `INIT_DB` setting. The benchmark launches explicitly force initialization off and manage only their dedicated fixtures.
