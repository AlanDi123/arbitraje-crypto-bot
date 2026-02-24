"""
Motor de Arbitraje Triangular Inteligente con Cálculo de Fees.
Estrategia: Binance ↔ MEXC (u otro exchange argentino)
Siempre considera fees de transferencia y trading para calcular rentabilidad REAL.

FEES ACTUALIZADOS (2025-2026):
- MEXC: USDT TRC20 withdrawal = ~1 USDT
- MEXC: ARS deposit = GRATIS (promoción hasta Feb 20, 2026)
- MEXC: Trading fee = 0% maker, 0.05% taker
- Binance: USDT TRC20 withdrawal = ~1 USDT
- Binance: ARS withdrawal = GRATIS (promoción)
- Binance: Trading fee = 0.1% (puede ser menor con BNB)
"""

import asyncio
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from ..utils import Config, setup_logger, TradeLogger
from ..api import ExchangeManager


@dataclass
class FeeStructure:
    """Estructura de fees por exchange."""
    exchange_id: str
    withdrawal_fee_usdt: float  # Fee de retiro en USDT (TRC20)
    withdrawal_fee_ars: float  # Fee de retiro en ARS (banco)
    deposit_fee_ars: float  # Fee de depósito en ARS
    trading_fee_percent: float  # Fee de trading (% del volumen)
    is_promotion: bool = False  # Si hay promoción de fees cero
    promotion_end_date: str = ""  # Fecha de fin de promoción


@dataclass
class TriangularRoute:
    """Representa una ruta de arbitraje triangular con fees incluidos."""
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    amount_usdt: float
    amount_ars_invested: float
    
    # Fees detallados
    trading_fee_buy: float  # Fee en compra (ARS)
    trading_fee_sell: float  # Fee en venta (ARS)
    withdrawal_fee_usdt: float  # Fee de transferencia USDT
    withdrawal_fee_ars: float  # Fee convertido a ARS
    
    # Resultados
    gross_profit_ars: float  # Profit bruto (sin fees)
    total_fees_ars: float  # Total de fees en ARS
    net_profit_ars: float  # Profit neto (con fees)
    net_profit_percent: float  # % de retorno real
    
    timestamp: datetime = field(default_factory=datetime.now)
    is_profitable: bool = False  # Si el profit neto es positivo


@dataclass
class ExchangeBalance:
    """Balance de un exchange."""
    exchange_id: str
    ars: float
    usdt: float
    last_update: datetime = field(default_factory=datetime.now)


