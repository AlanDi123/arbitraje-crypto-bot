"""
Módulo de conexión con exchanges argentinos.
Soporta: IOL (InvertirOnline), Ripio Trade, CryptoMarket, Bitso, MEXC.
Incluye CriptoYa para consulta de precios consolidados.
"""

import asyncio
import hmac
import hashlib
import base64
import time
import urllib.parse
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from datetime import datetime
import aiohttp
from ..utils import Config, setup_logger

logger = setup_logger("api.argentine_exchanges")


class ArgentineExchangeBase(ABC):
    """Clase base para exchanges argentinos."""

    def __init__(self, config: Config, exchange_id: str):
        self.config = config
        self.exchange_id = exchange_id
        self.session: Optional[aiohttp.ClientSession] = None
        self.name = exchange_id.upper()

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


class RipioTradeAPI(ArgentineExchangeBase):
    """
    Conexión con Ripio Trade API v4.
    Documentación: https://apidocs.ripiotrade.co/
    """

    def __init__(self, config: Config):
        super().__init__(config, 'ripio')
        self.base_url = "https://api.ripiotrade.co/v4"
        self.api_key = config.get("RIPIO_API_KEY", "")
        self.secret_key = config.get("RIPIO_SECRET_KEY", "")
        self.pair = "USDT_ARS"

    async def connect(self) -> bool:
        """Conecta con Ripio Trade."""
        try:
            if not self.api_key or not self.secret_key:
                logger.error("❌ Credenciales de Ripio inválidas")
                return False

            self.session = aiohttp.ClientSession()
            
            # Probar conexión con endpoint público
            async with self.session.get(f"{self.base_url}/public/tickers/{self.pair}") as response:
                if response.status == 200:
                    logger.info(f"✅ Conectado a {self.name} Trade")
                    return True
                else:
                    logger.error(f"❌ Error conectando a {self.name}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False

    async def disconnect(self) -> None:
        """Desconecta de Ripio Trade."""
        if self.session:
            await self.session.close()
            logger.info(f"🔌 Desconectado de {self.name}")

    def _generate_signature(self, method: str, path: str, payload: str = "") -> str:
        """Genera firma HMAC-SHA256 para autenticación."""
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method}{path}{payload}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).base64encode()
        return signature.decode(), timestamp

    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            if not self.session:
                return 0

            path = "/v4/wallet/balances"
            payload = ""
            signature, timestamp = self._generate_signature("GET", path, payload)

            headers = {
                "Authorization": self.api_key,
                "Timestamp": timestamp,
                "Signature": signature,
                "Content-Type": "application/json"
            }

            async with self.session.get(
                f"{self.base_url}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Buscar balance de USDT o ARS
                    for balance in data.get('data', []):
                        if balance.get('currency') == currency:
                            return float(balance.get('available', 0))
                return 0

        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0

    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            if not self.session:
                return {}

            # Mapear símbolo a formato Ripio (USDT/ARS -> USDT_ARS)
            ripio_pair = symbol.replace("/", "_")
            
            async with self.session.get(
                f"{self.base_url}/public/tickers/{ripio_pair}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': symbol,
                        'bid': float(data.get('bid', 0)),
                        'ask': float(data.get('ask', 0)),
                        'last': float(data.get('last', 0)),
                        'volume': float(data.get('volume', 0)),
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            if not self.session:
                return {}

            ripio_pair = symbol.replace("/", "_")
            
            async with self.session.get(
                f"{self.base_url}/public/orders/level-2",
                params={"pair": ripio_pair, "limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    orderbook = data.get('data', {})
                    return {
                        'symbol': symbol,
                        'bids': orderbook.get('buy_orders', [])[:limit],
                        'asks': orderbook.get('sell_orders', [])[:limit],
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            ripio_pair = symbol.replace("/", "_")
            payload = {
                "amount": str(amount),
                "pair": ripio_pair,
                "side": side,
                "type": "market"
            }
            payload_str = str(payload).replace("'", '"')
            path = "/v4/orders"
            signature, timestamp = self._generate_signature("POST", path, payload_str)

            headers = {
                "Authorization": self.api_key,
                "Timestamp": timestamp,
                "Signature": signature,
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            ripio_pair = symbol.replace("/", "_")
            payload = {
                "amount": str(amount),
                "pair": ripio_pair,
                "price": str(price),
                "side": side,
                "type": "limit"
            }
            payload_str = str(payload).replace("'", '"')
            path = "/v4/orders"
            signature, timestamp = self._generate_signature("POST", path, payload_str)

            headers = {
                "Authorization": self.api_key,
                "Timestamp": timestamp,
                "Signature": signature,
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden limit {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}


class CryptoMarketAPI(ArgentineExchangeBase):
    """
    Conexión con CryptoMarket API v3.
    Documentación: https://api.exchange.cryptomkt.com/
    """

    def __init__(self, config: Config):
        super().__init__(config, 'cryptomarket')
        self.base_url = "https://api.exchange.cryptomkt.com/api/3"
        self.api_key = config.get("CRYPTOMARKET_API_KEY", "")
        self.secret_key = config.get("CRYPTOMARKET_SECRET_KEY", "")
        self.pair = "USDTARS"  # Formato CryptoMarket

    async def connect(self) -> bool:
        """Conecta con CryptoMarket."""
        try:
            if not self.api_key or not self.secret_key:
                logger.error("❌ Credenciales de CryptoMarket inválidas")
                return False

            self.session = aiohttp.ClientSession()
            
            # Probar conexión con endpoint público
            async with self.session.get(f"{self.base_url}/public/symbol") as response:
                if response.status == 200:
                    logger.info(f"✅ Conectado a {self.name}")
                    return True
                else:
                    logger.error(f"❌ Error conectando a {self.name}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False

    async def disconnect(self) -> None:
        """Desconecta de CryptoMarket."""
        if self.session:
            await self.session.close()
            logger.info(f"🔌 Desconectado de {self.name}")

    def _generate_signature(self, method: str, path: str, body: str = "") -> str:
        """Genera firma HS256 para autenticación."""
        timestamp = str(int(time.time() * 1000))
        message = f"{method}{path}{body}{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Formato: base64(api_key:signature:timestamp)
        auth_data = f"{self.api_key}:{signature}:{timestamp}"
        return base64.b64encode(auth_data.encode()).decode()

    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            if not self.session:
                return 0

            path = "/spot/balance"
            signature = self._generate_signature("GET", path)

            headers = {
                "Authorization": f"HS256 {signature}",
                "Content-Type": "application/json"
            }

            async with self.session.get(
                f"{self.base_url}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Buscar balance
                    for balance in data:
                        if balance.get('currency') == currency:
                            return float(balance.get('available', 0))
                return 0

        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0

    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            if not self.session:
                return {}

            # Mapear símbolo a formato CryptoMarket (USDT/ARS -> USDTARS)
            cm_pair = symbol.replace("/", "")
            
            async with self.session.get(
                f"{self.base_url}/public/ticker/{cm_pair}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ticker = data.get(cm_pair, {})
                    return {
                        'symbol': symbol,
                        'bid': float(ticker.get('bid', 0)),
                        'ask': float(ticker.get('ask', 0)),
                        'last': float(ticker.get('last', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            if not self.session:
                return {}

            cm_pair = symbol.replace("/", "")
            
            async with self.session.get(
                f"{self.base_url}/public/orderbook/{cm_pair}",
                params={"depth": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    orderbook = data.get(cm_pair, {})
                    return {
                        'symbol': symbol,
                        'bids': orderbook.get('bids', [])[:limit],
                        'asks': orderbook.get('asks', [])[:limit],
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            cm_pair = symbol.replace("/", "")
            payload = {
                "symbol": cm_pair,
                "side": side,
                "quantity": str(amount),
                "type": "market"
            }
            payload_str = str(payload).replace("'", '"')
            path = "/spot/order"
            signature = self._generate_signature("POST", path, payload_str)

            headers = {
                "Authorization": f"HS256 {signature}",
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            cm_pair = symbol.replace("/", "")
            payload = {
                "symbol": cm_pair,
                "side": side,
                "quantity": str(amount),
                "price": str(price),
                "type": "limit"
            }
            payload_str = str(payload).replace("'", '"')
            path = "/spot/order"
            signature = self._generate_signature("POST", path, payload_str)

            headers = {
                "Authorization": f"HS256 {signature}",
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden limit {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}


class BitsoAPI(ArgentineExchangeBase):
    """
    Conexión con Bitso API v1.
    Documentación: https://docs.bitso.com/
    Soporta trading en Argentina (USDT/ARS).
    """

    def __init__(self, config: Config):
        super().__init__(config, 'bitso')
        self.base_url = "https://api.bitso.com/v2"
        self.api_key = config.get("BITSO_API_KEY", "")
        self.api_secret = config.get("BITSO_API_SECRET", "")
        self.pair = "usdt_ars"  # Formato Bitso

    async def connect(self) -> bool:
        """Conecta con Bitso."""
        try:
            if not self.api_key or not self.api_secret:
                logger.error("❌ Credenciales de Bitso inválidas")
                return False

            self.session = aiohttp.ClientSession()
            
            # Probar conexión con endpoint público
            async with self.session.get(f"{self.base_url}/ticker") as response:
                if response.status == 200:
                    logger.info(f"✅ Conectado a {self.name}")
                    return True
                else:
                    logger.error(f"❌ Error conectando a {self.name}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False

    async def disconnect(self) -> None:
        """Desconecta de Bitso."""
        if self.session:
            await self.session.close()
            logger.info(f"🔌 Desconectado de {self.name}")

    def _generate_signature(self, nonce: str, method: str, path: str, data: str = "") -> str:
        """Genera firma HMAC-SHA256 para autenticación Bitso."""
        message = f"{nonce}{method}{path}{data}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            if not self.session:
                return 0

            nonce = str(int(time.time() * 1000))
            path = "/account/balance"
            signature = self._generate_signature(nonce, "GET", path)

            headers = {
                "Authorization": f"Bitso {self.api_key}:{nonce}:{signature}",
                "Content-Type": "application/json"
            }

            async with self.session.get(
                f"{self.base_url}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    balances = data.get('data', {}).get('balances', [])
                    for balance in balances:
                        if balance.get('currency') == currency:
                            return float(balance.get('available', 0))
                return 0

        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0

    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            if not self.session:
                return {}

            # Mapear símbolo a formato Bitso (USDT/ARS -> usdt_ars)
            bitso_book = symbol.replace("/", "_").lower()
            
            async with self.session.get(
                f"{self.base_url}/ticker",
                params={"book": bitso_book}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ticker = data.get('payload', {})
                    return {
                        'symbol': symbol,
                        'bid': float(ticker.get('bid', 0)),
                        'ask': float(ticker.get('ask', 0)),
                        'last': float(ticker.get('last', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            if not self.session:
                return {}

            bitso_book = symbol.replace("/", "_").lower()
            
            async with self.session.get(
                f"{self.base_url}/order_book",
                params={"book": bitso_book}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    orderbook = data.get('payload', {})
                    return {
                        'symbol': symbol,
                        'bids': orderbook.get('bids', [])[:limit],
                        'asks': orderbook.get('asks', [])[:limit],
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            bitso_book = symbol.replace("/", "_").lower()
            nonce = str(int(time.time() * 1000))
            path = "/orders"
            
            payload = {
                "book": bitso_book,
                "side": side,
                "type": "market",
                "amount": str(amount)
            }
            payload_str = str(payload).replace("'", '"')
            signature = self._generate_signature(nonce, "POST", path, payload_str)

            headers = {
                "Authorization": f"Bitso {self.api_key}:{nonce}:{signature}",
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            bitso_book = symbol.replace("/", "_").lower()
            nonce = str(int(time.time() * 1000))
            path = "/orders"
            
            payload = {
                "book": bitso_book,
                "side": side,
                "type": "limit",
                "amount": str(amount),
                "price": str(price)
            }
            payload_str = str(payload).replace("'", '"')
            signature = self._generate_signature(nonce, "POST", path, payload_str)

            headers = {
                "Authorization": f"Bitso {self.api_key}:{nonce}:{signature}",
                "Content-Type": "application/json"
            }

            async with self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden limit {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}


class IOLAPI(ArgentineExchangeBase):
    """
    Conexión con IOL (InvertirOnline) API.
    Documentación: https://www.invertironline.com/documentacion-api
    Nota: IOL requiere autenticación OAuth2 y validación desde cuenta de inversión.
    """

    def __init__(self, config: Config):
        super().__init__(config, 'iol')
        self.base_url = "https://api.invertironline.com/api"
        self.api_key = config.get("IOL_API_KEY", "")
        self.api_secret = config.get("IOL_API_SECRET", "")
        self.username = config.get("IOL_USERNAME", "")
        self.password = config.get("IOL_PASSWORD", "")
        self.token: Optional[str] = None
        self.token_expires: float = 0

    async def connect(self) -> bool:
        """Conecta con IOL usando OAuth2."""
        try:
            if not all([self.api_key, self.api_secret, self.username, self.password]):
                logger.error("❌ Credenciales de IOL inválidas (requiere API Key, Secret, Username y Password)")
                return False

            self.session = aiohttp.ClientSession()
            
            # Obtener token OAuth2
            token_data = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
                "client_id": self.api_key,
                "client_secret": self.api_secret
            }

            async with self.session.post(
                f"{self.base_url}/token",
                data=token_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get('access_token')
                    expires_in = data.get('expires_in', 3600)
                    self.token_expires = time.time() + expires_in - 60  # Renovar 1 min antes
                    
                    logger.info(f"✅ Conectado a {self.name} (InvertirOnline)")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"❌ Error autenticando en {self.name}: {error}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False

    async def disconnect(self) -> None:
        """Desconecta de IOL."""
        if self.session:
            await self.session.close()
            logger.info(f"🔌 Desconectado de {self.name}")

    async def _ensure_token(self) -> bool:
        """Asegura tener un token válido."""
        if not self.token or time.time() >= self.token_expires:
            return await self.connect()
        return True

    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            if not self.session or not await self._ensure_token():
                return 0

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            # IOL tiene cuentas separadas para ARS y USD
            account_type = "ars" if currency == "ARS" else "usd"
            
            async with self.session.get(
                f"{self.base_url}/cuentas/posiciones/{account_type}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # IOL devuelve posiciones, buscar saldo disponible
                    return float(data.get('disponible', 0))
                return 0

        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0

    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            if not self.session:
                return {}

            # IOL usa tickers específicos para criptos
            # USDT se opera como "USDT" en el mercado crypto
            async with self.session.get(
                f"{self.base_url}/instrumentos"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Buscar USDT en la lista de instrumentos
                    for inst in data:
                        if inst.get('simbolo') == 'USDT':
                            return {
                                'symbol': symbol,
                                'bid': float(inst.get('precio_venta', 0)),
                                'ask': float(inst.get('precio_compra', 0)),
                                'last': float(inst.get('ultimo_precio', 0)),
                                'volume': float(inst.get('volumen', 0)),
                                'timestamp': int(time.time() * 1000),
                            }
                return {}

        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            if not self.session:
                return {}

            # IOL no expone orderbook público directamente
            # Usar endpoint de profundidad de mercado
            async with self.session.get(
                f"{self.base_url}/instrumentos/USDT/ordenes"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': symbol,
                        'bids': data.get('compra', [])[:limit],
                        'asks': data.get('venta', [])[:limit],
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

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
            if not self.session or not await self._ensure_token():
                return {'error': 'Session not initialized'}

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            payload = {
                "simbolo": "USDT",
                "tipo": "market",
                "lado": side,
                "cantidad": amount
            }

            async with self.session.post(
                f"{self.base_url}/operaciones",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

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
            if not self.session or not await self._ensure_token():
                return {'error': 'Session not initialized'}

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            payload = {
                "simbolo": "USDT",
                "tipo": "limit",
                "lado": side,
                "cantidad": amount,
                "precio": price
            }

            async with self.session.post(
                f"{self.base_url}/operaciones",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Orden limit {side} creada en {self.name}: {data.get('id')}")
                    return data
                else:
                    error = await response.text()
                    return {'error': error}

        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}


class MEXCAPI(ArgentineExchangeBase):
    """
    Conexión con MEXC API v3.
    Documentación: https://www.mexc.com/api-docs/spot-v3/general-info
    MEXC soporta ARS/USDT y depósitos/retiros en ARS sin comisiones.
    """

    def __init__(self, config: Config):
        super().__init__(config, 'mexc')
        self.base_url = "https://api.mexc.com/api/v3"
        self.api_key = config.get("MEXC_API_KEY", "")
        self.api_secret = config.get("MEXC_API_SECRET", "")
        self.pair = "ARSUSDT"  # Formato MEXC (ARS/USDT → ARSUSDT)

    async def connect(self) -> bool:
        """Conecta con MEXC."""
        try:
            if not self.api_key or not self.api_secret:
                logger.error("❌ Credenciales de MEXC inválidas")
                return False

            self.session = aiohttp.ClientSession()
            
            # Probar conexión con endpoint público
            async with self.session.get(f"{self.base_url}/ping") as response:
                if response.status == 200:
                    logger.info(f"✅ Conectado a {self.name}")
                    return True
                else:
                    logger.error(f"❌ Error conectando a {self.name}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error conectando a {self.name}: {e}")
            return False

    async def disconnect(self) -> None:
        """Desconecta de MEXC."""
        if self.session:
            await self.session.close()
            logger.info(f"🔌 Desconectado de {self.name}")

    def _generate_signature(self, query_string: str) -> str:
        """Genera firma HMAC SHA256 para autenticación MEXC."""
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _get_signed(self, path: str, params: Dict = None) -> Dict:
        """Realiza una petición GET firmada."""
        if not params:
            params = {}
        
        timestamp = int(time.time() * 1000)
        params['timestamp'] = timestamp
        params['recvWindow'] = 5000
        
        query_string = urllib.parse.urlencode(params)
        signature = self._generate_signature(query_string)
        
        headers = {
            "X-MEXC-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}?{query_string}&signature={signature}"
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                logger.error(f"Error en {path}: {error}")
                return {}

    async def _post_signed(self, path: str, params: Dict = None) -> Dict:
        """Realiza una petición POST firmada."""
        if not params:
            params = {}
        
        timestamp = int(time.time() * 1000)
        params['timestamp'] = timestamp
        params['recvWindow'] = 5000
        
        query_string = urllib.parse.urlencode(params)
        signature = self._generate_signature(query_string)
        
        headers = {
            "X-MEXC-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}?{query_string}&signature={signature}"
        
        async with self.session.post(url, headers=headers, json=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                logger.error(f"Error en {path}: {error}")
                return {}

    async def get_balance(self, currency: str) -> float:
        """Obtiene el balance de una moneda."""
        try:
            if not self.session:
                return 0

            data = await self._get_signed("/account")
            if data and 'balances' in data:
                for balance in data['balances']:
                    if balance.get('asset') == currency:
                        return float(balance.get('free', 0))
            return 0

        except Exception as e:
            logger.error(f"Error obteniendo balance de {currency} en {self.name}: {e}")
            return 0

    async def get_ticker(self, symbol: str) -> Dict:
        """Obtiene el ticker de un par."""
        try:
            if not self.session:
                return {}

            # Mapear símbolo a formato MEXC (USDT/ARS → ARSUSDT)
            # MEXC usa el formato BASEQUOTE
            if symbol == 'USDT/ARS':
                mexc_symbol = 'ARSUSDT'  # ARS es la base, USDT es la quote
            else:
                mexc_symbol = symbol.replace("/", "").upper()
            
            async with self.session.get(
                f"{self.base_url}/ticker/24hr",
                params={"symbol": mexc_symbol}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': symbol,
                        'bid': float(data.get('bidPrice', 0)),
                        'ask': float(data.get('askPrice', 0)),
                        'last': float(data.get('lastPrice', 0)),
                        'volume': float(data.get('volume', 0)),
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol} en {self.name}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Obtiene el orderbook de un par."""
        try:
            if not self.session:
                return {}

            if symbol == 'USDT/ARS':
                mexc_symbol = 'ARSUSDT'
            else:
                mexc_symbol = symbol.replace("/", "").upper()
            
            async with self.session.get(
                f"{self.base_url}/depth",
                params={"symbol": mexc_symbol, "limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': symbol,
                        'bids': [[float(b[0]), float(b[1])] for b in data.get('bids', [])][:limit],
                        'asks': [[float(a[0]), float(a[1])] for a in data.get('asks', [])][:limit],
                        'timestamp': int(time.time() * 1000),
                    }
                return {}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            if symbol == 'USDT/ARS':
                mexc_symbol = 'ARSUSDT'
            else:
                mexc_symbol = symbol.replace("/", "").upper()

            # MEXC requiere quantity para market orders
            params = {
                "symbol": mexc_symbol,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": str(amount)
            }

            data = await self._post_signed("/order", params)
            
            if data and data.get('orderId'):
                logger.info(f"📦 Orden de mercado {side} creada en {self.name}: {data.get('orderId')}")
                return data
            else:
                return {'error': data.get('msg', 'Error creando orden')}

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
            if not self.session:
                return {'error': 'Session not initialized'}

            if symbol == 'USDT/ARS':
                mexc_symbol = 'ARSUSDT'
            else:
                mexc_symbol = symbol.replace("/", "").upper()

            params = {
                "symbol": mexc_symbol,
                "side": side.upper(),
                "type": "LIMIT",
                "quantity": str(amount),
                "price": str(price),
                "timeInForce": "GTC"
            }

            data = await self._post_signed("/order", params)
            
            if data and data.get('orderId'):
                logger.info(f"📦 Orden limit {side} creada en {self.name}: {data.get('orderId')}")
                return data
            else:
                return {'error': data.get('msg', 'Error creando orden')}

        except Exception as e:
            logger.error(f"Error creando orden limit en {self.name}: {e}")
            return {'error': str(e)}


class CriptoYaAPI:
    """
    API de CriptoYa para consulta de precios consolidados.
    Documentación: https://docs.criptoya.com/
    No requiere autenticación.
    
    Endpoints:
    - /api/{exchange}/{coin}/{fiat}/{volumen} - Precio específico
    - No hay endpoint único para todos los exchanges, hay que consultar uno por uno
    """

    def __init__(self):
        self.base_url = "https://criptoya.com/api"
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = setup_logger("api.criptoya")
        # Lista de exchanges soportados por CriptoYa para ARS
        self.supported_exchanges = [
            'binance', 'cryptomkt', 'bitso', 'ripio', 'buenbit',
            'lemoncash', 'belobit', 'letsbit', 'satoshitango',
            'tiendacrypto', 'fiwind', 'alphabybit', 'universalcoin',
            'eluter', 'p2p', 'huobi', 'kucoin', 'bitget', 'okx',
            'coinex', 'bingx', 'weex', 'trubit', 'paydece'
        ]

    async def connect(self) -> bool:
        """Inicializa la sesión."""
        try:
            self.session = aiohttp.ClientSession()
            self.logger.info("✅ Conectado a CriptoYa (precios consolidados)")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error conectando a CriptoYa: {e}")
            return False

    async def disconnect(self) -> None:
        """Cierra la sesión."""
        if self.session:
            await self.session.close()
            self.logger.info("🔌 Desconectado de CriptoYa")

    async def get_exchange_price(self, exchange: str, coin: str = "USDT", fiat: str = "ARS", volume: float = 0.1) -> Dict:
        """
        Obtiene precio de un exchange específico.
        
        Args:
            exchange: Nombre del exchange (binance, buenbit, letsbit, etc.)
            coin: Criptomoneda (USDT por defecto)
            fiat: Moneda fiat (ARS por defecto)
            volume: Volumen para la consulta (0.1 por defecto)
        
        Returns:
            Dict con precio del exchange
        """
        try:
            if not self.session:
                return {}

            # Formato: /api/{exchange}/{coin}/{fiat}/{volume}
            endpoint = f"{self.base_url}/{exchange}/{coin}/{fiat}/{volume}"
            
            async with self.session.get(endpoint, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        # Algunos exchanges pueden devolver HTML o no tener datos
                        return {}
                    
                    data = await response.json()
                    return {
                        'exchange': exchange,
                        'coin': coin,
                        'fiat': fiat,
                        'bid': float(data.get('bid', 0)),
                        'ask': float(data.get('ask', 0)),
                        'price': float(data.get('ask', 0)),  # Usar ask como precio de referencia
                        'timestamp': data.get('time', int(time.time() * 1000)),
                    }
                return {}

        except asyncio.TimeoutError:
            return {}
        except Exception as e:
            self.logger.debug(f"Error obteniendo precio de {exchange} en CriptoYa: {e}")
            return {}

    async def get_all_prices(self) -> Dict:
        """
        Obtiene precios de USDT de múltiples exchanges argentinos.
        Returns:
            Dict con precios de cada exchange
        """
        try:
            if not self.session:
                return {}

            # Consultar múltiples exchanges en paralelo
            tasks = []
            for exchange in self.supported_exchanges[:10]:  # Limitar a 10 para no saturar
                tasks.append(self.get_exchange_price(exchange))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            prices = {}
            for result in results:
                if isinstance(result, dict) and result.get('exchange'):
                    exchange = result['exchange']
                    prices[exchange] = {
                        'bid': result.get('bid', 0),
                        'ask': result.get('ask', 0),
                        'price': result.get('price', 0),
                        'timestamp': result.get('timestamp', 0),
                    }

            return prices

        except Exception as e:
            self.logger.error(f"Error obteniendo precios de CriptoYa: {e}")
            return {}

    async def get_usdt_arbitrage(self) -> List[Dict]:
        """
        Obtiene oportunidades de arbitraje de USDT entre exchanges argentinos.
        
        Returns:
            Lista de oportunidades ordenadas por spread
        """
        try:
            prices = await self.get_all_prices()
            if not prices:
                return []

            opportunities = []
            exchanges = list(prices.keys())

            for i in range(len(exchanges)):
                for j in range(i + 1, len(exchanges)):
                    ex1 = exchanges[i]
                    ex2 = exchanges[j]

                    p1 = prices[ex1]
                    p2 = prices[ex2]

                    buy_price = p1.get('ask', 0)
                    sell_price = p2.get('bid', 0)

                    if buy_price > 0 and sell_price > 0:
                        spread = sell_price - buy_price
                        spread_pct = (spread / buy_price) * 100 if buy_price > 0 else 0

                        if spread_pct > 0.5:  # Mínimo 0.5% para considerar
                            opportunities.append({
                                'buy_exchange': ex1,
                                'sell_exchange': ex2,
                                'buy_price': buy_price,
                                'sell_price': sell_price,
                                'spread': spread,
                                'spread_percent': spread_pct,
                                'source': 'criptoya',
                            })

            # Ordenar por spread descendente
            opportunities.sort(key=lambda x: x['spread_percent'], reverse=True)
            return opportunities[:5]  # Retornar top 5 oportunidades

        except Exception as e:
            self.logger.error(f"Error calculando arbitraje en CriptoYa: {e}")
            return []


# Factory para crear exchanges argentinos
def create_argentine_exchange(config: Config, exchange_id: str) -> Optional[ArgentineExchangeBase]:
    """
    Crea una instancia de exchange argentino.

    Args:
        config: Configuración del bot
        exchange_id: ID del exchange ('mexc', 'ripio', 'cryptomarket', 'bitso', 'iol')

    Returns:
        Instancia del exchange o None si no es soportado
    """
    exchanges = {
        'mexc': MEXCAPI,
        'ripio': RipioTradeAPI,
        'cryptomarket': CryptoMarketAPI,
        'bitso': BitsoAPI,
        'iol': IOLAPI,
    }

    exchange_class = exchanges.get(exchange_id)
    if exchange_class:
        return exchange_class(config)

    return None
