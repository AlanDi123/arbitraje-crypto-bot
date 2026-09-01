"""
Módulo de utilidades para el bot de arbitraje.
Incluye funciones de cifrado, configuración y utilidades generales.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from datetime import datetime


class CryptoManager:
    """Gestiona el cifrado y descifrado de credenciales sensibles."""
    
    def __init__(self, password: str, salt_file: str = "data/.salt"):
        self.password = password.encode()
        self.salt_file = Path(salt_file)
        self.salt = self._get_or_create_salt()
        self.key = self._derive_key()
        self.fernet = Fernet(self.key)
    
    def _get_or_create_salt(self) -> bytes:
        """Obtiene o crea una sal para el cifrado."""
        if self.salt_file.exists():
            with open(self.salt_file, 'rb') as f:
                return f.read()
        
        # Crear directorio si no existe
        self.salt_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Generar nueva sal
        salt = os.urandom(16)
        with open(self.salt_file, 'wb') as f:
            f.write(salt)
        
        return salt
    
    def _derive_key(self) -> bytes:
        """Deriva una clave de cifrado desde la contraseña."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        return key
    
    def encrypt(self, data: str) -> str:
        """Cifra un string y lo devuelve en base64."""
        encrypted = self.fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Descifra un string desde base64."""
        decoded = base64.b64decode(encrypted_data.encode())
        decrypted = self.fernet.decrypt(decoded)
        return decrypted.decode()
    
    def encrypt_file(self, input_file: str, output_file: str) -> None:
        """Cifra un archivo completo."""
        with open(input_file, 'r') as f:
            data = f.read()
        
        encrypted = self.encrypt(data)
        
        with open(output_file, 'w') as f:
            f.write(encrypted)
    
    def decrypt_file(self, input_file: str) -> str:
        """Descifra un archivo completo."""
        with open(input_file, 'r') as f:
            encrypted = f.read()
        
        return self.decrypt(encrypted)


class Config:
    """Gestiona la configuración del bot desde variables de entorno y archivos."""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self._load_env()
        
        # Configuración de Binance
        self.binance_api_key = os.getenv("BINANCE_API_KEY", "")
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.binance_testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        self.binance_min_order = float(os.getenv("BINANCE_MIN_ORDER_USDT", "5"))
        
        # Configuración Exchange Argentino
        self.argentine_exchange = os.getenv("ARGENTINE_EXCHANGE", "buenbit")
        self.argentine_api_key = os.getenv("ARGENTINE_API_KEY", "")
        self.argentine_api_secret = os.getenv("ARGENTINE_API_SECRET", "")
        
        # Exchanges adicionales (formato: EXCHANGEID_API_KEY, EXCHANGEID_API_SECRET)
        self.additional_exchanges = self._parse_additional_exchanges()
        
        # Configuración de Telegram
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Configuración de Cifrado
        self.encryption_password = os.getenv("ENCRYPTION_PASSWORD", "")
        
        # Configuración de Trading
        self.initial_capital = float(os.getenv("INITIAL_CAPITAL_USDT", "7"))
        self.max_positions = int(os.getenv("MAX_POSITIONS", "1"))
        self.stop_loss_percent = float(os.getenv("STOP_LOSS_PERCENT", "5"))
        self.min_profit_percent = float(os.getenv("MIN_PROFIT_PERCENT", "0.5"))
        self.cooldown_seconds = int(os.getenv("COOLDOWN_SECONDS", "30"))
        self.real_trading_confirmation = os.getenv("CONFIRM_REAL_TRADING", "")
        self.real_trading_confirmed = self.real_trading_confirmation == "YES_I_UNDERSTAND_THE_RISK"
        self.max_real_trade_usdt = float(os.getenv("MAX_REAL_TRADE_USDT", str(self.initial_capital)))
        self.usdt_transfer_network = os.getenv("USDT_TRANSFER_NETWORK", "TRC20")
        self.transfer_timeout_minutes = int(os.getenv("TRANSFER_TIMEOUT_MINUTES", "20"))
        
        # Configuración de Noticias
        self.news_check_interval = int(os.getenv("NEWS_CHECK_INTERVAL_SECONDS", "300"))
        self.news_sources = os.getenv("NEWS_SOURCES", "infobae,clarin,pagina12").split(",")
        
        # Configuración de Logs
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file = os.getenv("LOG_FILE", "data/logs/arbitrage_bot.log")
        
        # Configuración de ML
        self.ml_model_path = os.getenv("ML_MODEL_PATH", "data/models/arbitrage_model.pkl")
        self.retrain_interval_hours = int(os.getenv("RETRAIN_INTERVAL_HOURS", "24"))
    
    def _parse_additional_exchanges(self) -> Dict[str, Dict[str, str]]:
        """
        Parsea exchanges adicionales desde variables de entorno.
        Formato: BYBIT_API_KEY, BYBIT_API_SECRET, OKX_API_KEY, OKX_API_SECRET, etc.
        """
        exchanges = {}
        
        # Lista de exchanges soportados
        supported = ['bybit', 'okx', 'kucoin', 'gateio', 'huobi', 'bitget', 'mexc', 'crypto_com']
        
        for exchange_id in supported:
            api_key = os.getenv(f"{exchange_id.upper()}_API_KEY", "")
            api_secret = os.getenv(f"{exchange_id.upper()}_API_SECRET", "")
            
            if api_key and api_secret:
                exchanges[exchange_id] = {
                    'api_key': api_key,
                    'api_secret': api_secret,
                }
        
        return exchanges
    
    def get_additional_exchanges(self) -> Dict[str, Dict[str, str]]:
        """Devuelve los exchanges adicionales configurados."""
        return self.additional_exchanges

    def get(self, key: str, default: str = "") -> str:
        """Obtiene un valor de configuración por clave."""
        return os.getenv(key, default)

    def _load_env(self) -> None:
        """Carga variables de entorno desde el archivo .env."""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    
    def validate(self) -> tuple[bool, list[str]]:
        """Valida la configuración mínima indispensable."""
        errors = []
        
        if not self.binance_api_key:
            errors.append("BINANCE_API_KEY no configurada")
        if not self.binance_api_secret:
            errors.append("BINANCE_API_SECRET no configurada")
        if not self.argentine_api_key or not self.argentine_api_secret:
            errors.append(
                "ARGENTINE_API_KEY / ARGENTINE_API_SECRET no configuradas "
                f"(necesarias para conectar {self.argentine_exchange.upper()})"
            )
        
        return len(errors) == 0, errors

    def optional_warnings(self) -> list[str]:
        """Funcionalidades opcionales sin configurar (no bloquean el arranque)."""
        warnings = []
        if not self.telegram_token or not self.telegram_chat_id:
            warnings.append("Telegram no configurado: no habrá notificaciones")
        if not self.encryption_password:
            warnings.append("ENCRYPTION_PASSWORD no configurada: las credenciales quedan en texto plano en .env")
        return warnings
    
    def to_dict(self) -> Dict[str, Any]:
        """Devuelve la configuración como diccionario (sin datos sensibles)."""
        return {
            "binance_testnet": self.binance_testnet,
            "argentine_exchange": self.argentine_exchange,
            "initial_capital": self.initial_capital,
            "max_positions": self.max_positions,
            "stop_loss_percent": self.stop_loss_percent,
            "min_profit_percent": self.min_profit_percent,
            "cooldown_seconds": self.cooldown_seconds,
            "news_check_interval": self.news_check_interval,
            "log_level": self.log_level,
        }


def get_project_root() -> Path:
    """Devuelve la ruta raíz del proyecto."""
    return Path(__file__).parent.parent


def get_timestamp() -> str:
    """Devuelve un timestamp formateado para logs."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_data(data: str) -> str:
    """Genera un hash SHA256 de un string."""
    return hashlib.sha256(data.encode()).hexdigest()
