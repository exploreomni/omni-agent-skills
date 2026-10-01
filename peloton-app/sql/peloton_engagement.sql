-- Query tab name: peloton_engagement
-- Snowflake. Illustrative member engagement per product; replace with the workouts/subscriptions model.
select * from values
  ('Bike',   4.6, 31, 92, 71, 38, 'Cycling'),
  ('Bike+',  5.1, 34, 94, 78, 46, 'Cycling'),
  ('Tread',  4.2, 36, 90, 69, 41, 'Running'),
  ('Tread+', 4.9, 41, 95, 82, 44, 'Running'),
  ('Row',    4.4, 28, 91, 74, 52, 'Rowing'),
  ('Guide',  3.8, 24, 84, 63, 61, 'Strength'),
  ('App',    3.1, 22, 76, 58, 70, 'Multi-modality')
as v(product, avg_workouts_per_week, avg_minutes_per_workout, retention_12m_pct, nps, cross_training_pct, primary_modality)
