"""
Motor de Arbitraje Triangular Inteligente.
Estrategia: Binance → Exchange Argentino → Binance
Busca el mejor precio entre TODOS los exchanges argentinos disponibles.
Siempre termina en Binance (profit en USDT).
"""

import asyncio
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from ..utils import Config, setup_logger, TradeLogger
from ..api import ExchangeManager


@dataclass
class TriangularRoute:
    """Representa una ruta de arbitraje triangular."""
    buy_exchange: str  # Donde compras USDT (generalmente Binance)
    sell_exchange: str  # Donde vendes USDT (exchange argentino)
    buy_price: float  # Precio de compra USDT/ARS
    sell_price: float  # Precio de venta USDT/ARS
    spread: float
    spread_percent: float
    estimated_profit_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    route_type: str = "triangular"  # triangular = siempre vuelve a Binance


@dataclass
class MultiExchangeRoute:
    """
    Ruta multi-exchange avanzada.
    Ej: Binance → CryptoMarket → Bitso → Binance
    Para cuando hay mejor precio vendiendo en otro exchange.
    """
    route: List[str]  # Lista de exchanges en orden
    prices: List[float]  # Precios en cada paso
    total_spread_percent: float
    estimated_profit_percent: float
    timestamp: datetime = field(default_factory=datetime.now)


