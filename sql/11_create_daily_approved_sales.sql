
CREATE TABLE IF NOT EXISTS daily.approved_sales (
    report_date DATE NOT NULL,
    sale_id BIGINT NOT NULL,
    sale_date DATE NOT NULL,
    store_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    units INTEGER NOT NULL CHECK (units > 0),

    loaded_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT pk_daily_approved_sales
    PRIMARY KEY (report_date, sale_id)
);
