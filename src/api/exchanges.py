"""
Módulo de conexión con APIs de exchanges.
Soporta múltiples exchanges: Binance, Bybit, OKX, KuCoin, Gate.io,
y exchanges argentinos (Buenbit, Ripio, SatoshiTango, Lemon, Belo, IOL, CryptoMarket, Bitso).
Incluye CriptoYa para consulta de precios consolidados.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import ccxt
import aiohttp
import socket
import urllib.request
from ..utils import Config, setup_logger
from .argentine_exchanges import (
    ArgentineExchangeBase,
    RipioTradeAPI,
    CryptoMarketAPI,
    BitsoAPI,
    IOLAPI,
    CriptoYaAPI,
    create_argentine_exchange,
)

logger = setup_logger("api.exchanges")


def get_public_ip() -> str:
    """
    Obtiene la IP pública actual del servidor.
    Usa múltiples servicios como fallback.
    """
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com',
    ]
    
    for service in services:
        try:
            req = urllib.request.Request(service, headers={'User-Agent': 'curl/7.68.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                if ip:
                    return ip
        except Exception:
            continue
    
    # Fallback: intentar obtener IP local
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Desconocida"


# ===========================================
# CONFIGURACIÓN DE EXCHANGES SOPORTADOS
# ===========================================
SUPPORTED_EXCHANGES = {
    # Internacionales
    'binance': {
        'ccxt_id': 'binance',
        'name': 'Binance',
        'testnet_available': True,
        'min_order_usdt': 5,
        'pairs': ['USDT/ARS', 'BTC/USDT', 'ETH/USDT'],
    },
    'binance_testnet': {
        'ccxt_id': 'binance',
        'name': 'Binance Testnet',
        'testnet_available': True,
        'min_order_usdt': 5,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'bybit': {
        'ccxt_id': 'bybit',
        'name': 'Bybit',
        'testnet_available': True,
        'min_order_usdt': 1,
        'pairs': ['BTC/USDT', 'ETH/USDT', 'XRP/USDT'],  # Bybit no tiene ARS
    },
    'okx': {
        'ccxt_id': 'okx',
        'name': 'OKX',
        'testnet_available': False,
        'min_order_usdt': 5,
        'pairs': ['BTC/USDT', 'ETH/USDT'],  # OKX no tiene ARS para usuarios internacionales
    },
    'kucoin': {
        'ccxt_id': 'kucoin',
        'name': 'KuCoin',
        'testnet_available': False,
        'min_order_usdt': 2,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'gateio': {
        'ccxt_id': 'gateio',
        'name': 'Gate.io',
        'testnet_available': False,
        'min_order_usdt': 1,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'huobi': {
        'ccxt_id': 'huobi',
        'name': 'Huobi (HTX)',
        'testnet_available': False,
        'min_order_usdt': 5,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'bitget': {
        'ccxt_id': 'bitget',
        'name': 'Bitget',
        'testnet_available': False,
        'min_order_usdt': 2,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'mexc': {
        'ccxt_id': 'mexc',
        'name': 'MEXC',
        'testnet_available': False,
        'min_order_usdt': 5,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    'crypto_com': {
        'ccxt_id': 'cryptocom',
        'name': 'Crypto.com',
        'testnet_available': False,
        'min_order_usdt': 10,
        'pairs': ['USDT/ARS', 'BTC/USDT'],
    },
    # Argentinos
    'buenbit': {
        'ccxt_id': 'buenbit',
        'name': 'Buenbit',
        'testnet_available': False,
        'min_order_ars': 1000,
        'pairs': ['USDT/ARS', 'BTC/ARS', 'ETH/ARS'],
    },
    'ripio': {
        'ccxt_id': 'ripio',
        'name': 'Ripio',
        'testnet_available': False,
        'min_order_ars': 500,
        'pairs': ['USDT/ARS', 'BTC/ARS'],
    },
    'satoshi': {
        'ccxt_id': 'satoshi',
        'name': 'SatoshiTango',
        'testnet_available': False,
        'min_order_ars': 1000,
        'pairs': ['USDT/ARS', 'BTC/ARS'],
    },
    'lemon': {
        'ccxt_id': 'lemon',
        'name': 'Lemon Cash',
        'testnet_available': False,
        'min_order_ars': 500,
        'pairs': ['USDT/ARS', 'BTC/ARS'],
    },
    'belo': {
        'ccxt_id': 'belo',
        'name': 'Belo',
        'testnet_available': False,
        'min_order_ars': 1000,
        'pairs': ['USDT/ARS', 'BTC/ARS'],
    },
    'p2p': {
        'ccxt_id': 'p2p',
        'name': 'Binance P2P',
        'testnet_available': False,
        'min_order_ars': 1000,
        'pairs': ['USDT/ARS'],
    },
}


class ExchangeBase(ABC):
    """Clase base para todos los exchanges."""
    
    def __init__(self, config: Config, exchange_id: str):
        self.config = config
        self.exchange_id = exchange_id
        self.exchange_info = SUPPORTED_EXCHANGES.get(exchange_id, {})
        self.name = self.exchange_info.get('name', exchange_id)
        self.session: Optional[aiohttp.ClientSession] = None
        self.exchange: Optional[ccxt.Exchange] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establece conexión con el exchange."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Cierra la conexión con el exchange."""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        pass
    
    @abstractmethod
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float
    ) -> Dict:
        """Crea una orden de mercado."""
        pass
    
    @abstractmethod
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Dict:
        """Crea una orden limit."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Obtiene el estado de una orden."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancela una orden."""
        pass
    
    @abstractmethod
    async def get_trades_history(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict]:
        """Obtiene el historial de operaciones."""
        pass
    
    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[Dict]:
        """Obtiene velas japonesas (klines/candlesticks)."""
        pass
    
    def get_min_order(self) -> float:
        """Obtiene el monto mínimo de orden."""
        return self.exchange_info.get('min_order_usdt', self.exchange_info.get('min_order_ars', 5))
    
    def is_testnet(self) -> bool:
        """Verifica si es testnet."""
        return self.exchange_info.get('testnet_available', False) and self.exchange_id.endswith('_testnet')

    async def get_deposit_address(self, currency: str, network: Optional[str] = None) -> Dict:
        if not self.exchange:
            raise NotImplementedError(f"{self.name} no tiene una conexión CCXT activa")
        params = {'network': network} if network else {}
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: self.exchange.fetch_deposit_address(currency, params))
        return {'address': result.get('address'), 'tag': result.get('tag'), 'network': result.get('network', network)}

    async def withdraw(self, currency: str, amount: float, address: str, network: Optional[str] = None, tag: Optional[str] = None) -> Dict:
        if not self.exchange:
            raise NotImplementedError(f"{self.name} no tiene una conexión CCXT activa")
        params = {'network': network} if network else {}
        return await asyncio.get_event_loop().run_in_executor(None, lambda: self.exchange.withdraw(currency, amount, address, tag, params))


