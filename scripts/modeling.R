suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(tidyr)
})

rmse <- function(actual, predicted) {
  sqrt(mean((actual - predicted)^2, na.rm = TRUE))
}

safe_numeric <- function(x) {
  as.numeric(ifelse(is.finite(x), x, NA_real_))
}

determine_holdout <- function(n) {
  if (n >= 12) return(4)
  if (n >= 8) return(3)
  if (n >= 6) return(2)
  if (n >= 5) return(1)
  return(0)
}

CALIBRATION_QUANTILE <- 0.90
MIN_CALIBRATION_ADDON <- 1e-6

compute_interval_calibration <- function(actual, predicted, residuals) {
  holdout_abs_err <- safe_numeric(abs(actual - predicted))
  holdout_abs_err <- holdout_abs_err[is.finite(holdout_abs_err)]

  residual_abs_err <- safe_numeric(abs(residuals))
  residual_abs_err <- residual_abs_err[is.finite(residual_abs_err)]

  if (length(holdout_abs_err) > 0) {
    addon <- as.numeric(quantile(holdout_abs_err, probs = CALIBRATION_QUANTILE, na.rm = TRUE))
    addon <- max(addon, MIN_CALIBRATION_ADDON)
    return(list(addon = addon, source = "holdout_abs_error_q90"))
  }

  if (length(residual_abs_err) > 0) {
    addon <- as.numeric(quantile(residual_abs_err, probs = CALIBRATION_QUANTILE, na.rm = TRUE))
    addon <- max(addon, MIN_CALIBRATION_ADDON)
    return(list(addon = addon, source = "residual_abs_error_q90"))
  }

  list(addon = MIN_CALIBRATION_ADDON, source = "epsilon_fallback")
}

forecast_linear <- function(train_df, future_years, test_years) {
  fit <- lm(workforce_supply ~ year, data = train_df)

  future_pred <- as.data.frame(
    predict(fit, newdata = data.frame(year = future_years), interval = "prediction")
  )

  test_pred <- numeric(0)
  if (length(test_years) > 0) {
    test_pred <- safe_numeric(predict(fit, newdata = data.frame(year = test_years)))
  }

  list(
    name = "linear",
    future = data.frame(
      year = future_years,
      predicted_supply = safe_numeric(future_pred$fit),
      lower = safe_numeric(future_pred$lwr),
      upper = safe_numeric(future_pred$upr)
    ),
    test_pred = test_pred,
    residuals = safe_numeric(residuals(fit)),
    warning_count = 0,
    warning_text = ""
  )
}

forecast_quadratic <- function(train_df, future_years, test_years) {
  fit <- lm(workforce_supply ~ year + I(year^2), data = train_df)

  future_pred <- as.data.frame(
    predict(fit, newdata = data.frame(year = future_years), interval = "prediction")
  )

  test_pred <- numeric(0)
  if (length(test_years) > 0) {
    test_pred <- safe_numeric(predict(fit, newdata = data.frame(year = test_years)))
  }

  list(
    name = "quadratic",
    future = data.frame(
      year = future_years,
      predicted_supply = safe_numeric(future_pred$fit),
      lower = safe_numeric(future_pred$lwr),
      upper = safe_numeric(future_pred$upr)
    ),
    test_pred = test_pred,
    residuals = safe_numeric(residuals(fit)),
    warning_count = 0,
    warning_text = ""
  )
}

