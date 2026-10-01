-- Query tab name: peloton_monthly_sales
-- Snowflake. Deterministic synthetic monthly sales by product and region (24 months). Replace with the orders/subscriptions tables.
with months as (
  select seq4() as idx,
         dateadd('month', -seq4(), date_trunc('month', current_date())) as month_start
  from table(generator(rowcount => 24))
),
products as (
  select * from values
    ('Bike',   'Bike',  1445, 5200),
    ('Bike+',  'Bike',  2495, 3100),
    ('Tread',  'Tread', 2995, 1900),
    ('Tread+', 'Tread', 5995,  450),
    ('Row',    'Row',   2995,  700),
    ('Guide',  'Guide',  295, 1600),
    ('App',    'App',      0, 9000)
  as v(product, family, unit_price_usd, baseline_monthly_units)
),
-- regional mix differs by product so the "Where it sells" view has something to say
product_regions as (
  select * from values
    ('Bike','United States',0.70),('Bike','Canada',0.07),('Bike','UK & Ireland',0.11),('Bike','Germany',0.05),('Bike','Australia',0.07),
    ('Bike+','United States',0.66),('Bike+','Canada',0.07),('Bike+','UK & Ireland',0.13),('Bike+','Germany',0.06),('Bike+','Australia',0.08),
    ('Tread','United States',0.74),('Tread','Canada',0.06),('Tread','UK & Ireland',0.10),('Tread','Germany',0.04),('Tread','Australia',0.06),
    ('Tread+','United States',0.82),('Tread+','Canada',0.06),('Tread+','UK & Ireland',0.07),('Tread+','Germany',0.02),('Tread+','Australia',0.03),
    ('Row','United States',0.78),('Row','Canada',0.07),('Row','UK & Ireland',0.09),('Row','Germany',0.02),('Row','Australia',0.04),
    ('Guide','United States',0.62),('Guide','Canada',0.08),('Guide','UK & Ireland',0.14),('Guide','Germany',0.07),('Guide','Australia',0.09),
    ('App','United States',0.55),('App','Canada',0.08),('App','UK & Ireland',0.17),('App','Germany',0.09),('App','Australia',0.11)
  as r(product, region, region_weight)
)
select
  p.product,
  p.family,
  m.month_start as month,
  r.region,
  round(p.baseline_monthly_units * r.region_weight
        * power(1.012, 23 - m.idx)
        * (1 + 0.22 * cos(2 * pi() * (month(m.month_start) - 1) / 12))
        * (0.9 + (abs(hash(p.product, m.month_start, r.region)) % 100) / 500.0)) as units_sold,
  units_sold * p.unit_price_usd as hardware_revenue_usd,
  round(units_sold * iff(p.product = 'App', 0.55, 0.92)) as new_memberships,
  round(units_sold * (0.03 + (abs(hash(r.region, p.product, m.idx)) % 100) / 2500.0)) as returns
from products p
join product_regions r on r.product = p.product
cross join months m
order by p.product, m.month_start, r.region
