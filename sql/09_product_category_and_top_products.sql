
-- QUICKKART: CATEGORY-WISE SALES AND PROFIT

WITH category_kpis AS (

    SELECT
        p.product_category,

        COUNT(*) AS total_transactions,

        SUM(s.units) AS total_units,

        SUM(
            s.units * p.product_price
        ) AS total_revenue,

        SUM(
            s.units *
            (p.product_price - p.product_cost)
        ) AS total_gross_profit

    FROM historical.sales s

    INNER JOIN historical.products p
        ON s.product_id = p.product_id

    GROUP BY p.product_category
)

SELECT
    DENSE_RANK() OVER (
        ORDER BY total_revenue DESC
    ) AS revenue_rank,

    product_category,
    total_transactions,
    total_units,

    ROUND(total_revenue, 2)
        AS total_revenue,

    ROUND(total_gross_profit, 2)
        AS total_gross_profit,

    ROUND(
        100.0 * total_gross_profit
        / NULLIF(total_revenue, 0),
        2
    ) AS gross_profit_margin_pct

FROM category_kpis

ORDER BY revenue_rank, product_category;




-- QUICKKART: TOP 10 PRODUCTS BY UNITS SOLD

WITH product_kpis AS (

    SELECT
        p.product_id,
        p.product_name,
        p.product_category,

        SUM(s.units) AS units_sold,

        SUM(
            s.units * p.product_price
        ) AS total_revenue,

        SUM(
            s.units *
            (p.product_price - p.product_cost)
        ) AS total_gross_profit

    FROM historical.sales s

    INNER JOIN historical.products p
        ON s.product_id = p.product_id

    GROUP BY
        p.product_id,
        p.product_name,
        p.product_category
),

product_ranking AS (

    SELECT
        *,

        DENSE_RANK() OVER (
            ORDER BY units_sold DESC
        ) AS units_rank,

        DENSE_RANK() OVER (
            ORDER BY total_gross_profit DESC
        ) AS profit_rank

    FROM product_kpis
)

SELECT
    units_rank,
    profit_rank,
    product_name,
    product_category,
    units_sold,

    ROUND(total_revenue, 2)
        AS total_revenue,

    ROUND(total_gross_profit, 2)
        AS total_gross_profit

FROM product_ranking

ORDER BY units_rank, product_name

LIMIT 10;
