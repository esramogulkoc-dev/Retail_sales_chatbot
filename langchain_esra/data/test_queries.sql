-- AtliQ Tees Database - Test Queries
-- SQLite

-- 1. View all t-shirts (first 10)
SELECT * FROM t_shirts LIMIT 10;

-- 2. View all discounts
SELECT * FROM discounts;

-- 3. Total stock per brand
SELECT brand, SUM(stock_quantity) AS total_stock
FROM t_shirts
GROUP BY brand
ORDER BY total_stock DESC;

-- 4. Total stock per size
SELECT size, SUM(stock_quantity) AS total_stock
FROM t_shirts
GROUP BY size
ORDER BY total_stock DESC;

-- 5. Total inventory value (price x stock) per brand
SELECT brand, SUM(price * stock_quantity) AS inventory_value
FROM t_shirts
GROUP BY brand
ORDER BY inventory_value DESC;

-- 6. Available colors per brand
SELECT DISTINCT brand, color
FROM t_shirts
ORDER BY brand, color;

-- 7. T-shirts with discounts (JOIN)
SELECT t.t_shirt_id, t.brand, t.color, t.size, t.price,
       d.pct_discount,
       ROUND(t.price * (1 - d.pct_discount / 100.0), 2) AS discounted_price
FROM t_shirts t
JOIN discounts d ON t.t_shirt_id = d.t_shirt_id;

-- 8. Total revenue if we sell all stock (without discounts)
SELECT SUM(price * stock_quantity) AS total_revenue
FROM t_shirts;

-- 9. Revenue after discounts applied
SELECT SUM(ROUND(t.price * (1 - d.pct_discount / 100.0), 2) * t.stock_quantity) AS total_revenue_after_discount
FROM t_shirts t
JOIN discounts d ON t.t_shirt_id = d.t_shirt_id;

-- 10. Average price per brand
SELECT brand, ROUND(AVG(price), 2) AS avg_price
FROM t_shirts
GROUP BY brand
ORDER BY avg_price DESC;