forecast_holt <- function(train_df, future_years, test_years) {
  y <- ts(train_df$workforce_supply, frequency = 1)

  warning_messages <- character(0)

  fit <- withCallingHandlers(
    tryCatch(
      HoltWinters(y, gamma = FALSE),
      error = function(e) {
        warning_messages <<- c(warning_messages, paste("error:", conditionMessage(e)))
        NULL
      }
    ),
    warning = function(w) {
      warning_messages <<- c(warning_messages, conditionMessage(w))
      invokeRestart("muffleWarning")
    }
  )

  if (is.null(fit)) {
    return(NULL)
  }

  future_pred <- safe_numeric(predict(fit, n.ahead = length(future_years)))

  test_pred <- numeric(0)
  if (length(test_years) > 0) {
    test_pred <- safe_numeric(predict(fit, n.ahead = length(test_years)))
  }

  if (!is.null(fit$fitted) && nrow(fit$fitted) > 0) {
    fitted_vals <- safe_numeric(fit$fitted[, "xhat"])
    observed_vals <- safe_numeric(train_df$workforce_supply)
    observed_tail <- observed_vals[2:length(observed_vals)]
    common_len <- min(length(observed_tail), length(fitted_vals))

    if (common_len > 0) {
      residuals_vec <- safe_numeric(observed_tail[1:common_len] - fitted_vals[1:common_len])
    } else {
      residuals_vec <- safe_numeric(observed_vals - mean(observed_vals, na.rm = TRUE))
    }
  } else {
    residuals_vec <- safe_numeric(train_df$workforce_supply - mean(train_df$workforce_supply, na.rm = TRUE))
  }

  sigma <- sd(residuals_vec, na.rm = TRUE)
  if (!is.finite(sigma) || sigma <= 0) {
    sigma <- max(sd(train_df$workforce_supply, na.rm = TRUE), 1e-6)
  }

  z <- qnorm(0.975)
  h <- seq_along(future_years)
  band <- z * sigma * sqrt(h)

  list(
    name = "holt_winters",
    future = data.frame(
      year = future_years,
      predicted_supply = future_pred,
      lower = future_pred - band,
      upper = future_pred + band
    ),
    test_pred = test_pred,
    residuals = residuals_vec,
    warning_count = length(warning_messages),
    warning_text = paste(unique(warning_messages), collapse = " | ")
  )
}

fit_model_by_name <- function(model_name, train_df, future_years, test_years) {
  if (model_name == "linear") {
    return(forecast_linear(train_df, future_years, test_years))
  }
  if (model_name == "quadratic") {
    return(forecast_quadratic(train_df, future_years, test_years))
  }
  if (model_name == "holt_winters") {
    return(forecast_holt(train_df, future_years, test_years))
  }
  NULL
}

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
diagnostic_rows <- list()
idx <- 1
diagnostic_idx <- 1

