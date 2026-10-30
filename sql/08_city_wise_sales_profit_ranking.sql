
-- QUICKKART: TOP 5 CITIES BY REVENUE

WITH city_sales AS (

    SELECT
        st.store_city,
        s.sale_id,
        s.units,

        s.units * p.product_price
            AS revenue,

        s.units * (
            p.product_price - p.product_cost
        ) AS gross_profit

    FROM historical.sales s

    INNER JOIN historical.products p
        ON s.product_id = p.product_id

    INNER JOIN historical.stores st
        ON s.store_id = st.store_id
),

city_kpis AS (

    SELECT
        store_city,

        COUNT(*) AS total_transactions,

        SUM(units) AS total_units,

        SUM(revenue) AS total_revenue,

        SUM(gross_profit) AS total_gross_profit

    FROM city_sales

    GROUP BY store_city
),

city_ranking AS (

    SELECT
        *,

        RANK() OVER (
            ORDER BY total_revenue DESC
        ) AS revenue_rank

    FROM city_kpis
)

SELECT
    revenue_rank,
    store_city,
    total_transactions,
    total_units,

    ROUND(
        total_revenue, 2
    ) AS total_revenue,

    ROUND(
        total_gross_profit, 2
    ) AS total_gross_profit,

    ROUND(
        100.0 * total_gross_profit
        / NULLIF(total_revenue, 0), 2
    ) AS gross_profit_margin_pct

FROM city_ranking

ORDER BY revenue_rank, store_city

LIMIT 5;
