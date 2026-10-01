-- Query tab name: peloton_products
-- Snowflake. Indicative specs and US list prices for the prototype; replace with Peloton's catalog table.
select * from values
  ('Bike',   'Bike',  'Cycling',        1445, 44.00, '4 ft x 2 ft',      135, 297, 21.5, 'Tilt',           'Manual resistance knob',              'Entry-level studio cycling at home',               2014, 'Cardio'),
  ('Bike+',  'Bike',  'Cycling',        2495, 44.00, '4 ft x 2 ft',      140, 297, 23.8, 'Rotate + tilt',  'Auto-Follow resistance',              'Cycling plus off-bike strength and yoga',          2020, 'Cardio + Strength'),
  ('Tread',  'Tread', 'Running',        2995, 44.00, '68 in x 33 in',    290, 300, 23.8, 'Tilt',           '0-12.5 mph, 0-12.5% incline',         'Running and walking with guided classes',          2020, 'Cardio'),
  ('Tread+', 'Tread', 'Running',        5995, 44.00, '75 in x 36.5 in',  455, 300, 32.0, 'Tilt',           'Slat belt, 0-12.5 mph, 0-15% incline', 'Premium running with a shock-absorbing slat belt', 2023, 'Cardio'),
  ('Row',    'Row',   'Rowing',         2995, 44.00, '8 ft x 2 ft',      156, 300, 23.8, 'Swivel + tilt',  'Form Assist stroke feedback',         'Full-body low-impact cardio',                      2022, 'Cardio + Strength'),
  ('Guide',  'Guide', 'Strength',        295, 24.00, 'Connects to TV',     1, 999,  0.0, 'Uses your TV',   'Camera Movement Tracker',             'Strength training with rep tracking',              2022, 'Strength'),
  ('App',    'App',   'Multi-modality',    0, 12.99, 'No hardware',        0, 999,  0.0, 'Your own device','Works with any equipment',            'Classes anywhere on phone, tablet, or TV',         2018, 'Multi-modality')
as v(product, family, modality, list_price_usd, membership_usd_per_month, footprint, weight_lb, max_user_weight_lb, screen_inches, screen_movement, signature_feature, best_for, launch_year, training_focus)
