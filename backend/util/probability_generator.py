import pandas as pd

def calculate_strike_probabilities(fingerprint_csv_path, current_price, strike_prices, ttc_minutes):
    """
    Calculate real-time strike probabilities using fingerprint data.
    Args:
        fingerprint_csv_path (str): Path to fingerprint CSV file
        current_price (float): Current symbol price
        strike_prices (list): List of strike prices (float)
        ttc_minutes (int): Minutes to market close (1-15)
    Returns:
        dict: Mapping of strike prices to probabilities (rounded to 1 decimal place)
    """
    # Load the fingerprint CSV
    df = pd.read_csv(fingerprint_csv_path, index_col=0)
    if ttc_minutes < 1 or ttc_minutes > 15:
        raise ValueError("ttc_minutes must be between 1 and 15")
    ttc_row_label = f"{ttc_minutes}m TTC"
    if ttc_row_label not in df.index:
        raise ValueError(f"TTC row '{ttc_row_label}' not found in fingerprint data")
    probabilities = df.loc[ttc_row_label]
    thresholds = []
    for col in df.columns:
        threshold_str = col.replace(">= ", "").replace("%", "")
        thresholds.append(float(threshold_str))
    results = {}
    for strike_price in strike_prices:
        buffer_percent = abs((strike_price - current_price) / current_price) * 100
        matching_threshold = None
        for i, threshold in enumerate(thresholds):
            if threshold >= buffer_percent:
                matching_threshold = threshold
                break
        if matching_threshold is None:
            matching_threshold = thresholds[-1]
        threshold_col = f">= {matching_threshold:.2f}%"
        probability = probabilities[threshold_col]
        results[strike_price] = round(probability, 1)
    return results 