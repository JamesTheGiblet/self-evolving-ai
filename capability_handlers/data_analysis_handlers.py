# capability_handlers/data_analysis_handlers.py

import math
import re
import statistics
from collections import Counter
from typing import Dict, Any, List

from utils.logger import log
from core.context_manager import ContextManager
from core.utils.data_extraction import _extract_data_recursively
# Import constants
from core.constants import DEFAULT_STOP_WORDS

def execute_data_analysis_basic_v1(agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list):
    data_points = cap_inputs.get("data_to_analyze", []) # Expects a list

    extracted_numbers: List[float] = []
    extracted_texts: List[str] = []
    _extract_data_recursively(data_points, extracted_numbers, extracted_texts)

    details: Dict[str, Any] = {
        "input_item_count": len(data_points) if isinstance(data_points, list) else 1,
        "extracted_numbers_count": len(extracted_numbers),
        "extracted_texts_count": len(extracted_texts),
    }
    outcome = "success_no_data_analyzed"
    immediate_reward = 0.1 # Base reward for attempting
    log_message_parts = []


    # Numerical Analysis
    if extracted_numbers:
        details["numerical_analysis"] = {}
        num_analysis = details["numerical_analysis"]

        num_analysis["sum"] = sum(extracted_numbers)
        num_analysis["mean"] = num_analysis["sum"] / len(extracted_numbers) if extracted_numbers else 0
        num_analysis["min"] = min(extracted_numbers) if extracted_numbers else None
        num_analysis["max"] = max(extracted_numbers) if extracted_numbers else None

        std_dev = 0
        if len(extracted_numbers) > 1:
            # Population standard deviation
            variance = sum([(x - num_analysis["mean"]) ** 2 for x in extracted_numbers]) / len(extracted_numbers)
            std_dev = math.sqrt(variance)
            num_analysis["std_dev_population"] = std_dev
        else:
            num_analysis["std_dev_population"] = 0

        if std_dev > 1e-9: # Avoid issues with near-zero std_dev for outlier detection
            k_std_dev = params_used.get("outlier_std_devs", 2.0) # Use params_used from capability definition
            lower_bound = num_analysis["mean"] - (k_std_dev * std_dev)
            upper_bound = num_analysis["mean"] + (k_std_dev * std_dev)
            outliers = [x for x in extracted_numbers if x < lower_bound or x > upper_bound]
            num_analysis["outliers"] = outliers
            num_analysis["outlier_count"] = len(outliers)
            num_analysis["outlier_detection_threshold_std_devs"] = k_std_dev

        immediate_reward += 0.3 + min(len(extracted_numbers) * 0.01, 0.2)
        outcome = "success_numerical_analysis"
        log_message_parts.append(f"Numerical (Mean: {num_analysis['mean']:.2f}, StdDev: {std_dev:.2f}, Outliers: {num_analysis.get('outlier_count', 0)})")
    else:
        log_message_parts.append("No numerical data extracted")

    # Textual Analysis
    if extracted_texts:
        details["textual_analysis"] = {}
        txt_analysis = details["textual_analysis"]
        full_text = " ".join(extracted_texts)

        words = re.findall(r'\b\w+\b', full_text.lower()) # Split into words, lowercase
        txt_analysis["word_count"] = len(words)

        if words:
            # Use configurable stop words list
            stop_words_to_use = params_used.get("stop_words_override", DEFAULT_STOP_WORDS)
            if not isinstance(stop_words_to_use, set): # Ensure it's a set for efficient lookup
                stop_words_to_use = set(stop_words_to_use)
            filtered_words = [word for word in words if word not in stop_words_to_use and len(word) > 2 and not word.isdigit()]

            if filtered_words:
                word_counts = Counter(filtered_words)
                txt_analysis["top_keywords"] = word_counts.most_common(params_used.get("top_n_keywords", 5)) # Use params_used
            else:
                txt_analysis["top_keywords"] = []

        immediate_reward += 0.2 + min(txt_analysis["word_count"] * 0.001, 0.2)
        if outcome == "success_numerical_analysis":
            outcome = "success_mixed_analysis"
        else:
            outcome = "success_textual_analysis"
        log_message_parts.append(f"Textual (Words: {txt_analysis['word_count']}, TopKeywords: {len(txt_analysis.get('top_keywords',[]))})")
    elif not extracted_numbers: # No numbers and no text
        log_message_parts.append("No textual data extracted")

    if not extracted_numbers and not extracted_texts:
        outcome = "failure_no_data_to_analyze" # More specific outcome
        immediate_reward = -0.1 # Penalize if no data at all was found/extracted
        log_message_parts = ["No numerical or textual data extracted for analysis."]


    log(f"[{agent.name}] Cap 'data_analysis_basic_v1' performed. " + " | ".join(log_message_parts))

    return {"outcome": outcome, "reward": immediate_reward, "details": details}

