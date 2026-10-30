
-- QUICKKART: IQR AND OUTLIER ANALYSIS

WITH transaction_values AS (

    SELECT
        s.sale_id,
        s.units * p.product_price AS sale_amount

    FROM historical.sales s

    JOIN historical.products p
        ON s.product_id = p.product_id
),

quartiles AS (

    SELECT
        PERCENTILE_CONT(0.25)
        WITHIN GROUP (ORDER BY sale_amount)::NUMERIC
            AS q1,

        PERCENTILE_CONT(0.75)
        WITHIN GROUP (ORDER BY sale_amount)::NUMERIC
            AS q3

    FROM transaction_values
),

bounds AS (

    SELECT
        q1,
        q3,
        q3 - q1 AS iqr,

        q1 - 1.5 * (q3 - q1) AS lower_limit,

        q3 + 1.5 * (q3 - q1) AS upper_limit

    FROM quartiles
),

outlier_counts AS (

    SELECT
        COUNT(*) AS total_records,

        COUNT(*) FILTER (
            WHERE t.sale_amount > b.upper_limit
        ) AS high_outliers,

        COUNT(*) FILTER (
            WHERE t.sale_amount < b.lower_limit
        ) AS low_outliers

    FROM transaction_values t
    CROSS JOIN bounds b
)

SELECT
    ROUND(b.q1, 2) AS q1,

    ROUND(b.q3, 2) AS q3,

    ROUND(b.iqr, 2) AS iqr,

    ROUND(b.lower_limit, 2) AS lower_limit,

    ROUND(b.upper_limit, 2) AS upper_limit,

    c.total_records,

    c.high_outliers,

    c.low_outliers,

    c.high_outliers + c.low_outliers
        AS total_outliers,

    ROUND(
        100.0 * (
            c.high_outliers + c.low_outliers
        ) / NULLIF(c.total_records, 0),
        2
    ) AS outlier_percentage

FROM bounds b
CROSS JOIN outlier_counts c;