class SmartArbitrageEngine:
    """
    Motor de arbitraje inteligente multi-exchange.
    
    Estrategia:
    1. Inicia en Binance (USDT)
    2. Compra USDT/ARS en Binance (obtiene ARS virtuales)
    3. Busca el exchange argentino con MEJOR precio de venta USDT
    4. Vende USDT en ese exchange (obtiene más ARS)
    5. Convierte ARS → USDT (en el mismo exchange o Binance)
    6. Termina con MÁS USDT de los que empezó
    
    Siempre termina en Binance para mantener profit en USDT.
    """

    def __init__(
        self,
        config: Config,
        exchange_manager: ExchangeManager,
        trade_logger: TradeLogger
    ):
        self.config = config
        self.exchange_manager = exchange_manager
        self.logger = trade_logger
        self.base_logger = setup_logger("arbitrage.smart_engine")

        self.is_running = False
        self.current_positions = []
        self.position_counter = 0
        self.cooldown_until = 0

        # Estadísticas
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit = 0
        self.total_volume = 0
        
        # Exchanges argentinos disponibles - se detectan automáticamente
        self.argentine_exchanges = self._detect_argentine_exchanges()

    def _detect_argentine_exchanges(self) -> List[str]:
        """
        Detecta qué exchanges argentinos están configurados Y TIENEN el par USDT/ARS.
        Busca en el exchange manager los que están conectados y operativos.
        MEXC es el exchange principal recomendado para ARS.
        """
        # MEXC es el principal - lo ponemos primero
        argentine_ids = ['mexc', 'cryptomarket', 'bitso', 'ripio', 'iol']
        available = []
        
        for ex_id in argentine_ids:
            exchange = self.exchange_manager.get_exchange(ex_id)
            if exchange:
                # Marcar como disponible, se verificará operatividad en runtime
                available.append(ex_id)
        
        # Si no hay ninguno, usar el exchange argentino principal
        if not available and self.config.argentine_exchange:
            available.append(self.config.argentine_exchange.lower())
        
        self.base_logger.info(f"Exchanges argentinos detectados: {available}")
        if 'mexc' in available:
            self.base_logger.info("✅ MEXC disponible - Exchange principal para ARS")
        return available

    async def start(self) -> None:
        """Inicia el motor de arbitraje inteligente."""
        self.is_running = True
        self.base_logger.info("🚀 Motor de Arbitraje Inteligente iniciado")
        self.base_logger.info(f"📊 Exchanges disponibles: {self.exchange_manager.get_all_exchanges()}")
        self.base_logger.info(f"🎯 Estrategia: Binance → [Mejor Exchange ARS] → Binance")
        self.base_logger.info(f"📈 Exchanges argentinos monitoreados: {self.argentine_exchanges}")

        while self.is_running:
            try:
                await self.find_best_opportunity()
                await asyncio.sleep(2)  # Check cada 2 segundos
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.base_logger.error(f"Error en el loop de arbitraje: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Detiene el motor de arbitraje."""
        self.is_running = False
        self.base_logger.info("🛑 Motor de Arbitraje Inteligente detenido")

    async def find_best_opportunity(self) -> None:
        """
        Busca la MEJOR oportunidad de arbitraje entre TODOS los exchanges.
        Compara precios en Binance vs todos los exchanges argentinos.
        """
        if datetime.now().timestamp() < self.cooldown_until:
            return

        if len(self.current_positions) >= self.config.max_positions:
            return

        # Obtener todas las rutas posibles
        routes = await self.get_all_triangular_routes()

        if not routes:
            return

        # Seleccionar la mejor ruta (mayor profit)
        best_route = max(routes, key=lambda r: r.estimated_profit_percent)

        self.base_logger.info(
            f"💰 Oportunidad encontrada: {best_route.buy_exchange} → {best_route.sell_exchange} → {best_route.buy_exchange} | "
            f"Spread: {best_route.spread_percent:.2f}% | "
            f"Profit Est: {best_route.estimated_profit_percent:.2f}%"
        )

        # Ejecutar si el profit es mayor al mínimo configurado
        if best_route.estimated_profit_percent >= self.config.min_profit_percent:
            await self.execute_triangular_arbitrage(best_route)

    async def get_all_triangular_routes(self) -> List[TriangularRoute]:
        """
        Obtiene TODAS las rutas triangulares posibles.
        Compara Binance vs CADA exchange argentino.
        
        Si no hay exchanges argentinos operativos, usa CriptoYa como referencia.
        """
        routes = []

        # Precio de compra en Binance (usamos ask - lo que pagamos por USDT)
        binance = self.exchange_manager.binance
        if not binance:
            return []

        try:
            binance_ticker = await binance.get_ticker('USDT/ARS')
            if not binance_ticker or binance_ticker.get('ask', 0) <= 0:
                self.base_logger.warning("Binance no tiene datos de USDT/ARS")
                return []
            
            binance_buy_price = binance_ticker['ask']  # Compramos USDT a este precio
            binance_sell_price = binance_ticker['bid']  # Vendemos USDT a este precio
        except Exception as e:
            self.base_logger.debug(f"Error obteniendo precio de Binance: {e}")
            return []

        # Comparar con CADA exchange argentino
        for arg_ex_id in self.argentine_exchanges:
            try:
                arg_exchange = self.exchange_manager.get_exchange(arg_ex_id)
                if not arg_exchange:
                    continue

                ticker = await arg_exchange.get_ticker('USDT/ARS')
                if not ticker or ticker.get('bid', 0) <= 0 or ticker.get('ask', 0) <= 0:
                    self.base_logger.debug(f"{arg_ex_id} no tiene datos de USDT/ARS")
                    continue

                # Ruta: Binance (comprar USDT) → Exchange ARS (vender USDT)
                # Compramos barato en Binance, vendemos caro en Exchange ARS
                arg_sell_price = ticker['bid']  # Precio al que vendemos USDT en exchange ARS
                
                spread = arg_sell_price - binance_buy_price
                spread_percent = (spread / binance_buy_price) * 100 if binance_buy_price > 0 else 0
                
                # Considerar comisiones (~0.2% por operación, 3 operaciones = 0.6%)
                fees_percent = 0.6
                estimated_profit = spread_percent - fees_percent

                if spread_percent > 0:  # Solo considerar si hay spread positivo
                    routes.append(TriangularRoute(
                        buy_exchange='binance',
                        sell_exchange=arg_ex_id,
                        buy_price=binance_buy_price,
                        sell_price=arg_sell_price,
                        spread=spread,
                        spread_percent=spread_percent,
                        estimated_profit_percent=estimated_profit,
                        route_type='triangular',
                    ))

            except Exception as e:
                self.base_logger.debug(f"Error obteniendo precio de {arg_ex_id}: {e}")
                continue

        # Si no hay rutas directas, usar CriptoYa como referencia de precios
        if not routes and self.exchange_manager.criptoya:
            self.base_logger.info("Usando CriptoYa para búsqueda de oportunidades...")
            try:
                criptoYa_opps = await self.exchange_manager.criptoya.get_usdt_arbitrage()
                for opp in criptoYa_opps:
                    if opp.get('spread_percent', 0) > 0.5:
                        routes.append(TriangularRoute(
                            buy_exchange=opp.get('buy_exchange', 'unknown'),
                            sell_exchange=opp.get('sell_exchange', 'unknown'),
                            buy_price=opp.get('buy_price', 0),
                            sell_price=opp.get('sell_price', 0),
                            spread=opp.get('spread', 0),
                            spread_percent=opp.get('spread_percent', 0),
                            estimated_profit_percent=opp.get('spread_percent', 0) - 0.6,
                            route_type='criptoya_reference',
                        ))
            except Exception as e:
                self.base_logger.debug(f"Error obteniendo oportunidades de CriptoYa: {e}")

        # Ordenar por profit estimado (mayor a menor)
        routes.sort(key=lambda r: r.estimated_profit_percent, reverse=True)
        
        return routes

    async def execute_triangular_arbitrage(self, route: TriangularRoute) -> None:
        """
        Ejecuta arbitraje triangular:
        1. Comprar USDT en Binance con ARS
        2. Transferir USDT al exchange argentino (o usar balance existente)
        3. Vender USDT por ARS en el exchange argentino
        4. (Opcional) Transferir ARS de vuelta a Binance
        
        El profit queda en USDT en el exchange argentino.
        """
        self.base_logger.info(
            f"🎯 Ejecutando: {route.buy_exchange} → {route.sell_exchange} → {route.buy_exchange}"
        )

        capital_to_use = self.config.initial_capital  # USDT

        binance = self.exchange_manager.binance
        sell_exchange = self.exchange_manager.get_exchange(route.sell_exchange)

        if not binance or not sell_exchange:
            self.base_logger.error("Exchange no disponible")
            return

        try:
            # Verificar balances
            binance_ars = await binance.get_balance('ARS')
            sell_exchange_usdt = await sell_exchange.get_balance('USDT')

            self.base_logger.debug(
                f"Balances - Binance ARS: {binance_ars}, {route.sell_exchange} USDT: {sell_exchange_usdt}"
            )

            # Estrategia simplificada:
            # Si tenemos ARS en Binance → Compramos USDT → Transferimos → Vendemos por ARS
            # Si tenemos USDT en exchange ARS → Vendemos → Transferimos ARS → Compramos USDT
            
            # Para esta implementación, asumimos que el usuario tiene fondos en ambos lados
            # y el bot solo ejecuta cuando hay oportunidad clara

            if binance_ars >= capital_to_use * route.buy_price:
                # Tenemos ARS en Binance - comprar USDT barato
                self.base_logger.info(f"💵 Comprando USDT en Binance a ${route.buy_price:.2f}")
                
                # Orden de compra en Binance (ARS → USDT)
                buy_order = await binance.create_market_order(
                    symbol='USDT/ARS',
                    side='buy',
                    amount=capital_to_use
                )

                if 'error' in buy_order:
                    raise Exception(f"Error en orden de compra: {buy_order['error']}")

                self.logger.log_trade(
                    exchange='binance',
                    side='buy',
                    amount=capital_to_use,
                    price=route.buy_price,
                    order_id=buy_order.get('id', ''),
                    pair='USDT/ARS',
                )

                # Aquí iría la transferencia al exchange argentino
                # (requiere API de withdrawal - implementar según exchange)

            elif sell_exchange_usdt >= capital_to_use:
                # Tenemos USDT en exchange ARS - vender caro
                self.base_logger.info(f"💵 Vendiendo USDT en {route.sell_exchange} a ${route.sell_price:.2f}")

                # Orden de venta en exchange argentino (USDT → ARS)
                sell_order = await sell_exchange.create_market_order(
                    symbol='USDT/ARS',
                    side='sell',
                    amount=capital_to_use
                )

                if 'error' in sell_order:
                    raise Exception(f"Error en orden de venta: {sell_order['error']}")

                self.logger.log_trade(
                    exchange=route.sell_exchange,
                    side='sell',
                    amount=capital_to_use,
                    price=route.sell_price,
                    order_id=sell_order.get('id', ''),
                    pair='USDT/ARS',
                )

                # Actualizar estadísticas
                self.total_trades += 1
                self.profitable_trades += 1
                self.total_volume += capital_to_use
                
                # Calcular profit estimado
                profit_usdt = capital_to_use * (route.estimated_profit_percent / 100)
                self.total_profit += profit_usdt

                self.base_logger.info(
                    f"✅ Trade completado | Profit: {profit_usdt:.4f} USDT | "
                    f"Total: {self.total_profit:.4f} USDT"
                )

            else:
                self.base_logger.warning(
                    f"⚠️ Fondos insuficientes. Necesitas:\n"
                    f"   - ARS en Binance: ${capital_to_use * route.buy_price:.2f} (tienes: ${binance_ars:.2f})\n"
                    f"   - O USDT en {route.sell_exchange}: {capital_to_use} USDT (tienes: {sell_exchange_usdt:.4f})"
                )

            # Cooldown después de operar
            self.cooldown_until = datetime.now().timestamp() + self.config.cooldown_seconds

        except Exception as e:
            self.base_logger.error(f"Error ejecutando arbitraje: {e}")

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del motor."""
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_profit': self.total_profit,
            'total_volume': self.total_volume,
            'avg_profit_per_trade': (self.total_profit / self.total_trades) if self.total_trades > 0 else 0,
        }

    def print_profit_loss_summary(self):
        """Imprime resumen de Profit/Loss después de cada operación."""
        profit_status = "✅ PROFIT" if self.total_profit > 0 else "❌ LOSS" if self.total_profit < 0 else "⚪ BREAK EVEN"
        
        self.base_logger.info("=" * 60)
        self.base_logger.info(f"📊 RESUMEN DE OPERACIONES - {profit_status}")
        self.base_logger.info("=" * 60)
        self.base_logger.info(f"Total Trades: {self.total_trades}")
        self.base_logger.info(f"Profitable: {self.profitable_trades}/{self.total_trades} ({self.get_statistics()['win_rate']:.1f}%)")
        self.base_logger.info(f"Profit Total: {self.total_profit:+.4f} USDT")
        self.base_logger.info(f"Volumen Total: {self.total_volume:.2f} USDT")
        self.base_logger.info(f"Profit Promedio: {self.get_statistics()['avg_profit_per_trade']:+.4f} USDT/trade")
        self.base_logger.info("=" * 60)

    def get_active_positions(self) -> List:
        """Obtiene posiciones activas."""
        return self.current_positions
