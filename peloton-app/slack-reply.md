# Slack reply draft (internal thread: Peloton "interactive product comparison" brief)

Happy to take this one. I've put a first "art of the possible" cut on the demo instance as an Omni App:

https://omni.omniapp.co/w/f8a35453?redirectToApp=true

What it does:
- Pick up to four products (Bike, Bike+, Tread, Tread+, Row, Guide, App) and get a side-by-side with "winner" tags
- Spec sheet with best-in-row highlights and a differences-only toggle
- 24-month momentum chart (units / hardware revenue / new memberships) with region filter, plus regional share
- Member engagement small multiples (workouts per week, retention, NPS, cross-training)
- A "Fit finder": goal, budget, space, priority → a ranked line-up with reasons, one click to compare the top three

Built as plain HTML on top of three workbook queries, so once Peloton points those three tabs at their catalog, orders, and workouts tables it goes live with no code changes. Right now it runs on sample data (badge in the header says so). Specs and list prices are indicative.

Happy to iterate on the concept before we show it. Ideas I'd add next: a "build your bundle" view (hardware + accessories + membership total cost over 12/24 months), and a cohort view of retention by product.
