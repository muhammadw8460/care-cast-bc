suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(tidyr)
})

args <- commandArgs(trailingOnly = TRUE)
input_path <- ifelse(length(args) >= 1, args[[1]], "data/processed/analytical_dataset.csv")
output_root <- ifelse(length(args) >= 2, args[[2]], "outputs")
forecast_horizon <- ifelse(length(args) >= 3, as.integer(args[[3]]), 5)

charts_dir <- file.path(output_root, "charts")
reports_dir <- file.path(output_root, "reports")
dir.create(charts_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(reports_dir, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(input_path)) {
  stop(sprintf("Input file not found: %s", input_path))
}

df <- read_csv(input_path, show_col_types = FALSE)

required_any <- c("year", "region", "workforce_supply")
missing_cols <- setdiff(required_any, names(df))
if (length(missing_cols) > 0) {
  stop(sprintf("Missing required columns: %s", paste(missing_cols, collapse = ", ")))
}

df <- df %>%
  mutate(
    year = as.integer(year),
    workforce_supply = as.numeric(workforce_supply),
    population = if ("population" %in% names(.)) as.numeric(population) else NA_real_,
    demand_indicator = if ("demand_indicator" %in% names(.)) as.numeric(demand_indicator) else NA_real_,
    profession = if ("profession" %in% names(.)) profession else "Allied Health"
  ) %>%
  filter(!is.na(year), !is.na(region), !is.na(workforce_supply))

predictors <- c()
if ("population" %in% names(df) && !all(is.na(df$population))) predictors <- c(predictors, "population")
if ("demand_indicator" %in% names(df) && !all(is.na(df$demand_indicator))) predictors <- c(predictors, "demand_indicator")
predictors <- c(predictors, "factor(region)")

formula_text <- paste("workforce_supply ~", paste(c("year", predictors), collapse = " + "))
reg_formula <- as.formula(formula_text)

reg_df <- df %>%
  select(all_of(c("workforce_supply", "year", "region", setdiff(c("population", "demand_indicator"), character(0))))) %>%
  drop_na(workforce_supply, year, region)

if ("population" %in% names(reg_df)) reg_df <- reg_df %>% filter(!is.na(population))
if ("demand_indicator" %in% names(reg_df)) reg_df <- reg_df %>% filter(!is.na(demand_indicator))

if (nrow(reg_df) >= 10) {
  reg_model <- lm(reg_formula, data = reg_df)
  summary_path <- file.path(reports_dir, "regression_summary.txt")
  writeLines(capture.output(summary(reg_model)), summary_path)

  reg_predictions <- cbind(
    reg_df,
    as.data.frame(predict(reg_model, newdata = reg_df, interval = "confidence"))
  )

  reg_predictions <- reg_predictions %>% rename(predicted_supply = fit)
  write_csv(reg_predictions, file.path(reports_dir, "regression_predictions.csv"))
} else {
  writeLines("Not enough rows for regression model.", file.path(reports_dir, "regression_summary.txt"))
}

series <- df %>%
  group_by(region, profession, year) %>%
  summarise(workforce_supply = sum(workforce_supply, na.rm = TRUE), .groups = "drop")

forecast_rows <- list()
idx <- 1
for (key in split(series, interaction(series$region, series$profession, drop = TRUE))) {
  if (nrow(key) < 3) next

  key <- key %>% arrange(year)
  fit <- lm(workforce_supply ~ year, data = key)
  next_years <- seq(max(key$year) + 1, max(key$year) + forecast_horizon)
  future_df <- data.frame(year = next_years)

  pred <- as.data.frame(predict(fit, newdata = future_df, interval = "prediction"))
  out <- cbind(
    data.frame(region = key$region[[1]], profession = key$profession[[1]], year = next_years),
    pred
  ) %>% rename(predicted_supply = fit, lower = lwr, upper = upr)

  forecast_rows[[idx]] <- out
  idx <- idx + 1
}

if (length(forecast_rows) > 0) {
  forecast_df <- bind_rows(forecast_rows)
  write_csv(forecast_df, file.path(reports_dir, "workforce_forecast.csv"))
} else {
  write_csv(data.frame(), file.path(reports_dir, "workforce_forecast.csv"))
}

yearly_supply <- df %>%
  group_by(year, region) %>%
  summarise(workforce_supply = sum(workforce_supply, na.rm = TRUE), .groups = "drop")

supply_plot <- ggplot(yearly_supply, aes(x = year, y = workforce_supply, color = region)) +
  geom_line(linewidth = 0.9) +
  geom_point(size = 1.8) +
  labs(
    title = "Allied Health Workforce Supply Trend",
    x = "Year",
    y = "Workforce Supply"
  ) +
  theme_minimal()

ggsave(file.path(charts_dir, "supply_trends_by_region.png"), supply_plot, width = 10, height = 6, dpi = 300)

if ("population" %in% names(df) && !all(is.na(df$population))) {
  comp <- df %>%
    group_by(year) %>%
    summarise(
      supply = sum(workforce_supply, na.rm = TRUE),
      demand_proxy = sum(population, na.rm = TRUE),
      .groups = "drop"
    )

  comp_long <- comp %>%
    pivot_longer(cols = c("supply", "demand_proxy"), names_to = "series", values_to = "value")

  comp_plot <- ggplot(comp_long, aes(x = year, y = value, color = series)) +
    geom_line(linewidth = 1) +
    geom_point(size = 1.8) +
    labs(
      title = "Supply vs Demand Proxy Over Time",
      x = "Year",
      y = "Value"
    ) +
    theme_minimal()

  ggsave(file.path(charts_dir, "supply_vs_demand_proxy.png"), comp_plot, width = 10, height = 6, dpi = 300)
}

writeLines("Modeling run completed.", file.path(reports_dir, "run_status.txt"))
