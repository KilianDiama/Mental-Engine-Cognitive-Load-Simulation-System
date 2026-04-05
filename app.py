from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, List, Optional, Callable, Deque
from collections import deque

# =========================================================
# CONFIGURATION
# =========================================================

@dataclass(frozen=True)
class SystemConfig:
    phi: float = 1.618033988749
    max_stress: float = 3.0
    decay_rate: float = 0.015
    burnout_clarity: float = 0.2
    burnout_stress: float = 2.2
    history_size: int = 5000

# =========================================================
# DOMAIN MODEL
# =========================================================

@dataclass(frozen=True, slots=True)
class NeuroState:
    energy: float
    stress: float
    resilience: float
    clarity: float
    timestamp: datetime

    def is_burnout(self, cfg: SystemConfig) -> bool:
        return self.clarity < cfg.burnout_clarity or self.stress > cfg.burnout_stress

# =========================================================
# VALIDATION
# =========================================================

class InputValidator:
    @staticmethod
    def validate(intensity: float, hours: float, recovery: float):
        if not (0 <= intensity <= 1):
            raise ValueError("Intensity must be between 0 and 1")
        if hours <= 0:
            raise ValueError("Hours must be > 0")
        if not (0 <= recovery <= 1):
            raise ValueError("Recovery must be between 0 and 1")

# =========================================================
# STRATEGY (SIMULATION ENGINE)
# =========================================================

class SimulationStrategy(Protocol):
    def step(self, state: NeuroState, intensity: float, hours: float, recovery: float) -> NeuroState:
        ...

class DefaultSimulationStrategy:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def _circadian(self, t: datetime) -> float:
        return 1.0 + 0.25 * math.cos((t.hour - 3) * (2 * math.pi / 24))

    def step(self, state: NeuroState, intensity: float, hours: float, recovery: float) -> NeuroState:
        circ = self._circadian(state.timestamp)

        drain = (intensity ** self.cfg.phi) * (1.5 - state.resilience) * hours * 0.12
        passive = self.cfg.decay_rate * hours * circ
        gain = (recovery / (1 + state.stress * 0.5)) * hours * 0.25

        energy = self._clamp(state.energy - drain - passive + gain, 0, 1)

        stress_delta = (intensity * 1.6 * hours) - (recovery * 2.2 * hours)
        stress = self._clamp(state.stress + stress_delta, 0, self.cfg.max_stress)

        resilience = self._update_resilience(state, stress, recovery, hours)

        clarity = self._compute_clarity(energy, resilience, stress)

        return NeuroState(
            energy=round(energy, 4),
            stress=round(stress, 4),
            resilience=round(resilience, 4),
            clarity=round(clarity, 4),
            timestamp=state.timestamp + timedelta(hours=hours),
        )

    def _update_resilience(self, state, stress, recovery, hours):
        if stress < 0.6 and recovery > 0.5:
            delta = 0.03 * hours
        else:
            delta = -0.06 * (stress / self.cfg.max_stress)
        return self._clamp(state.resilience + delta, 0.1, 1.0)

    def _compute_clarity(self, energy, resilience, stress):
        return max(0.0, (energy * 0.5 + resilience * 0.5) * (1 - stress / self.cfg.max_stress))

    @staticmethod
    def _clamp(val, lo, hi):
        return max(lo, min(hi, val))

# =========================================================
# CORE ENGINE
# =========================================================

class MentalEngine:
    def __init__(
        self,
        user: str,
        config: SystemConfig = SystemConfig(),
        strategy: Optional[SimulationStrategy] = None,
    ):
        self.user = user
        self.cfg = config
        self.strategy = strategy or DefaultSimulationStrategy(config)
        self.history: Deque[NeuroState] = deque(maxlen=config.history_size)
        self.alerts: List[Callable[[str], None]] = []

        self.history.append(
            NeuroState(1.0, 0.0, 1.0, 1.0, datetime.now())
        )

    @property
    def current(self) -> NeuroState:
        return self.history[-1]

    def update(self, intensity: float, hours: float, recovery: float = 0.0) -> NeuroState:
        InputValidator.validate(intensity, hours, recovery)

        new_state = self.strategy.step(self.current, intensity, hours, recovery)
        self.history.append(new_state)

        if new_state.is_burnout(self.cfg):
            self._trigger_alert()

        return new_state

    def predict_burnout(self, intensity: float, horizon: int = 48) -> Optional[int]:
        temp = self.current
        for h in range(1, horizon + 1):
            temp = self.strategy.step(temp, intensity, 1, 0)
            if temp.is_burnout(self.cfg):
                return h
        return None

    def _trigger_alert(self):
        for cb in self.alerts:
            cb(f"[ALERT] {self.user} burnout detected")

# =========================================================
# REPORTING (DECOUPLED)
# =========================================================

class ReportGenerator:
    @staticmethod
    def summary(state: NeuroState) -> dict:
        return {
            "energy": state.energy,
            "stress": state.stress,
            "resilience": state.resilience,
            "clarity": state.clarity,
            "time": state.timestamp.isoformat(),
        }

# =========================================================
# CLI VIEW (OPTIONAL)
# =========================================================

class ConsoleRenderer:
    @staticmethod
    def render(state: NeuroState):
        def bar(v):
            return "█" * int(v * 20)

        print("\n=== MENTAL STATE ===")
        print(f"Time     : {state.timestamp.strftime('%H:%M')}")
        print(f"Energy   : {bar(state.energy)} {state.energy:.2f}")
        print(f"Clarity  : {bar(state.clarity)} {state.clarity:.2f}")
        print(f"Stress   : {state.stress:.2f}")
        print(f"Resil.   : {state.resilience:.2f}")

# =========================================================
# EXAMPLE USAGE
# =========================================================

if __name__ == "__main__":
    engine = MentalEngine("Kiliandiama")

    engine.alerts.append(print)

    engine.update(0.95, 8)
    ConsoleRenderer.render(engine.current)

    engine.update(0.05, 1.5, recovery=0.9)
    ConsoleRenderer.render(engine.current)

    eta = engine.predict_burnout(0.8)
    print(f"\nBurnout ETA (80% load): {eta}h")