class BinanceAPI(ExchangeBase):
    """Conexión con Binance usando CCXT."""
    
    def __init__(self, config: Config):
        super().__init__(config, 'binance_testnet' if config.binance_testnet else 'binance')
    
    async def connect(self) -> bool:
        """Conecta con Binance."""
        try:
            self.exchange = ccxt.binance({
                'apiKey': self.config.binance_api_key,
                'secret': self.config.binance_api_secret,
                'sandbox': self.config.binance_testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                }
            })
            
            await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.load_markets
            )
            
            logger.info(f"✅ Conectado a {self.name} ({'TESTNET' if self.config.binance_testnet else 'MAINNET'})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Desconecta de Binance."""
        if self.exchange:
            try:
                # CCXT usa close() para cerrar la sesión
                await asyncio.get_event_loop().run_in_executor(
                    None, self.exchange.close
                )
            except AttributeError:
                # Algunos exchanges no tienen el método close
                pass
            except Exception:
                pass
            logger.info(f"🔌 Desconectado de {self.name}")
    
    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            balance = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_balance
            )
            return balance.get(currency, {}).get('free', 0)
        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency}: {e}")
            return 0
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            ticker = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.exchange.fetch_ticker(symbol)
            )
            return {
                'symbol': symbol,
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'last': ticker.get('last', 0),
                'volume': ticker.get('baseVolume', 0),
                'timestamp': ticker.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol}: {e}")
            return {}
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            orderbook = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.exchange.fetch_order_book(symbol, limit)
            )
            return {
                'symbol': symbol,
                'bids': orderbook.get('bids', [])[:limit],
                'asks': orderbook.get('asks', [])[:limit],
                'timestamp': orderbook.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"Error obteniendo orderbook de {symbol}: {e}")
            return {}
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float
    ) -> Dict:
        """Crea una orden de mercado."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.create_market_order(symbol, side, amount)
            )
            logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error creando orden de mercado en {self.name}: {e}")
            return {'error': str(e)}
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Dict:
        """Crea una orden limit."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.create_limit_order(symbol, side, amount, price)
            )
            logger.info(f"📦 Orden limit {side} creada en {self.name}: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}
    
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Obtiene el estado de una orden."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_order(order_id, symbol)
            )
            return {
                'id': order.get('id'),
                'status': order.get('status'),
                'side': order.get('side'),
                'amount': order.get('amount'),
                'filled': order.get('filled'),
                'price': order.get('price'),
                'average': order.get('average'),
            }
        except Exception as e:
            logger.error(f"Error obteniendo estado de orden: {e}")
            return {}
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancela una orden."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.cancel_order(order_id, symbol)
            )
            logger.info(f"❌ Orden cancelada en {self.name}: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelando orden: {e}")
            return False
    
    async def get_trades_history(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[Dict]:
        """Obtiene el historial de operaciones."""
        try:
            trades = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_my_trades(symbol, limit=limit)
            )
            return trades
        except Exception as e:
            logger.error(f"Error obteniendo historial de trades: {e}")
            return []
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[Dict]:
        """Obtiene velas japonesas."""
        try:
            klines = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_ohlcv(symbol, interval, since=since, limit=limit)
            )
            
            return [
                {
                    'timestamp': k[0],
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5],
                }
                for k in klines
            ]
        except Exception as e:
            logger.error(f"Error obteniendo klines: {e}")
            return []