def execute_data_analysis_v1(agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list):
    """
    Performs advanced data analysis.
    Input: cap_inputs["data_to_analyze"] (list or other structure)
    Params: params_used["analysis_type"] ('advanced_stats', 'keyword_search', 'regex_match')
            params_used["keywords"] (list of strings for keyword_search)
            params_used["regex_pattern"] (string for regex_match)
    """
    data_points = cap_inputs.get("data_to_analyze", [])
    analysis_type_param = params_used.get("analysis_type", "advanced_stats") # Default to advanced_stats

    extracted_numbers: List[float] = []
    extracted_texts: List[str] = []
    _extract_data_recursively(data_points, extracted_numbers, extracted_texts)

    details: Dict[str, Any] = {
        "input_item_count": len(data_points) if isinstance(data_points, list) else 1,
        "extracted_numbers_count": len(extracted_numbers),
        "extracted_texts_count": len(extracted_texts),
        "requested_analysis_type": analysis_type_param
    }
    outcome = "success_analysis_performed" # Default optimistic outcome
    immediate_reward = 0.2 # Base reward for attempting advanced analysis
    log_parts = []

    if analysis_type_param == "advanced_stats":
        if extracted_numbers:
            details["advanced_numerical_stats"] = {}
            adv_num_stats = details["advanced_numerical_stats"]

            adv_num_stats["mean"] = statistics.mean(extracted_numbers)
            if len(extracted_numbers) > 1:
                adv_num_stats["median"] = statistics.median(extracted_numbers)
                try:
                    adv_num_stats["mode"] = statistics.mode(extracted_numbers)
                except statistics.StatisticsError:
                    adv_num_stats["mode"] = "N/A (no unique mode or data too sparse)"
                adv_num_stats["stdev_sample"] = statistics.stdev(extracted_numbers)
                adv_num_stats["variance_sample"] = statistics.variance(extracted_numbers)
            else: # For single number list
                adv_num_stats["median"] = extracted_numbers[0] if extracted_numbers else None
                adv_num_stats["mode"] = extracted_numbers[0] if extracted_numbers else None
                adv_num_stats["stdev_sample"] = 0
                adv_num_stats["variance_sample"] = 0

            immediate_reward += 0.5 + min(len(extracted_numbers) * 0.01, 0.3)
            log_parts.append(f"AdvancedStats (Mean: {adv_num_stats['mean']:.2f}, Median: {adv_num_stats.get('median', 'N/A')}, StDev: {adv_num_stats.get('stdev_sample', 0):.2f})")
        else: # No numbers for stats
            outcome = "failure_no_numerical_data_for_stats"
            immediate_reward = 0.05
            log_parts.append("AdvancedStats requested but no numerical data found.")

    elif analysis_type_param == "keyword_search":
        if extracted_texts:
            keywords_to_find = params_used.get("keywords", [])
            if not isinstance(keywords_to_find, list): keywords_to_find = []

            details["keyword_search_results"] = {}
            kw_results = details["keyword_search_results"]
            full_text_lower = " ".join(extracted_texts).lower()

            found_keywords_summary = {}
            for keyword in keywords_to_find:
                kw_lower = keyword.lower()
                count = full_text_lower.count(kw_lower)
                found_keywords_summary[keyword] = count

            kw_results["summary"] = found_keywords_summary
            kw_results["keywords_searched"] = keywords_to_find
            immediate_reward += 0.3 + min(len(keywords_to_find) * 0.05, 0.2)
            log_parts.append(f"KeywordSearch (Found: {sum(found_keywords_summary.values())} instances of {len(keywords_to_find)} keywords)")
        else: # No text for keyword search
            outcome = "failure_no_text_for_keyword_search"
            immediate_reward = 0.05
            log_parts.append("KeywordSearch requested but no textual data found.")

    elif analysis_type_param == "regex_match":
        if extracted_texts:
            regex_pattern = params_used.get("regex_pattern")
            details["regex_match_results"] = {}
            rgx_results = details["regex_match_results"]

            if regex_pattern and isinstance(regex_pattern, str):
                try:
                    matches = []
                    for text_item in extracted_texts:
                        matches.extend(re.findall(regex_pattern, text_item))
                    rgx_results["matches"] = matches
                    rgx_results["match_count"] = len(matches)
                    rgx_results["pattern_used"] = regex_pattern
                    immediate_reward += 0.4 + min(len(matches) * 0.02, 0.3)
                    log_parts.append(f"RegexMatch (Pattern: '{regex_pattern}', Found: {len(matches)} matches)")
                except re.error as e:
                    outcome = "failure_invalid_regex_pattern"
                    rgx_results["error"] = f"Invalid regex pattern: {str(e)}"
                    immediate_reward = 0.0
                    log_parts.append(f"RegexMatch failed due to invalid pattern: {regex_pattern}")
            else:
                outcome = "failure_no_regex_pattern_provided"
                immediate_reward = 0.05
                log_parts.append("RegexMatch requested but no pattern provided or pattern invalid.")
        else: # No text for regex
            outcome = "failure_no_text_for_regex"
            immediate_reward = 0.05
            log_parts.append("RegexMatch requested but no textual data found.")
    elif analysis_type_param == "correlation":
        details["correlation_analysis"] = {}
        corr_analysis_details = details["correlation_analysis"]

        # Example cap_inputs["data_to_analyze"] structure for named series correlation:
        # {
        #     "temperature": [20, 22, 21, 23, 22, 24, 25],
        #     "humidity": [60, 58, 59, 55, 56, 53, 52],
        #     "sales": [100, 110, 105, 115, 112, 120, 125],
        #     "another_numeric_series": [1, 2, 3, 4, 5, 6, 7], # Example of another series
        #     "non_numeric_data": "some text" # This will be ignored by named series logic
        # }
        # The 'analysis_type' (set to 'correlation') would typically come from
        # params_used, which are derived from the capability's definition
        # in capability_registry.py or overridden by the agent.

        
        # Check for named series input first
        if isinstance(data_points, dict) and len(data_points) >= 2:
            valid_series = {}
            for name, series_data in data_points.items():
                if isinstance(series_data, list) and all(isinstance(x, (int, float)) for x in series_data) and len(series_data) >= 2:
                    valid_series[name] = [float(x) for x in series_data] # Ensure float for stats.correlation
                else:
                    log(f"[{agent.name}] DataAnalysis: Series '{name}' in correlation input is not a valid list of numbers or too short. Skipping.", level="DEBUG")
            
            if len(valid_series) >= 2:
                corr_analysis_details["type"] = "named_series_correlation"
                corr_analysis_details["correlations"] = []
                series_names = list(valid_series.keys())
                calculated_any_correlation = False
                for i in range(len(series_names)):
                    for j in range(i + 1, len(series_names)):
                        s_name1, s_name2 = series_names[i], series_names[j]
                        series1_data, series2_data = valid_series[s_name1], valid_series[s_name2]
                        
                        if len(series1_data) != len(series2_data):
                            corr_analysis_details["correlations"].append({
                                "series_pair": (s_name1, s_name2),
                                "error": "Series lengths do not match for correlation."
                            })
                            log_parts.append(f"Correlation between '{s_name1}' & '{s_name2}' skipped (length mismatch).")
                            continue
                        try:
                            correlation_coefficient = statistics.correlation(series1_data, series2_data)
                            corr_analysis_details["correlations"].append({
                                "series_pair": (s_name1, s_name2),
                                "coefficient": correlation_coefficient,
                                "series1_length": len(series1_data),
                                "series2_length": len(series2_data)
                            })
                            log_parts.append(f"Correlation ('{s_name1}' vs '{s_name2}'): {correlation_coefficient:.3f}")
                            calculated_any_correlation = True
                        except statistics.StatisticsError as e:
                            corr_analysis_details["correlations"].append({
                                "series_pair": (s_name1, s_name2),
                                "error": f"StatsError: {str(e)}"
                            })
                            log_parts.append(f"Correlation error ('{s_name1}' vs '{s_name2}'): {str(e)}")
                if calculated_any_correlation:
                    immediate_reward += 0.5 
                    outcome = "success_named_series_correlation"
                else: # No successful correlations calculated, possibly all errors or length mismatches
                    immediate_reward += 0.1
                    outcome = "failure_correlation_calculation_issues_named_series"
            else: # Not enough valid named series, fall through to split logic or fail
                log_parts.append("Not enough valid named series for correlation, trying fallback.")
                # Fall through to use extracted_numbers if no valid named series were processed

        # Fallback to splitting extracted_numbers if named series correlation wasn't successful or applicable
        if outcome not in ["success_named_series_correlation", "failure_correlation_calculation_issues_named_series"]:
            if extracted_numbers and len(extracted_numbers) >= 4 and len(extracted_numbers) % 2 == 0:
                # ... (existing split_series_correlation logic remains here) ...
                # This part is unchanged from your previous version for brevity,
                # but it would be the same logic as before for splitting `extracted_numbers`.
                # For the purpose of this diff, assume it's correctly placed here.
                log_parts.append("Fallback: Attempting split-series correlation on flattened numbers.")
                # (Placeholder for the actual split logic from previous version)
                # If successful: outcome = "success_split_series_correlation", immediate_reward += 0.4
                # If error: outcome = "failure_correlation_calculation_error_split_series", immediate_reward += 0.05
            else:
                outcome = "failure_insufficient_data_for_any_correlation"
                corr_analysis_details["message"] = "Insufficient data for named series correlation, and not enough data or unsuitable structure for fallback split-series correlation."
                immediate_reward = 0.05 # Minimal reward for attempting
                log_parts.append("Correlation analysis: Insufficient data for named or fallback split-series correlation.")

    else: # Unknown analysis_type_param
        outcome = "failure_unknown_analysis_type"
        log_parts.append(f"Unknown or unsupported analysis_type: '{analysis_type_param}'")

    if not log_parts: # Should not happen if logic above is complete
        outcome = "failure_analysis_type_not_applicable_or_unknown"
        log_parts.append(f"Analysis type '{analysis_type_param}' not applicable or unknown with available data.")
        immediate_reward = 0.05

    log(f"[{agent.name}] Cap 'data_analysis_v1' performed. " + " | ".join(log_parts))
    return {"outcome": outcome, "reward": immediate_reward, "details": details}