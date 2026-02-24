"""
Módulo de logging para el bot de arbitraje.
Proporciona logs detallados en archivo y consola con colores.
"""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from colorama import init, Fore, Style

init(autoreset=True)


class JSONFormatter(logging.Formatter):
    """Formatea los logs como JSON para análisis posterior."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Formatea los logs con colores para la consola."""
    
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, Fore.WHITE)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{color}[{timestamp}] [{record.levelname}] {record.getMessage()}{Style.RESET_ALL}"


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: str = "INFO",
    json_logs: bool = False
) -> logging.Logger:
    """
    Configura un logger con salida a archivo y consola.
    
    Args:
        name: Nombre del logger
        log_file: Ruta al archivo de log (opcional)
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Si True, usa formato JSON para el archivo
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Evitar duplicar handlers
    if logger.handlers:
        return logger
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)
    
    # Handler para archivo
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        if json_logs:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        logger.addHandler(file_handler)
    
    return logger


class TradeLogger:
    """Logger especializado para operaciones de trading."""
    
    def __init__(self, base_logger: logging.Logger):
        self.logger = base_logger
    
    def log_trade_open(
        self,
        exchange: str,
        pair: str,
        side: str,
        amount: float,
        price: float,
        order_id: str
    ) -> None:
        """Registra la apertura de una operación."""
        self.logger.info(
            f"📈 OPERACIÓN ABIERTA | Exchange: {exchange} | Par: {pair} | "
            f"Lado: {side} | Cantidad: {amount} | Precio: {price} | OrderID: {order_id}"
        )
    
    def log_trade_close(
        self,
        exchange: str,
        pair: str,
        side: str,
        amount: float,
        entry_price: float,
        exit_price: float,
        profit: float,
        profit_percent: float,
        order_id: str
    ) -> None:
        """Registra el cierre de una operación."""
        emoji = "✅" if profit > 0 else "❌"
        self.logger.info(
            f"{emoji} OPERACIÓN CERRADA | Exchange: {exchange} | Par: {pair} | "
            f"Cantidad: {amount} | Entrada: {entry_price} | Salida: {exit_price} | "
            f"Ganancia: {profit} ({profit_percent:.2f}%) | OrderID: {order_id}"
        )
    
    def log_arbitrage_opportunity(
        self,
        buy_exchange: str,
        sell_exchange: str,
        pair: str,
        buy_price: float,
        sell_price: float,
        spread: float,
        spread_percent: float,
        estimated_profit: float
    ) -> None:
        """Registra una oportunidad de arbitraje detectada."""
        self.logger.info(
            f"💰 OPORTUNIDAD DE ARBITRAJE | Comprar: {buy_exchange} @ {buy_price} | "
            f"Vender: {sell_exchange} @ {sell_price} | Spread: {spread_percent:.2f}% | "
            f"Ganancia Estimada: {estimated_profit}"
        )
    
    def log_error(
        self,
        operation: str,
        error: Exception,
        context: Optional[dict] = None
    ) -> None:
        """Registra un error con contexto."""
        context_str = f" | Contexto: {context}" if context else ""
        self.logger.error(f"❌ ERROR en {operation}: {error}{context_str}")
    
    def log_news_impact(
        self,
        headline: str,
        sentiment: str,
        expected_impact: str,
        confidence: float
    ) -> None:
        """Registra el impacto de una noticia en el mercado."""
        self.logger.info(
            f"📰 NOTICIA DETECTADA | Titular: {headline[:50]}... | "
            f"Sentimiento: {sentiment} | Impacto: {expected_impact} | "
            f"Confianza: {confidence:.2f}"
        )
    
    def log_ml_prediction(
        self,
        prediction: str,
        confidence: float,
        features: dict
    ) -> None:
        """Registra una predicción del modelo de ML."""
        self.logger.debug(
            f"🤖 ML PREDICTION | {prediction} | Confianza: {confidence:.2f} | "
            f"Features: {features}"
        )