class GenericExchangeAPI(ExchangeBase):
    """
    Clase genérica para cualquier exchange soportado por CCXT.
    Usada para Bybit, OKX, KuCoin, Gate.io, etc.
    """

    def __init__(self, config: Config, exchange_id: str, api_key: str, api_secret: str):
        super().__init__(config, exchange_id)
        self.api_key = api_key
        self.api_secret = api_secret
        self.ccxt_id = self.exchange_info.get('ccxt_id', exchange_id)
        
        # OKX requiere passphrase adicional
        self.password = config.get(f"{exchange_id.upper()}_PASSWORD", "")
    
    async def connect(self) -> bool:
        """Conecta con el exchange."""
        try:
            # Validar credenciales antes de conectar
            if not self.api_key or not self.api_secret:
                logger.error(f"❌ Credenciales inválidas para {self.name} (API key o secret vacíos)")
                return False
            
            # Limpiar y validar credenciales
            api_key = str(self.api_key).strip()
            api_secret = str(self.api_secret).strip()
            
            if not api_key or not api_secret:
                logger.error(f"❌ Credenciales inválidas para {self.name} después de limpiar")
                return False
            
            # Algunos exchanges requieren passphrase (OKX, KuCoin, Gate.io)
            exchange_options = {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            }
            
            # Agregar passphrase si es requerido
            if self.password:
                exchange_options['password'] = self.password.strip()
            
            # Debug: mostrar longitud de credenciales (no el valor completo)
            logger.debug(f"Conectando a {self.name}: API key len={len(api_key)}, Secret len={len(api_secret)}")

            exchange_class = getattr(ccxt, self.ccxt_id, None)

            if not exchange_class:
                logger.error(f"Exchange {self.ccxt_id} no soportado por CCXT")
                return False

            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': exchange_options
            })

            # Cargar mercados con manejo de errores específico para OKX
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.exchange.load_markets
                )
            except TypeError as e:
                if "NoneType" in str(e):
                    # Bug conocido de CCXT con OKX - intentar sin cargar mercados
                    logger.warning(f"⚠️ {self.name}: Error cargando mercados (bug CCXT), continuando...")
                else:
                    raise

            logger.info(f"✅ Conectado a {self.name}")
            return True

        except ccxt.AuthenticationError as e:
            logger.error(f"❌ Error de autenticación en {self.name}: {e}")
            logger.error(f"   → Verifica API Key, Secret, Passphrase (si aplica), e IP autorizada")
            return False
        except ccxt.NetworkError as e:
            logger.error(f"❌ Error de red en {self.name}: {e}")
            return False
        except Exception as e:
            error_msg = str(e)
            # Detectar errores específicos
            if "Unmatched IP" in error_msg or "invalid API key" in error_msg.lower():
                logger.error(f"❌ Error de API en {self.name}: {e}")
                logger.error(f"   → Verifica que tu IP esté autorizada en el exchange")
            elif "NoneType" in error_msg or "unsupported operand" in error_msg:
                logger.error(f"❌ Error de credenciales en {self.name}: Credenciales inválidas o incompletas")
                logger.error(f"   → Verifica tu API_KEY y API_SECRET en el archivo .env (sin espacios)")
                if self.ccxt_id in ['okx', 'kucoin', 'gateio']:
                    logger.error(f"   → {self.name} requiere PASSPHRASE. Agrega {self.exchange_id.upper()}_PASSWORD a tu .env")
                logger.error(f"   → Error técnico: {error_msg}")
            else:
                logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Desconecta del exchange."""
        if self.exchange:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.exchange.close
                )
            except (AttributeError, Exception):
                # Algunos exchanges no tienen el método close
                pass
            logger.info(f"🔌 Desconectado de {self.name}")
    
    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            balance = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_balance
            )
            return balance.get(currency, {}).get('free', 0)
        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            ticker = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.exchange.fetch_ticker(symbol)
            )
            return {
                'symbol': symbol,
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'last': ticker.get('last', 0),
                'volume': ticker.get('baseVolume', 0),
                'timestamp': ticker.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            orderbook = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.exchange.fetch_order_book(symbol, limit)
            )
            return {
                'symbol': symbol,
                'bids': orderbook.get('bids', [])[:limit],
                'asks': orderbook.get('asks', [])[:limit],
                'timestamp': orderbook.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"Error obteniendo orderbook de {symbol} en {self.name}: {e}")
            return {}
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float
    ) -> Dict:
        """Crea una orden de mercado."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.create_market_order(symbol, side, amount)
            )
            logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error creando orden de mercado en {self.name}: {e}")
            return {'error': str(e)}
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Dict:
        """Crea una orden limit."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.create_limit_order(symbol, side, amount, price)
            )
            logger.info(f"📦 Orden limit {side} creada en {self.name}: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}
    
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Obtiene el estado de una orden."""
        try:
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_order(order_id, symbol)
            )
            return {
                'id': order.get('id'),
                'status': order.get('status'),
                'side': order.get('side'),
                'amount': order.get('amount'),
                'filled': order.get('filled'),
                'price': order.get('price'),
                'average': order.get('average'),
            }
        except Exception as e:
            logger.error(f"Error obteniendo estado de orden en {self.name}: {e}")
            return {}
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancela una orden."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.cancel_order(order_id, symbol)
            )
            logger.info(f"❌ Orden cancelada en {self.name}: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelando orden en {self.name}: {e}")
            return False
    
    async def get_trades_history(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[Dict]:
        """Obtiene el historial de operaciones."""
        try:
            trades = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_my_trades(symbol, limit=limit)
            )
            return trades
        except Exception as e:
            logger.error(f"Error obteniendo historial de trades en {self.name}: {e}")
            return []
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[Dict]:
        """Obtiene velas japonesas."""
        try:
            klines = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.exchange.fetch_ohlcv(symbol, interval, since=since, limit=limit)
            )
            
            return [
                {
                    'timestamp': k[0],
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5],
                }
                for k in klines
            ]
        except Exception as e:
            logger.error(f"Error obteniendo klines en {self.name}: {e}")
            return []


