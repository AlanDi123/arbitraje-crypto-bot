"""
Módulo de Machine Learning para predicción y aprendizaje.
Usa scikit-learn para analizar patrones de trading.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib

from ..utils import Config, setup_logger


class MLTrader:
    """
    Modelo de ML para predecir oportunidades de arbitraje.
    
    Características:
    - Aprende de operaciones anteriores (ganadoras/perdedoras)
    - Analiza patrones de precio, volumen y spread
    - Considera sentimiento de noticias
    - Se reentrena periódicamente
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger("ml.trader")
        
        self.model_path = Path(config.ml_model_path)
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        
        # Datos de entrenamiento
        self.training_data: List[Dict] = []
        self.features: List[str] = [
            'spread_percent',
            'binance_volume',
            'argentine_volume',
            'price_difference',
            'volatility',
            'hour_of_day',
            'day_of_week',
            'news_sentiment_score',
            'news_impact_score',
            'recent_win_rate',
            'avg_spread_last_10',
            'price_trend',
        ]
        
        # Estadísticas para features
        self.recent_trades: List[Dict] = []
        self.recent_spreads: List[float] = []
        
        # Estado del modelo
        self.is_trained = False
        self.last_training: Optional[datetime] = None
        self.training_count = 0
    
    async def start(self) -> None:
        """Inicia el sistema de ML."""
        self.logger.info("🤖 Sistema de ML iniciado")
        
        # Cargar modelo existente si hay
        await self.load_model()
        
        # Si no hay modelo, crear uno nuevo
        if not self.is_trained:
            self.logger.info("📝 Creando nuevo modelo...")
            self._initialize_model()
        
        # Loop de reentrenamiento periódico
        while True:
            try:
                await asyncio.sleep(self.config.retrain_interval_hours * 3600)
                await self.retrain_if_needed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error en el loop de ML: {e}")
                await asyncio.sleep(3600)
    
    async def stop(self) -> None:
        """Detiene el sistema de ML."""
        await self.save_model()
        self.logger.info("🤖 Sistema de ML detenido")
    
    def _initialize_model(self) -> None:
        """Inicializa un nuevo modelo."""
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def _create_features(
        self,
        spread_percent: float,
        binance_volume: float,
        argentine_volume: float,
        price_difference: float,
        volatility: float,
        news_sentiment: float,
        news_impact: float,
    ) -> np.ndarray:
        """Crea el vector de features para predicción."""
        now = datetime.now()
        
        # Calcular features adicionales
        recent_win_rate = self._calculate_recent_win_rate()
        avg_spread_last_10 = np.mean(self.recent_spreads[-10:]) if self.recent_spreads else 0
        price_trend = self._calculate_price_trend()
        
        features = [
            spread_percent,
            binance_volume,
            argentine_volume,
            price_difference,
            volatility,
            now.hour,
            now.weekday(),
            news_sentiment,
            news_impact,
            recent_win_rate,
            avg_spread_last_10,
            price_trend,
        ]
        
        return np.array(features).reshape(1, -1)
    
    def _calculate_recent_win_rate(self) -> float:
        """Calcula la tasa de victorias reciente."""
        if not self.recent_trades:
            return 0.5
        
        recent = self.recent_trades[-20:]  # Últimas 20 operaciones
        wins = sum(1 for t in recent if t.get('profit', 0) > 0)
        return wins / len(recent)
    
    def _calculate_price_trend(self) -> float:
        """Calcula la tendencia del precio (1 = alcista, -1 = bajista, 0 = neutral)."""
        if len(self.recent_spreads) < 5:
            return 0
        
        recent = self.recent_spreads[-5:]
        if recent[-1] > recent[0] * 1.01:
            return 1
        elif recent[-1] < recent[0] * 0.99:
            return -1
        return 0
    
    def predict(
        self,
        spread_percent: float,
        binance_volume: float,
        argentine_volume: float,
        price_difference: float,
        volatility: float,
        news_sentiment: float = 0,
        news_impact: float = 0,
    ) -> Tuple[str, float]:
        """
        Predice si una oportunidad es rentable.
        
        Returns:
            (decisión, confianza) - 'PROFIT' o 'LOSS' con confianza 0-1
        """
        if not self.is_trained:
            return 'PROFIT', 0.5  # Default si no está entrenado
        
        try:
            features = self._create_features(
                spread_percent,
                binance_volume,
                argentine_volume,
                price_difference,
                volatility,
                news_sentiment,
                news_impact,
            )
            
            # Escalar features
            features_scaled = self.scaler.transform(features)
            
            # Predecir
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # 1 = PROFIT, 0 = LOSS
            label = 'PROFIT' if prediction == 1 else 'LOSS'
            confidence = probabilities[prediction]
            
            self.logger.debug(
                f"🤖 Predicción: {label} | Confianza: {confidence:.2f} | "
                f"Spread: {spread_percent:.2f}%"
            )
            
            return label, confidence
            
        except Exception as e:
            self.logger.error(f"Error en predicción: {e}")
            return 'PROFIT', 0.5
    
    def record_trade(
        self,
        spread_percent: float,
        profit: float,
        binance_volume: float,
        argentine_volume: float,
        price_difference: float,
        volatility: float,
        news_sentiment: float = 0,
        news_impact: float = 0,
    ) -> None:
        """Registra una operación para aprendizaje futuro."""
        trade_data = {
            'timestamp': datetime.now().isoformat(),
            'features': {
                'spread_percent': spread_percent,
                'binance_volume': binance_volume,
                'argentine_volume': argentine_volume,
                'price_difference': price_difference,
                'volatility': volatility,
                'news_sentiment_score': news_sentiment,
                'news_impact_score': news_impact,
            },
            'profit': profit,
            'label': 1 if profit > 0 else 0,  # 1 = ganadora, 0 = perdedora
        }
        
        self.training_data.append(trade_data)
        self.recent_trades.append(trade_data)
        self.recent_spreads.append(spread_percent)
        
        # Mantener solo últimos 1000 trades
        if len(self.training_data) > 1000:
            self.training_data = self.training_data[-1000:]
        
        if len(self.recent_trades) > 100:
            self.recent_trades = self.recent_trades[-100:]
        
        self.logger.info(
            f"📝 Trade registrado: {'GANADOR' if profit > 0 else 'PERDEDOR'} | "
            f"Profit: {profit:.2f} | Spread: {spread_percent:.2f}% | "
            f"Total datos: {len(self.training_data)}"
        )
    
    async def retrain_if_needed(self) -> None:
        """Reentrena el modelo si hay suficientes datos nuevos."""
        # Necesitamos al menos 50 trades nuevos desde el último entrenamiento
        trades_since_last = len([
            d for d in self.training_data
            if self.last_training is None or d['timestamp'] > self.last_training.isoformat()
        ])
        
        if trades_since_last >= 50 and len(self.training_data) >= 100:
            self.logger.info(f"🔄 Reentrenando modelo con {len(self.training_data)} trades...")
            self._train_model()
            await self.save_model()
        else:
            self.logger.debug(
                f"⏭️ Saltando entrenamiento ({trades_since_last} trades nuevos, "
                f"mínimo 50 requeridos)"
            )
    
    def _train_model(self) -> None:
        """Entrena el modelo con los datos actuales."""
        if len(self.training_data) < 50:
            self.logger.warning("No hay suficientes datos para entrenar")
            return
        
        # Preparar datos
        X = []
        y = []
        
        for trade in self.training_data:
            features = trade['features']
            feature_vector = [
                features['spread_percent'],
                features['binance_volume'],
                features['argentine_volume'],
                features['price_difference'],
                features['volatility'],
                datetime.fromisoformat(trade['timestamp']).hour,
                datetime.fromisoformat(trade['timestamp']).weekday(),
                features['news_sentiment_score'],
                features['news_impact_score'],
                self._calculate_recent_win_rate(),
                np.mean(self.recent_spreads[-10:]) if self.recent_spreads else 0,
                self._calculate_price_trend(),
            ]
            X.append(feature_vector)
            y.append(trade['label'])
        
        X = np.array(X)
        y = np.array(y)
        
        # Dividir datos
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Escalar
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Entrenar
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluar
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        
        self.is_trained = True
        self.last_training = datetime.now()
        self.training_count += 1
        
        self.logger.info(
            f"✅ Modelo entrenado (Iteración #{self.training_count}) | "
            f"Accuracy: {accuracy:.2f} | Precision: {precision:.2f} | "
            f"Recall: {recall:.2f}"
        )
    
    async def save_model(self) -> None:
        """Guarda el modelo en disco."""
        if not self.is_trained:
            return
        
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'training_data': self.training_data,
                'last_training': self.last_training.isoformat() if self.last_training else None,
                'training_count': self.training_count,
            }, self.model_path)
            
            self.logger.info(f"💾 Modelo guardado en {self.model_path}")
            
        except Exception as e:
            self.logger.error(f"Error guardando modelo: {e}")
    
    async def load_model(self) -> None:
        """Carga el modelo desde disco."""
        if not self.model_path.exists():
            self.logger.info("📭 No hay modelo guardado, se creará uno nuevo")
            return
        
        try:
            data = joblib.load(self.model_path)
            
            self.model = data['model']
            self.scaler = data['scaler']
            self.training_data = data.get('training_data', [])
            self.last_training = (
                datetime.fromisoformat(data['last_training'])
                if data.get('last_training') else None
            )
            self.training_count = data.get('training_count', 0)
            self.is_trained = True
            
            self.logger.info(
                f"📥 Modelo cargado | Trades: {len(self.training_data)} | "
                f"Entrenamientos: {self.training_count}"
            )
            
        except Exception as e:
            self.logger.error(f"Error cargando modelo: {e}")
            self._initialize_model()
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del modelo."""
        return {
            'is_trained': self.is_trained,
            'training_data_size': len(self.training_data),
            'training_count': self.training_count,
            'last_training': self.last_training.isoformat() if self.last_training else None,
            'recent_win_rate': self._calculate_recent_win_rate(),
            'avg_spread': np.mean(self.recent_spreads) if self.recent_spreads else 0,
        }