class SmartArbitrageEngineWithFees:
    """
    Motor de arbitraje inteligente con cálculo DETALLADO de fees.
    
    Flujo:
    1. Verifica fees actuales de cada exchange
    2. Calcula mínimo necesario para que sea rentable
    3. Busca oportunidades con profit > fees
    4. Ejecuta solo si es rentable
    5. Muestra profit/loss REAL después de fees
    """

    # Fees actualizados (Febrero 2025)
    FEES_DATA = {
        'binance': FeeStructure(
            exchange_id='binance',
            withdrawal_fee_usdt=1.0,  # TRC20
            withdrawal_fee_ars=0.0,  # Promoción ARS
            deposit_fee_ars=0.0,
            trading_fee_percent=0.1,  # 0.1% estándar
            is_promotion=True,
            promotion_end_date='2025-12-31',
        ),
        'mexc': FeeStructure(
            exchange_id='mexc',
            withdrawal_fee_usdt=1.0,  # TRC20
            withdrawal_fee_ars=0.0,  # Promoción hasta Feb 20, 2026
            deposit_fee_ars=0.0,  # Promoción hasta Feb 20, 2026
            trading_fee_percent=0.05,  # 0.05% taker
            is_promotion=True,
            promotion_end_date='2026-02-20',
        ),
        'cryptomarket': FeeStructure(
            exchange_id='cryptomarket',
            withdrawal_fee_usdt=2.0,  # Estimado
            withdrawal_fee_ars=0.0,  # Transferencia bancaria
            deposit_fee_ars=0.0,
            trading_fee_percent=0.5,  # 0.5% estimado
            is_promotion=False,
        ),
        'bitso': FeeStructure(
            exchange_id='bitso',
            withdrawal_fee_usdt=5.0,  # Estimado
            withdrawal_fee_ars=0.0,
            deposit_fee_ars=0.0,
            trading_fee_percent=0.5,
            is_promotion=False,
        ),
    }

    def __init__(
        self,
        config: Config,
        exchange_manager: ExchangeManager,
        trade_logger: TradeLogger,
        simulation_mode: bool = False  # Nuevo parámetro
    ):
        self.config = config
        self.exchange_manager = exchange_manager
        self.logger = trade_logger
        self.base_logger = setup_logger("arbitrage.smart_engine_fees")
        self.simulation_mode = simulation_mode  # Modo simulación

        self.is_running = False
        self.current_positions = []
        self.position_counter = 0
        self.cooldown_until = 0

        # Estadísticas (separadas para simulación)
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit_usdt = 0
        self.total_fees_paid_usdt = 0
        self.total_volume_usdt = 0
        
        # Estadísticas de simulación
        self.simulation_trades = 0
        self.simulation_profit_usdt = 0
        self.simulation_missed_opportunities = 0
        
        # Balances cache
        self.balances: Dict[str, ExchangeBalance] = {}
        
        # Exchanges argentinos disponibles
        self.argentine_exchanges = self._detect_argentine_exchanges()
        
        # Mínimo de capital para operar (calculado dinámicamente)
        self.minimum_capital_ars = self._calculate_minimum_capital()
        
        # Sistema de alertas FLASH
        self.flash_alert_threshold = 10.0  # Alertar si spread > 10%
        self.flash_opportunities_found = 0
        self.last_flash_alert_time = None

    def _detect_argentine_exchanges(self) -> List[str]:
        """Detecta exchanges argentinos conectados."""
        # MEXC es el principal
        argentine_ids = ['mexc', 'cryptomarket', 'bitso']
        available = []
        
        for ex_id in argentine_ids:
            exchange = self.exchange_manager.get_exchange(ex_id)
            if exchange:
                available.append(ex_id)
        
        if not available and self.config.argentine_exchange:
            available.append(self.config.argentine_exchange.lower())
        
        self.base_logger.info(f"Exchanges argentinos detectados: {available}")
        return available

    def _calculate_minimum_capital(self) -> float:
        """
        Calcula el mínimo capital en ARS necesario para que sea rentable.
        
        Fórmula:
        fees_totales = withdrawal_fee_usdt * precio_usdt + trading_fees
        minimo = fees_totales / (spread_minimo - fees_percent)
        
        Con spread promedio de 0.8% y fees de ~0.7%, necesitamos:
        minimo = fees / (0.008 - 0.007) = fees / 0.001 = fees * 1000
        """
        # Fees fijos en USDT (ida y vuelta)
        withdrawal_fees_usdt = (
            self.FEES_DATA['binance'].withdrawal_fee_usdt +
            self.FEES_DATA.get('mexc', self.FEES_DATA['binance']).withdrawal_fee_usdt
        )  # ~2 USDT
        
        # Fees variables (%)
        trading_fees_percent = (
            self.FEES_DATA['binance'].trading_fee_percent +
            self.FEES_DATA.get('mexc', self.FEES_DATA['binance']).trading_fee_percent
        )  # ~0.15%
        
        # Spread mínimo objetivo (0.8%)
        target_spread_percent = 0.8
        
        # Profit mínimo después de fees (0.2%)
        min_profit_percent = 0.2
        
        # Cálculo:
        # Para ganar 0.2% después de fees, con spread de 0.8%:
        # fees_totales = spread - profit_deseado
        # fees_totales = 0.8% - 0.2% = 0.6%
        
        # fees_fijos_usdt = 2 USDT = ~3000 ARS (a $1500/USDT)
        # fees_fijos_percent = fees_fijos / capital
        # 0.6% = 0.006 = fees_fijos / capital
        # capital = fees_fijos / 0.006 = 3000 / 0.006 = 500,000 ARS
        
        # Pero queremos mínimo viable:
        # Si capital = 100,000 ARS (~67 USDT)
        # fees_fijos_percent = 3000 / 100000 = 3%
        # profit = 0.8% - 3% - 0.15% = NEGATIVO ❌
        
        # Si capital = 500,000 ARS (~333 USDT)
        # fees_fijos_percent = 3000 / 500000 = 0.6%
        # profit = 0.8% - 0.6% - 0.15% = 0.05% ✅ (muy bajo)
        
        # Si capital = 1,000,000 ARS (~667 USDT)
        # fees_fijos_percent = 3000 / 1000000 = 0.3%
        # profit = 0.8% - 0.3% - 0.15% = 0.35% ✅ (razonable)
        
        # Recomendación: 500,000 - 1,000,000 ARS mínimo
        minimum_recommended = 500000  # 500k ARS (~333 USDT)
        
        self.base_logger.info(f"Capital mínimo recomendado: ${minimum_recommended:,.0f} ARS")
        self.base_logger.info(f"  - Fees fijos: ~{withdrawal_fees_usdt:.1f} USDT por ciclo")
        self.base_logger.info(f"  - Fees trading: ~{trading_fees_percent:.2f}%")
        self.base_logger.info(f"  - Spread objetivo: >{target_spread_percent:.1f}%")
        
        return minimum_recommended

    async def start(self) -> None:
        """Inicia el motor de arbitraje."""
        self.is_running = True
        
        mode_text = "🧪 MODO SIMULACIÓN" if self.simulation_mode else "💰 MODO REAL"
        
        self.base_logger.info("=" * 70)
        self.base_logger.info(f"🚀 Motor de Arbitraje Inteligente con Fees INICIADO")
        self.base_logger.info(f"   {mode_text}")
        self.base_logger.info("=" * 70)
        self.base_logger.info(f"📊 Exchanges: Binance + {', '.join(self.argentine_exchanges)}")
        self.base_logger.info(f"💰 Capital mínimo: ${self.minimum_capital_ars:,.0f} ARS")
        self.base_logger.info(f"📈 Spread mínimo para operar: >0.6% (cubre fees)")
        self.base_logger.info(f"⚡ Alertas FLASH: Spread > {self.flash_alert_threshold}%")
        
        if self.simulation_mode:
            self.base_logger.info("⚠️  LAS OPERACIONES SON SIMULADAS - NO SE EJECUTAN ÓRDENES REALES")
            self.base_logger.info("💡 Usá este modo para probar el bot sin riesgo")
        
        self.base_logger.info("=" * 70)
        
        # Mostrar fees actuales
        self._print_fee_structure()

        while self.is_running:
            try:
                # Buscar oportunidades normales
                await self.find_best_opportunity()
                
                # Buscar oportunidades FLASH (spread > 10%)
                await self.check_flash_opportunities()
                
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.base_logger.error(f"Error en el loop: {e}")
                await asyncio.sleep(5)
        
        # Imprimir resumen final
        if self.simulation_mode:
            self.print_simulation_summary()

    async def stop(self) -> None:
        """Detiene el motor."""
        self.is_running = False
        self.base_logger.info("🛑 Motor detenido")
        self.print_profit_loss_summary()

    def _print_fee_structure(self):
        """Imprime estructura de fees actual."""
        self.base_logger.info("\n📋 ESTRUCTURA DE FEES ACTUAL")
        self.base_logger.info("-" * 70)
        
        for ex_id, fees in self.FEES_DATA.items():
            promo = " 🎁 PROMO" if fees.is_promotion else ""
            self.base_logger.info(f"{ex_id.upper()}{promo}:")
            self.base_logger.info(f"  • Retiro USDT (TRC20): {fees.withdrawal_fee_usdt} USDT")
            self.base_logger.info(f"  • Retiro ARS: ${fees.withdrawal_fee_ars:.0f}")
            self.base_logger.info(f"  • Depósito ARS: ${fees.deposit_fee_ars:.0f}")
            self.base_logger.info(f"  • Trading fee: {fees.trading_fee_percent:.2f}%")
            
            if fees.is_promotion:
                self.base_logger.info(f"  ⏰ Promo válida hasta: {fees.promotion_end_date}")
        
        self.base_logger.info("-" * 70)

    async def find_best_opportunity(self) -> None:
        """Busca la mejor oportunidad considerando fees."""
        if datetime.now().timestamp() < self.cooldown_until:
            return

        if len(self.current_positions) >= self.config.max_positions:
            return

        # Obtener todas las rutas con fees calculados
        routes = await self.get_all_routes_with_fees()

        if not routes:
            return

        # Filtrar solo las rentables
        profitable_routes = [r for r in routes if r.is_profitable]

        if not profitable_routes:
            # No hay oportunidades rentables
            if routes:
                best = max(routes, key=lambda r: r.net_profit_ars)
                self.base_logger.debug(
                    f"⚠️ Oportunidad detectada pero NO es rentable: "
                    f"Profit bruto: ${best.gross_profit_ars:.2f} ARS, "
                    f"Fees: ${best.total_fees_ars:.2f} ARS, "
                    f"Neto: ${best.net_profit_ars:.2f} ARS"
                )
            return

        # Seleccionar la mejor ruta rentable
        best_route = max(profitable_routes, key=lambda r: r.net_profit_percent)

        self.base_logger.info(
            f"💰 OPORTUNIDAD RENTABLE: {best_route.buy_exchange} → {best_route.sell_exchange}"
        )
        self.base_logger.info(f"   Spread: {best_route.sell_price/best_route.buy_price - 1:.2%}")
        self.base_logger.info(f"   Inversión: ${best_route.amount_ars_invested:,.0f} ARS")
        self.base_logger.info(f"   Profit BRUTO: ${best_route.gross_profit_ars:.2f} ARS")
        self.base_logger.info(f"   Fees TOTALES: ${best_route.total_fees_ars:.2f} ARS")
        self.base_logger.info(f"   Profit NETO: ${best_route.net_profit_ars:.2f} ARS ({best_route.net_profit_percent:.2f}%)")

        # Ejecutar si el profit neto es mayor al mínimo configurado
        if best_route.net_profit_percent >= self.config.min_profit_percent:
            await self.execute_arbitrage_with_fees(best_route)

    async def get_all_routes_with_fees(self) -> List[TriangularRoute]:
        """Obtiene todas las rutas con fees calculados."""
        routes = []

        binance = self.exchange_manager.binance
        if not binance:
            return []

        try:
            binance_ticker = await binance.get_ticker('USDT/ARS')
            if not binance_ticker or binance_ticker.get('ask', 0) <= 0:
                return []
            
            binance_buy_price = binance_ticker['ask']
            binance_sell_price = binance_ticker['bid']
        except Exception as e:
            self.base_logger.debug(f"Error obteniendo precio de Binance: {e}")
            return []

        # Comparar con cada exchange argentino
        for arg_ex_id in self.argentine_exchanges:
            try:
                arg_exchange = self.exchange_manager.get_exchange(arg_ex_id)
                if not arg_exchange:
                    continue

                ticker = await arg_exchange.get_ticker('USDT/ARS')
                if not ticker or ticker.get('bid', 0) <= 0 or ticker.get('ask', 0) <= 0:
                    continue

                # Calcular ruta con fees
                route = self._calculate_route_with_fees(
                    buy_exchange='binance',
                    sell_exchange=arg_ex_id,
                    buy_price=binance_buy_price,
                    sell_price=ticker['bid'],
                    amount_usdt=self.config.initial_capital,
                )
                
                if route:
                    routes.append(route)

            except Exception as e:
                self.base_logger.debug(f"Error obteniendo precio de {arg_ex_id}: {e}")
                continue

        # Ordenar por profit neto
        routes.sort(key=lambda r: r.net_profit_percent, reverse=True)
        return routes

    def _calculate_route_with_fees(
        self,
        buy_exchange: str,
        sell_exchange: str,
        buy_price: float,
        sell_price: float,
        amount_usdt: float
    ) -> Optional[TriangularRoute]:
        """
        Calcula una ruta de arbitraje con TODOS los fees incluidos.
        
        Flujo:
        1. Comprar USDT en exchange barato (ARS → USDT)
        2. Transferir USDT al exchange caro (fee de withdrawal)
        3. Vender USDT en exchange caro (USDT → ARS)
        4. Calcular profit neto después de fees
        """
        # Obtener fees de los exchanges
        buy_fees = self.FEES_DATA.get(buy_exchange, self.FEES_DATA['binance'])
        sell_fees = self.FEES_DATA.get(sell_exchange, self.FEES_DATA['mexc'])
        
        # 1. Compra de USDT (ARS → USDT)
        amount_ars_invested = amount_usdt * buy_price
        trading_fee_buy = amount_ars_invested * (buy_fees.trading_fee_percent / 100)
        
        # 2. Transferencia USDT
        withdrawal_fee_usdt = buy_fees.withdrawal_fee_usdt
        withdrawal_fee_ars = withdrawal_fee_usdt * sell_price  # Convertido a ARS al precio de venta
        
        # 3. Venta de USDT (USDT → ARS)
        amount_ars_received = amount_usdt * sell_price
        trading_fee_sell = amount_ars_received * (sell_fees.trading_fee_percent / 100)
        
        # 4. Cálculos finales
        gross_profit_ars = amount_ars_received - amount_ars_invested
        total_fees_ars = trading_fee_buy + trading_fee_sell + withdrawal_fee_ars
        net_profit_ars = gross_profit_ars - total_fees_ars
        net_profit_percent = (net_profit_ars / amount_ars_invested) * 100
        
        # Es rentable si el profit neto es positivo
        is_profitable = net_profit_ars > 0
        
        route = TriangularRoute(
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            buy_price=buy_price,
            sell_price=sell_price,
            amount_usdt=amount_usdt,
            amount_ars_invested=amount_ars_invested,
            trading_fee_buy=trading_fee_buy,
            trading_fee_sell=trading_fee_sell,
            withdrawal_fee_usdt=withdrawal_fee_usdt,
            withdrawal_fee_ars=withdrawal_fee_ars,
            gross_profit_ars=gross_profit_ars,
            total_fees_ars=total_fees_ars,
            net_profit_ars=net_profit_ars,
            net_profit_percent=net_profit_percent,
            is_profitable=is_profitable,
        )
        
        self.base_logger.debug(
            f"Ruta calculada: {buy_exchange} → {sell_exchange} | "
            f"Net: ${net_profit_ars:.2f} ARS ({net_profit_percent:.2f}%) | "
            f"Profitable: {is_profitable}"
        )
        
        return route

    async def execute_arbitrage_with_fees(self, route: TriangularRoute) -> None:
        """Ejecuta arbitraje (real o simulado) mostrando fees y profit."""
        self.base_logger.info("=" * 70)
        
        if self.simulation_mode:
            self.base_logger.info("🧪 SIMULACIÓN DE ARBITRAJE")
            self.simulation_trades += 1
        else:
            self.base_logger.info("🎯 EJECUTANDO ARBITRAJE")
            self.total_trades += 1
        
        self.base_logger.info("=" * 70)
        
        binance = self.exchange_manager.binance
        sell_exchange = self.exchange_manager.get_exchange(route.sell_exchange)

        if not binance or not sell_exchange:
            self.base_logger.error("❌ Exchange no disponible")
            return

        try:
            # Verificar balances
            binance_ars = await binance.get_balance('ARS')
            sell_exchange_usdt = await sell_exchange.get_balance('USDT')

            self.base_logger.info(f"📊 Balances actuales:")
            self.base_logger.info(f"   Binance ARS: ${binance_ars:,.2f}")
            self.base_logger.info(f"   {route.sell_exchange} USDT: {sell_exchange_usdt:.4f}")

            # Mostrar desglose de la operación
            self.base_logger.info(f"\n📋 DETALLES DE LA OPERACIÓN")
            self.base_logger.info(f"   Comprar {route.amount_usdt:.2f} USDT en {route.buy_exchange} a ${route.buy_price:.2f}")
            self.base_logger.info(f"   Vender {route.amount_usdt:.2f} USDT en {route.sell_exchange} a ${route.sell_price:.2f}")
            self.base_logger.info(f"   Inversión: ${route.amount_ars_invested:,.2f} ARS")
            
            self.base_logger.info(f"\n💸 FEES A PAGAR:")
            self.base_logger.info(f"   Trading fee ({route.buy_exchange}): ${route.trading_fee_buy:.2f} ARS")
            self.base_logger.info(f"   Trading fee ({route.sell_exchange}): ${route.trading_fee_sell:.2f} ARS")
            self.base_logger.info(f"   Withdrawal fee (USDT TRC20): {route.withdrawal_fee_usdt:.2f} USDT (~${route.withdrawal_fee_ars:.2f} ARS)")
            self.base_logger.info(f"   TOTAL FEES: ${route.total_fees_ars:.2f} ARS")
            
            self.base_logger.info(f"\n📈 RESULTADO ESPERADO:")
            self.base_logger.info(f"   Profit BRUTO: ${route.gross_profit_ars:.2f} ARS")
            self.base_logger.info(f"   Profit NETO: ${route.net_profit_ars:.2f} ARS ({route.net_profit_percent:.2f}%)")

            if self.simulation_mode:
                # SIMULACIÓN: No ejecutar órdenes reales
                self.base_logger.info(f"\n⚠️  MODO SIMULACIÓN - NO SE EJECUTAN ÓRDENES")
                
                # Actualizar estadísticas de simulación
                if route.net_profit_ars > 0:
                    self.profitable_trades += 1
                    profit_usdt = route.net_profit_ars / route.sell_price
                    self.simulation_profit_usdt += profit_usdt
                    self.base_logger.info(f"✅ SIMULACIÓN EXITOSA: +{profit_usdt:.4f} USDT")
                else:
                    self.simulation_missed_opportunities += 1
                    self.base_logger.info(f"❌ SIMULACIÓN: No es rentable")
                
                # Cooldown
                self.cooldown_until = datetime.now().timestamp() + self.config.cooldown_seconds
                
                self.base_logger.info(f"\n📊 ESTADÍSTICAS DE SIMULACIÓN:")
                self.base_logger.info(f"   Operaciones simuladas: {self.simulation_trades}")
                self.base_logger.info(f"   Profit simulado: {self.simulation_profit_usdt:.4f} USDT")
                self.base_logger.info(f"   Oportunidades perdidas: {self.simulation_missed_opportunities}")
                
            else:
                # MODO REAL: Ejecutar órdenes (implementación futura)
                self.base_logger.info(f"\n⚡ Ejecutando órdenes reales...")
                
                # 1. Comprar USDT en Binance
                # buy_order = await binance.create_market_order(...)
                
                # 2. Transferir USDT
                # transfer = await binance.withdraw_crypto(...)
                
                # 3. Vender USDT en exchange argentino
                # sell_order = await sell_exchange.create_market_order(...)
                
                # Actualizar estadísticas
                if route.net_profit_ars > 0:
                    self.profitable_trades += 1
                    profit_usdt = route.net_profit_ars / route.sell_price
                    self.total_profit_usdt += profit_usdt
                    self.total_fees_paid_usdt += route.total_fees_ars / route.sell_price
                    self.total_volume_usdt += route.amount_usdt
                    
                    self.base_logger.info(f"\n✅ OPERACIÓN COMPLETADA")
                    self.base_logger.info(f"   Profit: +{profit_usdt:.4f} USDT")
                
                # Cooldown
                self.cooldown_until = datetime.now().timestamp() + self.config.cooldown_seconds
                
                self.print_profit_loss_summary()

        except Exception as e:
            self.base_logger.error(f"❌ Error: {e}")

    def print_profit_loss_summary(self):
        """Imprime resumen detallado de Profit/Loss con fees."""
        profit_status = "✅ PROFIT" if self.total_profit_usdt > 0 else "❌ LOSS" if self.total_profit_usdt < 0 else "⚪ BREAK EVEN"
        
        avg_fee_per_trade = self.total_fees_paid_usdt / self.total_trades if self.total_trades > 0 else 0
        
        self.base_logger.info("=" * 70)
        self.base_logger.info(f"📊 RESUMEN DE OPERACIONES - {profit_status}")
        self.base_logger.info("=" * 70)
        self.base_logger.info(f"Total Trades: {self.total_trades}")
        self.base_logger.info(f"Profitable: {self.profitable_trades}/{self.total_trades} ({self.profitable_trades/self.total_trades*100 if self.total_trades > 0 else 0:.1f}%)")
        self.base_logger.info(f"Volumen Total: {self.total_volume_usdt:.2f} USDT")
        self.base_logger.info(f"Profit Total: {self.total_profit_usdt:+.4f} USDT")
        self.base_logger.info(f"Fees Pagados: {self.total_fees_paid_usdt:.4f} USDT")
        self.base_logger.info(f"Fee Promedio/Trade: {avg_fee_per_trade:.4f} USDT")
        self.base_logger.info(f"Profit Neto (después de fees): {self.total_profit_usdt:.4f} USDT")
        self.base_logger.info("=" * 70)

    def print_simulation_summary(self):
        """Imprime resumen de la simulación."""
        self.base_logger.info("=" * 70)
        self.base_logger.info("🧪 RESUMEN DE SIMULACIÓN")
        self.base_logger.info("=" * 70)
        self.base_logger.info(f"Operaciones simuladas: {self.simulation_trades}")
        self.base_logger.info(f"Operaciones rentables: {self.profitable_trades}")
        self.base_logger.info(f"Oportunidades perdidas: {self.simulation_missed_opportunities}")
        self.base_logger.info(f"Profit simulado total: {self.simulation_profit_usdt:+.4f} USDT")
        
        if self.simulation_trades > 0:
            win_rate = (self.profitable_trades / self.simulation_trades) * 100
            avg_profit = self.simulation_profit_usdt / self.simulation_trades
            self.base_logger.info(f"Win Rate: {win_rate:.1f}%")
            self.base_logger.info(f"Profit promedio/op: {avg_profit:+.4f} USDT")
        
        self.base_logger.info("=" * 70)
        self.base_logger.info("💡 ¿Querés operar en REAL? Cambiá a modo real en main.py")
        self.base_logger.info("=" * 70)

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del motor."""
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_profit': self.total_profit_usdt,
            'total_fees_paid': self.total_fees_paid_usdt,
            'total_volume': self.total_volume_usdt,
            'avg_profit_per_trade': (self.total_profit_usdt / self.total_trades) if self.total_trades > 0 else 0,
            'avg_fee_per_trade': (self.total_fees_paid_usdt / self.total_trades) if self.total_trades > 0 else 0,
        }

    def get_active_positions(self) -> List:
        """Obtiene posiciones activas."""
        return self.current_positions

    async def check_flash_opportunities(self) -> None:
        """
        Busca oportunidades FLASH con spread > 10%.
        Estas son extremadamente raras pero pueden ocurrir.
        """
        binance = self.exchange_manager.binance
        if not binance:
            return

        try:
            binance_ticker = await binance.get_ticker('USDT/ARS')
            if not binance_ticker:
                return
            
            binance_price = binance_ticker.get('ask', 0)
            if binance_price <= 0:
                return

            # Comparar con cada exchange argentino
            for arg_ex_id in self.argentine_exchanges:
                try:
                    arg_exchange = self.exchange_manager.get_exchange(arg_ex_id)
                    if not arg_exchange:
                        continue

                    ticker = await arg_exchange.get_ticker('USDT/ARS')
                    if not ticker:
                        continue

                    arg_price = ticker.get('bid', 0)
                    if arg_price <= 0:
                        continue

                    # Calcular spread
                    spread = arg_price - binance_price
                    spread_pct = (spread / binance_price) * 100

                    # Alertar si spread > threshold (10%)
                    if spread_pct >= self.flash_alert_threshold:
                        self.flash_opportunities_found += 1
                        now = datetime.now()
                        
                        # Solo alertar una vez cada 5 minutos para no spamear
                        if (self.last_flash_alert_time is None or 
                            (now - self.last_flash_alert_time).total_seconds() > 300):
                            
                            self.last_flash_alert_time = now
                            
                            # Calcular profit potencial con 7 USDT
                            capital_usdt = 7
                            fees_usdt = 2  # Withdrawal fees
                            invested_ars = capital_usdt * binance_price
                            received_ars = (capital_usdt - fees_usdt) * arg_price
                            profit_ars = received_ars - invested_ars
                            profit_pct = (profit_ars / invested_ars) * 100

                            self.base_logger.warning("=" * 70)
                            self.base_logger.warning("⚡⚡⚡ ALERTA FLASH DETECTADA ⚡⚡⚡")
                            self.base_logger.warning("=" * 70)
                            self.base_logger.warning(f"🔥 Spread: {spread_pct:.2f}% (>{self.flash_alert_threshold}%)")
                            self.base_logger.warning(f"📊 Comprar en Binance: ${binance_price:.2f}")
                            self.base_logger.warning(f"📊 Vender en {arg_ex_id.upper()}: ${arg_price:.2f}")
                            self.base_logger.warning(f"💰 CON 7 USDT:")
                            self.base_logger.warning(f"   Profit: ${profit_ars:.2f} ARS ({profit_pct:.2f}%)")
                            
                            if profit_ars > 0:
                                self.base_logger.warning("   ✅ ES RENTABLE - EJECUTAR AHORA!")
                                self.base_logger.warning("   ⚠️ La oportunidad puede desaparecer en segundos")
                            else:
                                self.base_logger.warning("   ❌ NO es rentable (fees > spread)")
                                self.base_logger.warning(f"   💡 Necesitas mínimo: ${abs(profit_ars) * (100/profit_pct) if profit_pct != 0 else 'N/A':,.0f} ARS de capital")
                            
                            self.base_logger.warning("=" * 70)
                            
                            # Enviar alerta por Telegram si está configurado
                            try:
                                from ..utils import TelegramNotifier
                                # El bot principal manejará el envío real
                            except:
                                pass

                except Exception as e:
                    self.base_logger.debug(f"Error verificando {arg_ex_id}: {e}")
                    continue

        except Exception as e:
            self.base_logger.debug(f"Error en check_flash: {e}")