class ExchangeManager:
    """
    Gestiona las conexiones con múltiples exchanges.
    Permite arbitraje entre cualquier par de exchanges configurados.
    Soporta exchanges internacionales (CCXT) y argentinos (API nativa).
    """

    def __init__(self, config: Config):
        self.config = config
        self.exchanges: Dict[str, ExchangeBase] = {}
        self.argentine_exchanges: Dict[str, ArgentineExchangeBase] = {}
        self.binance: Optional[BinanceAPI] = None
        self.criptoya: Optional[CriptoYaAPI] = None

    async def connect_all(self) -> bool:
        """Conecta todos los exchanges configurados."""
        # Mostrar IP pública al inicio
        public_ip = get_public_ip()
        logger.info(f"🌐 IP Pública detectada: {public_ip}")
        logger.info(f"   → Agrega esta IP a tus APIs de Bybit/OKX si es necesario")

        # Conectar Binance (principal)
        self.binance = BinanceAPI(self.config)
        binance_connected = await self.binance.connect()

        if binance_connected:
            self.exchanges['binance'] = self.binance

        # Conectar exchanges adicionales configurados (internacionales)
        additional_exchanges = self.config.get_additional_exchanges()
        failed_exchanges = []

        for exchange_id, credentials in additional_exchanges.items():
            try:
                api_key = credentials.get('api_key')
                api_secret = credentials.get('api_secret')

                # Validar credenciales antes de crear el exchange
                if not api_key or not api_secret:
                    logger.warning(f"⚠️ {exchange_id.upper()}: Credenciales incompletas, saltando...")
                    failed_exchanges.append(exchange_id)
                    continue

                exchange = GenericExchangeAPI(
                    self.config,
                    exchange_id,
                    api_key,
                    api_secret
                )

                if await exchange.connect():
                    self.exchanges[exchange_id] = exchange
                    logger.info(f"✅ Exchange {exchange.name} añadido al pool")
                else:
                    failed_exchanges.append(exchange_id)
            except Exception as e:
                logger.error(f"Error conectando {exchange_id}: {e}")
                failed_exchanges.append(exchange_id)

        # Conectar exchange argentino principal (usando API nativa)
        argentine_exchange_id = self.config.argentine_exchange.lower()
        native_argentine_exchanges = ['ripio', 'cryptomarket', 'bitso', 'iol']
        
        if argentine_exchange_id in native_argentine_exchanges:
            # Usar implementación nativa para exchanges argentinos soportados
            try:
                argentine = create_argentine_exchange(self.config, argentine_exchange_id)
                if argentine and await argentine.connect():
                    self.argentine_exchanges[argentine_exchange_id] = argentine
                    self.exchanges[argentine_exchange_id] = argentine
                    logger.info(f"✅ Exchange argentino {argentine.name} añadido al pool (API nativa)")
                else:
                    failed_exchanges.append(argentine_exchange_id)
            except Exception as e:
                logger.error(f"Error conectando exchange argentino {argentine_exchange_id}: {e}")
                failed_exchanges.append(argentine_exchange_id)
        elif self.config.argentine_api_key and self.config.argentine_api_secret:
            # Fallback: intentar con GenericExchangeAPI para exchanges legacy
            try:
                argentine = GenericExchangeAPI(
                    self.config,
                    argentine_exchange_id,
                    self.config.argentine_api_key,
                    self.config.argentine_api_secret
                )

                if await argentine.connect():
                    self.exchanges[argentine_exchange_id] = argentine
                    logger.info(f"✅ Exchange argentino {argentine.name} añadido al pool (CCXT)")
            except Exception as e:
                logger.error(f"Error conectando exchange argentino: {e}")

        # Conectar CriptoYa para consulta de precios consolidados
        self.criptoya = CriptoYaAPI()
        await self.criptoya.connect()

        logger.info(f"📊 Total de exchanges conectados: {len(self.exchanges)}")

        if failed_exchanges:
            logger.warning(f"⚠️ Exchanges fallidos: {', '.join(failed_exchanges)}")
            logger.warning(f"   → Verifica credenciales e IP autorizada ({public_ip})")

        return len(self.exchanges) >= 2  # Al menos 2 para arbitraje

    async def disconnect_all(self) -> None:
        """Desconecta todos los exchanges."""
        for exchange_id, exchange in list(self.exchanges.items()):
            await exchange.disconnect()
            del self.exchanges[exchange_id]
        
        for exchange_id, exchange in list(self.argentine_exchanges.items()):
            await exchange.disconnect()
            del self.argentine_exchanges[exchange_id]
        
        if self.criptoya:
            await self.criptoya.disconnect()
        
        self.binance = None
        logger.info("🔌 Todos los exchanges desconectados")
    
    def get_exchange(self, exchange_id: str) -> Optional[ExchangeBase]:
        """Obtiene un exchange por ID."""
        return self.exchanges.get(exchange_id)
    
    def get_all_exchanges(self) -> List[str]:
        """Devuelve la lista de exchanges conectados."""
        return list(self.exchanges.keys())
    
    async def get_arbitrage_opportunities(self) -> List[Dict]:
        """
        Busca oportunidades de arbitraje entre todos los exchanges.
        Usa CriptoYa para obtener precios consolidados de exchanges argentinos.
        Returns:
            Lista de oportunidades ordenadas por profit estimado
        """
        opportunities = []

        # Primero, intentar obtener oportunidades desde CriptoYa (precios consolidados)
        if self.criptoya:
            try:
                criptoya_opps = await self.criptoya.get_usdt_arbitrage()
                if criptoya_opps:
                    logger.debug(f"CriptoYa encontró {len(criptoya_opps)} oportunidades")
                    # Agregar timestamp a las oportunidades de CriptoYa
                    for opp in criptoya_opps:
                        opp['timestamp'] = datetime.now().isoformat()
                        opp['source'] = 'criptoya'
                    opportunities.extend(criptoya_opps)
            except Exception as e:
                logger.debug(f"Error obteniendo arbitraje de CriptoYa: {e}")

        # También buscar arbitraje directo entre Binance y exchange argentino principal
        ars_supported_exchanges = ['binance', self.config.argentine_exchange]

        # Obtener precios solo de exchanges con USDT/ARS
        prices = {}
        for exchange_id in ars_supported_exchanges:
            exchange = self.exchanges.get(exchange_id)
            if not exchange:
                continue
            try:
                ticker = await exchange.get_ticker('USDT/ARS')
                if ticker and ticker.get('bid', 0) > 0 and ticker.get('ask', 0) > 0:
                    prices[exchange_id] = {
                        'bid': ticker.get('bid', 0),
                        'ask': ticker.get('ask', 0),
                        'last': ticker.get('last', 0),
                    }
            except Exception as e:
                logger.debug(f"Error obteniendo USDT/ARS en {exchange_id}: {e}")

        # Si hay precios directos, compararlos
        if len(prices) >= 2:
            exchange_ids = list(prices.keys())

            for i in range(len(exchange_ids)):
                for j in range(i + 1, len(exchange_ids)):
                    ex1 = exchange_ids[i]
                    ex2 = exchange_ids[j]

                    p1 = prices[ex1]
                    p2 = prices[ex2]

                    if not all([p1.get('bid'), p1.get('ask'), p2.get('bid'), p2.get('ask')]):
                        continue

                    # Opción 1: Comprar en ex1, vender en ex2
                    spread_1_2 = p2['bid'] - p1['ask']
                    spread_1_2_pct = (spread_1_2 / p1['ask']) * 100 if p1['ask'] > 0 else 0

                    # Opción 2: Comprar en ex2, vender en ex1
                    spread_2_1 = p1['bid'] - p2['ask']
                    spread_2_1_pct = (spread_2_1 / p2['ask']) * 100 if p2['ask'] > 0 else 0

                    # Considerar comisiones (~0.1% por operación)
                    fees_pct = 0.2

                    if spread_1_2_pct > fees_pct + self.config.min_profit_percent:
                        opportunities.append({
                            'buy_exchange': ex1,
                            'sell_exchange': ex2,
                            'buy_price': p1['ask'],
                            'sell_price': p2['bid'],
                            'spread': spread_1_2,
                            'spread_percent': spread_1_2_pct,
                            'estimated_profit_percent': spread_1_2_pct - fees_pct,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'direct',
                        })

                    if spread_2_1_pct > fees_pct + self.config.min_profit_percent:
                        opportunities.append({
                            'buy_exchange': ex2,
                            'sell_exchange': ex1,
                            'buy_price': p2['ask'],
                            'sell_price': p1['bid'],
                        'spread': spread_2_1,
                        'spread_percent': spread_2_1_pct,
                        'estimated_profit_percent': spread_2_1_pct - fees_pct,
                        'timestamp': datetime.now().isoformat(),
                    })
        
        # Ordenar por profit estimado (mayor a menor)
        opportunities.sort(key=lambda x: x['estimated_profit_percent'], reverse=True)
        
        return opportunities
    
    async def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """Obtiene balances de todos los exchanges."""
        balances = {}
        
        for exchange_id, exchange in self.exchanges.items():
            try:
                usdt = await exchange.get_balance('USDT')
                ars = await exchange.get_balance('ARS')
                balances[exchange_id] = {
                    'USDT': usdt,
                    'ARS': ars,
                }
            except Exception as e:
                logger.error(f"Error obteniendo balance de {exchange_id}: {e}")
                balances[exchange_id] = {'USDT': 0, 'ARS': 0}
        
        return balances
    
    async def get_total_balance_usdt(self) -> float:
        """Calcula el balance total en USDT."""
        total = 0
        
        for exchange_id, exchange in self.exchanges.items():
            try:
                usdt = await exchange.get_balance('USDT')
                total += usdt
            except Exception as e:
                logger.error(f"Error calculando balance total: {e}")
        
        return total
