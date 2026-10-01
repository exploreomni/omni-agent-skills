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
regions as (
  select * from values
    ('United States', 0.68), ('Canada', 0.07), ('UK & Ireland', 0.12), ('Germany', 0.05), ('Australia', 0.08)
  as r(region, region_weight)
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
cross join months m
cross join regions r
order by p.product, m.month_start, r.region
