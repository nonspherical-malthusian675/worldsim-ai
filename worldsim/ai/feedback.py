"""Feedback loop system — connects simulation output back to AI/optimization."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    Adaptive feedback loop: simulation results → AI re-prediction → re-optimization.
    
    Detects performance drift and triggers corrective actions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._window_size = self.config.get("feedback_window", 20)
        self._drift_threshold = self.config.get("drift_threshold", 0.15)
        self._reoptimization_threshold = self.config.get("reopt_threshold", 0.10)
        
        self._metrics_window: List[Dict[str, float]] = []
        self._predictions_window: List[Dict[str, float]] = []
        self._corrections: List[Dict[str, Any]] = []
        self._callbacks: Dict[str, List[Callable]] = {}
        self._enabled = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def register_callback(self, event_type: str, callback: Callable) -> None:
        """Register a callback for feedback events."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        for cb in self._callbacks.get(event_type, []):
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"Feedback callback error: {e}")

    def update(self, tick: int, actual_metrics: Dict[str, float],
               predicted_metrics: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Process one feedback cycle.
        
        Args:
            tick: current simulation tick
            actual_metrics: actual measured metrics
            predicted_metrics: what was predicted (if any)
        
        Returns:
            Feedback result with drift status and corrections
        """
        if not self._enabled:
            return {"status": "disabled"}

        # Store in windows
        self._metrics_window.append({"tick": tick, **actual_metrics})
        if len(self._metrics_window) > self._window_size * 2:
            self._metrics_window = self._metrics_window[-self._window_size:]

        if predicted_metrics:
            self._predictions_window.append({"tick": tick, **predicted_metrics})
            if len(self._predictions_window) > self._window_size * 2:
                self._predictions_window = self._predictions_window[-self._window_size:]

        result = {
            "tick": tick,
            "drift_detected": False,
            "reoptimize": False,
            "corrections": {},
        }

        if len(self._metrics_window) < self._window_size:
            return {**result, "status": "warming_up"}

        # 1. Check prediction drift
        if predicted_metrics and len(self._predictions_window) >= self._window_size:
            drift = self._compute_prediction_drift()
            result["prediction_drift"] = drift
            if drift["drift_detected"]:
                result["drift_detected"] = True
                result["corrections"]["prediction_adjustment"] = drift["adjustment"]
                self._emit("drift_detected", {"tick": tick, "drift": drift})
                logger.info(f"Prediction drift at tick {tick}: {drift}")

        # 2. Check performance degradation
        performance = self._check_performance_degradation()
        result["performance"] = performance
        if performance["degrading"]:
            result["reoptimize"] = True
            result["corrections"]["performance_correction"] = performance["correction"]
            self._emit("performance_degrading", {"tick": tick, "performance": performance})
            logger.info(f"Performance degrading at tick {tick}: {performance}")

        # 3. Adaptive parameter adjustment
        if result["drift_detected"] or result["reoptimize"]:
            adjustment = self._compute_adaptive_adjustment(actual_metrics)
            result["corrections"]["adaptive_adjustment"] = adjustment
            self._corrections.append({"tick": tick, **result["corrections"]})
            if len(self._corrections) > 1000:
                self._corrections = self._corrections[-1000:]

        return result

    def _compute_prediction_drift(self) -> Dict[str, Any]:
        """Compare actual metrics to predictions over the window."""
        window = min(self._window_size, len(self._metrics_window), len(self._predictions_window))
        actuals = self._metrics_window[-window:]
        preds = self._predictions_window[-window:]

        drift_scores = {}
        for key in ["efficiency", "throughput", "stability", "resource_utilization"]:
            actual_vals = [a.get(key, 0) for a in actuals]
            pred_vals = [p.get(f"predicted_{key}", 0) for p in preds]
            if actual_vals and pred_vals:
                errors = [abs(a - p) for a, p in zip(actual_vals, pred_vals)]
                drift_scores[key] = {
                    "mean_error": float(np.mean(errors)),
                    "max_error": float(np.max(errors)),
                    "trend": float(errors[-1] - errors[0]) if len(errors) > 1 else 0,
                }

        overall_drift = np.mean([d["mean_error"] for d in drift_scores.values()]) if drift_scores else 0
        drift_detected = overall_drift > self._drift_threshold

        adjustment = {}
        if drift_detected:
            for key, scores in drift_scores.items():
                if scores["mean_error"] > self._drift_threshold:
                    adjustment[key] = scores["trend"] * 0.5  # correct half the trend

        return {
            "drift_detected": drift_detected,
            "overall_drift": round(overall_drift, 4),
            "by_metric": drift_scores,
            "adjustment": adjustment,
        }

    def _check_performance_degradation(self) -> Dict[str, Any]:
        """Check if key metrics are degrading over time."""
        window = self._metrics_window[-self._window_size:]
        result = {"degrading": False, "correction": {}}

        for key in ["efficiency", "stability"]:
            values = [m.get(key, 0) for m in window if key in m]
            if len(values) < 5:
                continue
            
            # Check if recent values are declining
            first_half = np.mean(values[:len(values)//2])
            second_half = np.mean(values[len(values)//2:])
            decline = first_half - second_half
            
            if decline > self._reoptimization_threshold:
                result["degrading"] = True
                result["correction"][f"increase_{key}"] = decline * 0.3

        return result

    def _compute_adaptive_adjustment(self, current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Compute adaptive parameter adjustments."""
        efficiency = current_metrics.get("efficiency", 0.5)
        stability = current_metrics.get("stability", 0.5)
        utilization = current_metrics.get("resource_utilization", 0.5)

        adjustments = {}
        
        if efficiency < 0.5:
            adjustments["energy_budget_multiplier"] = 1.2
            adjustments["prioritize_production"] = True
        elif efficiency > 0.9:
            adjustments["reduce_energy_budget"] = True
            adjustments["energy_budget_multiplier"] = 0.9

        if stability < 0.7:
            adjustments["smooth_transitions"] = True
            adjustments["reduce_randomness"] = True

        if utilization > 0.85:
            adjustments["scale_up_capacity"] = True

        return adjustments

    def get_correction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self._corrections[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        drift_count = sum(1 for c in self._corrections if "prediction_adjustment" in c)
        perf_count = sum(1 for c in self._corrections if "performance_correction" in c)
        return {
            "total_corrections": len(self._corrections),
            "drift_corrections": drift_count,
            "performance_corrections": perf_count,
            "feedback_window_size": len(self._metrics_window),
            "enabled": self._enabled,
        }

    def step(self, tick: int, state: Dict[str, Any], env_state: Dict[str, Any],
             agent_states: Dict[str, Any]) -> Dict[str, Any]:
        """AI module interface."""
        metrics = state
        predictions = None
        if "predicted_efficiency" in state:
            predictions = {k.replace("predicted_", ""): v
                         for k, v in state.items() if k.startswith("predicted_")}
        return self.update(tick, metrics, predictions)
