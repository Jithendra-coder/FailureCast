from backend.app.ml import metrics_for


def test_metrics_include_bias_rul_bands_and_asymmetric_score():
    result = metrics_for([10, 45, 90], [12, 42, 95])
    assert result["mae"] == 3.333
    assert result["bias"] == 1.333
    assert set(result["mae_by_rul_range"]) == {"0_30", "30_60", "60_plus"}
    assert result["nasa_score"] > 0


def test_nasa_score_penalizes_late_predictions_more_than_early_predictions():
    early = metrics_for([40], [35])["nasa_score"]
    late = metrics_for([40], [45])["nasa_score"]
    assert late > early
