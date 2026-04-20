-- Unified analytical dataset build for allied health forecasting.
--
-- Expected input tables (load from cleaned CSVs):
--   workforce_clean(year, region, profession, workforce_supply)
--   population_clean(year, region, population)
--   demand_clean(year, region, demand_indicator)

WITH workforce AS (
    SELECT
        CAST(year AS INTEGER) AS year,
        TRIM(region) AS region,
        TRIM(profession) AS profession,
        CAST(workforce_supply AS REAL) AS workforce_supply
    FROM workforce_clean
),
population AS (
    SELECT
        CAST(year AS INTEGER) AS year,
        TRIM(region) AS region,
        CAST(population AS REAL) AS population
    FROM population_clean
),
demand AS (
    SELECT
        CAST(year AS INTEGER) AS year,
        TRIM(region) AS region,
        CAST(demand_indicator AS REAL) AS demand_indicator
    FROM demand_clean
),
integrated AS (
    SELECT
        w.year,
        w.region,
        w.profession,
        w.workforce_supply,
        p.population,
        d.demand_indicator
    FROM workforce w
    LEFT JOIN population p
        ON w.year = p.year
       AND w.region = p.region
    LEFT JOIN demand d
        ON w.year = d.year
       AND w.region = d.region
)
SELECT *
FROM integrated
WHERE year IS NOT NULL
  AND region IS NOT NULL
  AND profession IS NOT NULL
ORDER BY year, region, profession;

-- Validation query examples:
-- 1) Check row count by year:
-- SELECT year, COUNT(*) AS records FROM integrated GROUP BY year ORDER BY year;
--
-- 2) Check missing demand/population after join:
-- SELECT
--   SUM(CASE WHEN population IS NULL THEN 1 ELSE 0 END) AS missing_population,
--   SUM(CASE WHEN demand_indicator IS NULL THEN 1 ELSE 0 END) AS missing_demand
-- FROM integrated;
