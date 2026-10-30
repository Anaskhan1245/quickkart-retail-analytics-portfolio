
-- QUICKKART: STORE-WISE INVENTORY RISK

SELECT
    st.store_id,
    st.store_name,
    st.store_city,

    COUNT(*) AS total_inventory_records,

    SUM(i.stock_on_hand)
        AS total_stock_units,

    COUNT(*) FILTER (
        WHERE i.stock_on_hand = 0
    ) AS zero_stock_products,

    COUNT(*) FILTER (
        WHERE i.stock_on_hand BETWEEN 1 AND 10
    ) AS low_stock_products,

    COUNT(*) FILTER (
        WHERE i.stock_on_hand > 10
    ) AS available_products,

    COUNT(*) FILTER (
        WHERE i.stock_on_hand < 0
           OR i.stock_on_hand IS NULL
    ) AS invalid_stock_records

FROM historical.inventory i

INNER JOIN historical.stores st
    ON i.store_id = st.store_id

GROUP BY
    st.store_id,
    st.store_name,
    st.store_city

ORDER BY
    zero_stock_products DESC,
    low_stock_products DESC,
    st.store_id;



-- QUICKKART: ZERO AND LOW STOCK PRODUCTS

SELECT
    st.store_name,
    st.store_city,

    p.product_name,
    p.product_category,

    i.stock_on_hand,

    CASE
        WHEN i.stock_on_hand = 0
            THEN 'ZERO STOCK'

        WHEN i.stock_on_hand BETWEEN 1 AND 10
            THEN 'LOW STOCK'

        ELSE 'AVAILABLE'
    END AS stock_status

FROM historical.inventory i

INNER JOIN historical.stores st
    ON i.store_id = st.store_id

INNER JOIN historical.products p
    ON i.product_id = p.product_id

WHERE i.stock_on_hand BETWEEN 0 AND 10

ORDER BY
    i.stock_on_hand ASC,
    st.store_name,
    p.product_name

LIMIT 20;