for (key in split(series, interaction(series$region, series$profession, drop = TRUE))) {
  if (nrow(key) < 4) next

  key <- key %>% arrange(year)
  n <- nrow(key)
  holdout_n <- determine_holdout(n)

  if (holdout_n > 0) {
    train <- key %>% slice(1:(n - holdout_n))
    test <- key %>% slice((n - holdout_n + 1):n)
  } else {
    train <- key
    test <- key[0, ]
  }

  next_years <- seq(max(key$year) + 1, max(key$year) + forecast_horizon)
  test_years <- if (nrow(test) > 0) safe_numeric(test$year) else numeric(0)

  candidate_names <- c("linear")
  if (nrow(train) >= 5) candidate_names <- c(candidate_names, "quadratic")
  if (nrow(train) >= 5) candidate_names <- c(candidate_names, "holt_winters")

  candidates <- list()
  for (model_name in candidate_names) {
    fit_result <- fit_model_by_name(model_name, train, next_years, test_years)
    if (!is.null(fit_result)) {
      candidates[[length(candidates) + 1]] <- fit_result
    }
  }

  if (length(candidates) == 0) next

  metrics <- data.frame()
  for (cand in candidates) {
    holdout_rmse <- NA_real_
    if (length(test_years) > 0 && length(cand$test_pred) == length(test_years)) {
      holdout_rmse <- rmse(safe_numeric(test$workforce_supply), safe_numeric(cand$test_pred))
    }

    insample_rmse <- rmse(rep(0, length(cand$residuals)), cand$residuals)
    warning_count <- ifelse(is.null(cand$warning_count), 0, cand$warning_count)
    warning_penalty <- ifelse(warning_count > 0, 1e6, 0)
    base_score <- ifelse(is.na(holdout_rmse), insample_rmse, holdout_rmse)
    selection_score <- base_score + warning_penalty

    metrics <- bind_rows(
      metrics,
      data.frame(
        model = cand$name,
        holdout_rmse = holdout_rmse,
        insample_rmse = insample_rmse,
        warning_count = warning_count,
        warning_penalty = warning_penalty,
        warning_text = ifelse(is.null(cand$warning_text), "", cand$warning_text),
        selection_score = selection_score
      )
    )
  }

  best_row <- metrics %>% arrange(selection_score) %>% slice(1)
  selected_model <- best_row$model[[1]]
  selected_holdout_rmse <- best_row$holdout_rmse[[1]]
  selected_candidate_idx <- which(sapply(candidates, function(x) x$name) == selected_model)[1]

  if (is.na(selected_candidate_idx)) next
  selected_candidate <- candidates[[selected_candidate_idx]]

  holdout_actual <- if (nrow(test) > 0) safe_numeric(test$workforce_supply) else numeric(0)
  holdout_pred <- if (length(selected_candidate$test_pred) > 0) safe_numeric(selected_candidate$test_pred) else numeric(0)
  if (length(holdout_actual) != length(holdout_pred)) {
    holdout_actual <- numeric(0)
    holdout_pred <- numeric(0)
  }

  calibration <- compute_interval_calibration(holdout_actual, holdout_pred, selected_candidate$residuals)

  final_fit <- fit_model_by_name(selected_model, key, next_years, numeric(0))
  if (is.null(final_fit)) next

  final_future <- final_fit$future
  lower_margin <- pmax(final_future$predicted_supply - final_future$lower, 0)
  upper_margin <- pmax(final_future$upper - final_future$predicted_supply, 0)

  final_future$lower <- final_future$predicted_supply - (lower_margin + calibration$addon)
  final_future$upper <- final_future$predicted_supply + (upper_margin + calibration$addon)

  final_future <- final_future %>%
    mutate(
      region = key$region[[1]],
      profession = key$profession[[1]],
      selected_model = selected_model,
      holdout_rmse = selected_holdout_rmse,
      holdout_points = holdout_n,
      model_warning_count = ifelse(is.null(selected_candidate$warning_count), 0, selected_candidate$warning_count),
      calibration_addon = calibration$addon,
      calibration_source = calibration$source,
      interval_target = 0.95,
      uncertainty_width = upper - lower
    ) %>%
    mutate(
      predicted_supply = pmax(predicted_supply, 0),
      lower = pmax(lower, 0),
      upper = pmax(upper, predicted_supply),
      uncertainty_width = pmax(upper - lower, 0)
    ) %>%
    select(region, profession, year, predicted_supply, lower, upper, selected_model, holdout_rmse, holdout_points, model_warning_count, calibration_addon, calibration_source, interval_target, uncertainty_width)

  forecast_rows[[idx]] <- final_future
  idx <- idx + 1

  model_diag <- metrics %>%
    mutate(
      region = key$region[[1]],
      profession = key$profession[[1]],
      holdout_points = holdout_n,
      selected = model == selected_model,
      calibration_addon = ifelse(model == selected_model, calibration$addon, NA_real_),
      calibration_source = ifelse(model == selected_model, calibration$source, NA_character_)
    ) %>%
    select(region, profession, model, holdout_points, holdout_rmse, insample_rmse, warning_count, warning_penalty, warning_text, selection_score, selected, calibration_addon, calibration_source)

  diagnostic_rows[[diagnostic_idx]] <- model_diag
  diagnostic_idx <- diagnostic_idx + 1
}

if (length(forecast_rows) > 0) {
  forecast_df <- bind_rows(forecast_rows)
  write_csv(forecast_df, file.path(reports_dir, "workforce_forecast.csv"))
} else {
  write_csv(data.frame(), file.path(reports_dir, "workforce_forecast.csv"))
}

if (length(diagnostic_rows) > 0) {
  diagnostics_df <- bind_rows(diagnostic_rows)
  write_csv(diagnostics_df, file.path(reports_dir, "forecast_model_diagnostics.csv"))
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
