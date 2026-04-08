"""engine/models/xgboost_model.py – XGBoost model wrapper with graceful fallback."""
from utils.logger import get_logger
from engine.models.base_model import BaseModel

_logger = get_logger(__name__)

try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False
    _logger.debug("xgboost not installed; XGBoostModel will be a no-op")


class XGBoostModel(BaseModel):
    """XGBoost regressor wrapper."""

    name = "xgboost"

    def __init__(self, n_estimators: int = 200, max_depth: int = 5, learning_rate: float = 0.05):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self._model = None

    def train(self, X, y) -> None:
        """Train XGBoost model with early stopping when possible.

        Holds out the last 20% of data for early stopping evaluation
        to prevent overfitting.  Falls back to full-data training when
        the dataset is too small.

        Args:
            X: Feature matrix.
            y: Target vector.
        """
        if not _XGB_AVAILABLE:
            _logger.warning("xgboost not available; XGBoostModel.train is a no-op")
            return
        try:
            import numpy as np
            n = len(X)
            split = int(n * 0.8)
            use_early_stop = split >= 10 and (n - split) >= 5

            # early_stopping_rounds=20: stop if validation metric does not
            # improve for 20 consecutive rounds — balances between giving
            # the model enough iterations and cutting off overfitting early.
            self._model = xgb.XGBRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42,
                verbosity=0,
                early_stopping_rounds=20 if use_early_stop else None,
            )

            if use_early_stop:
                X_train, X_es = np.array(X[:split]), np.array(X[split:])
                y_train, y_es = np.array(y[:split]), np.array(y[split:])
                self._model.fit(
                    X_train, y_train,
                    eval_set=[(X_es, y_es)],
                    verbose=False,
                )
                best = getattr(self._model, "best_iteration", self.n_estimators)
                _logger.info(
                    "XGBoostModel trained on %d samples (early stop @ %d rounds)",
                    n, best,
                )
            else:
                self._model.fit(X, y)
                _logger.info("XGBoostModel trained on %d samples (no early stop)", n)
        except Exception as exc:
            _logger.error("XGBoostModel.train failed: %s", exc)

    def predict(self, X):
        """Predict with XGBoost model.

        Args:
            X: Feature matrix.

        Returns:
            Array of predictions, or zeros if model not trained.
        """
        if self._model is None:
            try:
                import numpy as np
                return np.zeros(len(X))
            except ImportError:
                return [0.0] * len(X)
        try:
            return self._model.predict(X)
        except Exception as exc:
            _logger.error("XGBoostModel.predict failed: %s", exc)
            try:
                import numpy as np
                return np.zeros(len(X))
            except ImportError:
                return [0.0] * len(X)
