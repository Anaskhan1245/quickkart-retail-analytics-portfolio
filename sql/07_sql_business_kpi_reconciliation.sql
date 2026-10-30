
-- QUICKKART: SQL BUSINESS KPI RECONCILIATION

WITH sales_enriched AS (
    SELECT
        s.sale_id,
        s.date,
        s.store_id,
        s.product_id,
        s.units,

        p.product_name,
        p.product_price,
        p.product_cost,

        st.store_city,
        p.product_id AS matched_product_id,
        st.store_id AS matched_store_id

    FROM historical.sales s

    LEFT JOIN historical.products p
        ON s.product_id = p.product_id

    LEFT JOIN historical.stores st
        ON s.store_id = st.store_id
)

SELECT
    COUNT(*) AS total_transactions,

    SUM(units) AS total_units_sold,

    ROUND(
        SUM(units * product_price), 2
    ) AS total_revenue,

    ROUND(
        SUM(units * product_cost), 2
    ) AS total_cost,

    ROUND(
        SUM(units * (product_price - product_cost)), 2
    ) AS total_gross_profit,

    ROUND(
        100.0 * SUM(
            units * (product_price - product_cost)
        ) / NULLIF(
            SUM(units * product_price), 0
        ), 2
    ) AS gross_profit_margin_pct,

    COUNT(*) FILTER (
        WHERE matched_product_id IS NULL
    ) AS unknown_product_records,

    COUNT(*) FILTER (
        WHERE matched_store_id IS NULL
    ) AS unknown_store_records

FROM sales_enriched;
