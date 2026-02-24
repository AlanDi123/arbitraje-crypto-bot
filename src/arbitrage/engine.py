"""
Módulo principal de arbitraje.
Detecta oportunidades y ejecuta operaciones entre múltiples exchanges.
"""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field

from ..utils import Config, setup_logger, TradeLogger
from ..api import ExchangeManager


@dataclass
class ArbitrageOpportunity:
    """Representa una oportunidad de arbitraje."""
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    spread_percent: float
    estimated_profit: float
    estimated_profit_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    symbol: str = "USDT/ARS"


@dataclass
class Position:
    """Representa una posición abierta de arbitraje."""
    id: str
    buy_exchange: str
    sell_exchange: str
    entry_amount: float
    entry_price: float
    entry_timestamp: datetime
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    profit: Optional[float] = None
    profit_percent: Optional[float] = None
    status: str = "open"


class ArbitrageEngine:
    """
    Motor principal de arbitraje multi-exchange.
    Detecta oportunidades y gestiona operaciones entre todos los exchanges configurados.
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
        self.base_logger = setup_logger("arbitrage.engine")

        self.is_running = False
        self.current_positions: List[Position] = []
        self.position_counter = 0
        self.cooldown_until = 0

        # Estadísticas
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit = 0
        self.total_volume = 0

    async def start(self) -> None:
        """Inicia el motor de arbitraje."""
        self.is_running = True
        self.base_logger.info("🚀 Motor de arbitraje iniciado")
        self.base_logger.info(f"📊 Exchanges disponibles: {self.exchange_manager.get_all_exchanges()}")

        while self.is_running:
            try:
                await self.check_opportunities()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.base_logger.error(f"Error en el loop de arbitraje: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Detiene el motor de arbitraje."""
        self.is_running = False
        self.base_logger.info("🛑 Motor de arbitraje detenido")

    async def check_opportunities(self) -> None:
        """Verifica si hay oportunidades de arbitraje entre todos los exchanges."""
        if datetime.now().timestamp() < self.cooldown_until:
            return

        if len(self.current_positions) >= self.config.max_positions:
            return

        opportunities = await self.exchange_manager.get_arbitrage_opportunities()

        if not opportunities:
            return

        best_opportunity = opportunities[0]

        self.base_logger.info(
            f"💰 Oportunidad detectada: {best_opportunity['buy_exchange']} → {best_opportunity['sell_exchange']} | "
            f"Spread: {best_opportunity['spread_percent']:.2f}% | "
            f"Profit Est: {best_opportunity['estimated_profit_percent']:.2f}%"
        )

        opportunity = ArbitrageOpportunity(
            buy_exchange=best_opportunity['buy_exchange'],
            sell_exchange=best_opportunity['sell_exchange'],
            buy_price=best_opportunity['buy_price'],
            sell_price=best_opportunity['sell_price'],
            spread=best_opportunity['spread'],
            spread_percent=best_opportunity['spread_percent'],
            estimated_profit=0,
            estimated_profit_percent=best_opportunity['estimated_profit_percent'],
            timestamp=datetime.now(),
        )

        await self.execute_arbitrage(opportunity)

    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> None:
        """Ejecuta una operación de arbitraje entre dos exchanges."""
        self.base_logger.info(
            f"🎯 Ejecutando arbitraje: {opportunity.buy_exchange} → {opportunity.sell_exchange}"
        )

        capital_to_use = self.config.initial_capital

        buy_exchange = self.exchange_manager.get_exchange(opportunity.buy_exchange)
        sell_exchange = self.exchange_manager.get_exchange(opportunity.sell_exchange)

        if not buy_exchange or not sell_exchange:
            self.base_logger.error("Exchange no disponible")
            return

        buy_usdt = await buy_exchange.get_balance('USDT')
        sell_usdt = await sell_exchange.get_balance('USDT')

        self.base_logger.debug(
            f"Balances - {opportunity.buy_exchange}: {buy_usdt} USDT, "
            f"{opportunity.sell_exchange}: {sell_usdt} USDT"
        )

        try:
            buy_order = await buy_exchange.create_market_order(
                symbol='USDT/ARS', side='buy', amount=capital_to_use
            )

            if 'error' in buy_order:
                raise Exception(f"Error en orden de compra: {buy_order['error']}")

            sell_order = await sell_exchange.create_market_order(
                symbol='USDT/ARS', side='sell', amount=capital_to_use
            )

            if 'error' in sell_order:
                try:
                    await buy_exchange.cancel_order(buy_order.get('id'), 'USDT/ARS')
                except:
                    pass
                raise Exception(f"Error en orden de venta: {sell_order['error']}")

            self.position_counter += 1
            position = Position(
                id=f"ARB-{self.position_counter:04d}",
                buy_exchange=opportunity.buy_exchange,
                sell_exchange=opportunity.sell_exchange,
                entry_amount=capital_to_use,
                entry_price=opportunity.buy_price,
                entry_timestamp=datetime.now(),
            )

            self.current_positions.append(position)

            self.logger.log_trade_open(
                exchange=f"{opportunity.buy_exchange}/{opportunity.sell_exchange}",
                pair='USDT/ARS',
                side='ARBITRAGE',
                amount=capital_to_use,
                price=opportunity.buy_price,
                order_id=position.id
            )

            estimated_profit = capital_to_use * (opportunity.estimated_profit_percent / 100)
            position.profit = estimated_profit
            position.profit_percent = opportunity.estimated_profit_percent

            self.total_trades += 1
            self.total_volume += capital_to_use

            self.cooldown_until = datetime.now().timestamp() + self.config.cooldown_seconds

            self.base_logger.info(
                f"✅ Arbitraje ejecutado: {position.id} | "
                f"Monto: {capital_to_use} USDT | "
                f"Ganancia Est: {estimated_profit:.2f} USDT ({opportunity.estimated_profit_percent:.2f}%)"
            )

            await self.close_position(position, opportunity.sell_price)

        except Exception as e:
            self.logger.log_error("execute_arbitrage", e, {
                'buy_exchange': opportunity.buy_exchange,
                'sell_exchange': opportunity.sell_exchange,
                'capital_to_use': capital_to_use
            })
            self.base_logger.error(f"❌ Error ejecutando arbitraje: {e}")

    async def close_position(self, position: Position, exit_price: float) -> None:
        """Cierra una posición y registra la ganancia/pérdida."""
        position.exit_price = exit_price
        position.exit_timestamp = datetime.now()
        position.status = "closed"

        position.profit = position.entry_amount * (exit_price - position.entry_price) / position.entry_price
        position.profit_percent = (position.profit / position.entry_amount) * 100

        self.logger.log_trade_close(
            exchange=f"{position.buy_exchange}/{position.sell_exchange}",
            pair='USDT/ARS',
            side='ARBITRAGE',
            amount=position.entry_amount,
            entry_price=position.entry_price,
            exit_price=exit_price,
            profit=position.profit,
            profit_percent=position.profit_percent,
            order_id=position.id
        )

        if position.profit > 0:
            self.profitable_trades += 1
        self.total_profit += position.profit

        self.current_positions.remove(position)

        self.base_logger.info(
            f"📊 Posición cerrada: {position.id} | "
            f"Ganancia: {position.profit:.2f} USDT ({position.profit_percent:.2f}%) | "
            f"Total acumulado: {self.total_profit:.2f} USDT"
        )

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del motor de arbitraje."""
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_profit': self.total_profit,
            'total_volume': self.total_volume,
            'active_positions': len(self.current_positions),
            'avg_profit_per_trade': (self.total_profit / self.total_trades) if self.total_trades > 0 else 0,
        }

    def get_active_positions(self) -> List[Dict]:
        """Obtiene las posiciones activas."""
        return [
            {
                'id': p.id,
                'buy_exchange': p.buy_exchange,
                'sell_exchange': p.sell_exchange,
                'entry_amount': p.entry_amount,
                'entry_price': p.entry_price,
                'entry_timestamp': p.entry_timestamp.isoformat(),
                'profit': p.profit,
                'profit_percent': p.profit_percent,
            }
            for p in self.current_positions
        ]
