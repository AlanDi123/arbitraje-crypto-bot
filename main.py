"""
Bot de Arbitraje USDT/ARS - Archivo Principal

Este bot ejecuta operaciones de arbitraje entre Binance y exchanges argentinos,
analizando noticias en tiempo real y usando machine learning para optimizar decisiones.

Uso:
    python main.py          # Iniciar el bot
    python main.py --test   # Modo prueba (sin operaciones reales)
    python main.py --backtest  # Ejecutar backtesting
"""

import asyncio
import signal
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional

from src.utils import (
    Config,
    CryptoManager,
    setup_logger,
    TradeLogger,
    TelegramNotifier,
)
from src.api import ExchangeManager
from src.arbitrage import ArbitrageEngine, Backtester, SmartArbitrageEngineWithFees
from src.news import NewsAnalyzer
from src.ml import MLTrader
from src.tui import TUIDashboard


class ArbitrageBot:
    """
    Bot principal de arbitraje.

    Orquesta todos los módulos:
    - Conexión con exchanges
    - Detección y ejecución de arbitraje
    - Análisis de noticias
    - Machine Learning
    - Dashboard TUI
    - Notificaciones Telegram
    """

    def __init__(self, config: Config, test_mode: bool = False, simulation_mode: bool = False):
        self.config = config
        self.test_mode = test_mode
        self.simulation_mode = simulation_mode  # Nuevo parámetro
        self.logger = setup_logger("bot.main")
        self.trade_logger = TradeLogger(self.logger)
        
        # Componentes
        self.exchange_manager: Optional[ExchangeManager] = None
        self.arbitrage_engine: Optional[ArbitrageEngine] = None
        self.news_analyzer: Optional[NewsAnalyzer] = None
        self.ml_trader: Optional[MLTrader] = None
        self.telegram: Optional[TelegramNotifier] = None
        self.dashboard: Optional[TUIDashboard] = None
        self.backtester: Optional[Backtester] = None
        
        # Estado
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.tasks: list = []
        
        # Configurar cifrado
        if config.encryption_password:
            self.crypto = CryptoManager(config.encryption_password)
        else:
            self.crypto = None
    
    async def initialize(self) -> bool:
        """Inicializa todos los componentes del bot."""
        self.logger.info("🚀 Iniciando Arbitrage Bot USDT/ARS...")
        
        # Validar configuración
        valid, errors = self.config.validate()
        if not valid:
            self.logger.error("❌ Configuración inválida:")
            for error in errors:
                self.logger.error(f"   - {error}")
            return False
        
        self.logger.info("✅ Configuración validada")

        # Inicializar exchanges
        self.exchange_manager = ExchangeManager(self.config)
        connected = await self.exchange_manager.connect_all()

        if not connected:
            self.logger.error("❌ Error conectando a los exchanges")
            return False

        # Inicializar motor de arbitraje INTELIGENTE con cálculo de fees
        self.arbitrage_engine = SmartArbitrageEngineWithFees(
            self.config,
            self.exchange_manager,
            self.trade_logger,
            simulation_mode=self.simulation_mode,  # Pasar modo simulación
        )
        
        # Inicializar analizador de noticias
        self.news_analyzer = NewsAnalyzer(self.config)
        
        # Inicializar ML Trader
        self.ml_trader = MLTrader(self.config)
        
        # Inicializar Telegram
        self.telegram = TelegramNotifier(self.config)
        
        # Inicializar Dashboard
        self.dashboard = TUIDashboard(self.config)
        
        # Inicializar Backtester
        self.backtester = Backtester(self.config, self.exchange_manager)
        
        self.logger.info("✅ Todos los componentes inicializados")
        return True
    
    async def start(self) -> None:
        """Inicia todos los servicios del bot."""
        if self.test_mode:
            self.logger.info("🧪 MODO PRUEBA - No se ejecutarán operaciones reales")
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Iniciar componentes
        await self.telegram.start()
        
        # Crear tareas asíncronas
        self.tasks = [
            asyncio.create_task(self.arbitrage_engine.start()),
            asyncio.create_task(self.news_analyzer.start()),
            asyncio.create_task(self.ml_trader.start()),
            asyncio.create_task(self.dashboard.start()),
            asyncio.create_task(self._update_loop()),
        ]
        
        self.logger.info("✅ Bot en ejecución")
        
        # Esperar a que todas las tareas se completen
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            pass
    
    async def stop(self) -> None:
        """Detiene todos los servicios del bot."""
        self.logger.info("🛑 Deteniendo bot...")
        self.is_running = False
        
        # Cancelar tareas
        for task in self.tasks:
            task.cancel()
        
        # Detener componentes
        if self.dashboard:
            await self.dashboard.stop()
        if self.news_analyzer:
            await self.news_analyzer.stop()
        if self.ml_trader:
            await self.ml_trader.stop()
        if self.telegram:
            await self.telegram.stop()
        if self.exchange_manager:
            await self.exchange_manager.disconnect_all()
        
        # Imprimir resumen
        if self.arbitrage_engine:
            stats = self.arbitrage_engine.get_statistics()
            self.logger.info(f"📊 Resumen: {stats['total_trades']} trades, "
                           f"{stats['total_profit']:.2f} USDT profit")
        
        self.logger.info("✅ Bot detenido")
    
    async def _update_loop(self) -> None:
        """Loop de actualización de datos del dashboard."""
        while self.is_running:
            try:
                # Actualizar datos
                if self.dashboard and self.arbitrage_engine:
                    uptime = datetime.now() - self.start_time
                    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)

                    # Obtener balances - solo Binance y exchange argentino tienen USDT/ARS
                    binance_usdt = await self.exchange_manager.binance.get_balance('USDT')
                    binance_ars = await self.exchange_manager.binance.get_balance('ARS')

                    # Obtener exchange argentino (si está conectado)
                    argentine_exchange = self.exchange_manager.get_exchange(self.config.argentine_exchange)
                    if argentine_exchange:
                        argentine_usdt = await argentine_exchange.get_balance('USDT')
                        argentine_ars = await argentine_exchange.get_balance('ARS')
                    else:
                        argentine_usdt = 0
                        argentine_ars = 0

                    total_usdt = binance_usdt + argentine_usdt
                    
                    # Obtener precios de referencia de CriptoYa
                    criptoya_prices = {}
                    if self.exchange_manager.criptoya:
                        try:
                            criptoya_data = await self.exchange_manager.criptoya.get_all_prices()
                            if criptoya_data:
                                # Extraer precios USDT de cada exchange
                                for exchange, data in criptoya_data.items():
                                    if isinstance(data, dict):
                                        criptoya_prices[exchange] = {
                                            'buy': data.get('ask', 0),
                                            'sell': data.get('bid', 0),
                                            'last': data.get('price', 0),
                                        }
                        except Exception as e:
                            self.logger.debug(f"Error obteniendo precios CriptoYa: {e}")

                    self.dashboard.update_data({
                        'bot_status': 'running' if self.is_running else 'stopped',
                        'uptime': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                        'binance_balance': {'USDT': binance_usdt, 'ARS': binance_ars},
                        'argentine_balance': {'USDT': argentine_usdt, 'ARS': argentine_ars},
                        'total_balance_usdt': total_usdt,
                        'active_positions': self.arbitrage_engine.get_active_positions(),
                        'statistics': self.arbitrage_engine.get_statistics(),
                        'market_analysis': self.news_analyzer.get_market_analysis(),
                        'recent_news': self.news_analyzer.get_recent_news(5),
                        'ml_stats': self.ml_trader.get_stats(),
                        'criptoya_prices': criptoya_prices,  # Precios consolidados
                    })

                # Verificar si pausar por noticias
                if self.news_analyzer.should_pause_trading():
                    self.logger.warning("⚠️ Trading pausado por noticias de alto impacto")
                    if self.arbitrage_engine:
                        self.arbitrage_engine.is_running = False

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error en update loop: {e}")
                await asyncio.sleep(5)
    
    async def run_backtest(
        self,
        days: int = 30,
        initial_capital: Optional[float] = None
    ) -> None:
        """Ejecuta backtesting."""
        self.logger.info(f"🧪 Ejecutando backtest de {days} días...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        capital = initial_capital or self.config.initial_capital
        
        result = await self.backtester.run_backtest(start_date, end_date, capital)
        self.backtester.print_results(result)
        
        # Guardar resultados
        from pathlib import Path
        results_file = Path("data/logs/backtest_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(results_file, 'w') as f:
            json.dump({
                'start_date': result.start_date.isoformat(),
                'end_date': result.end_date.isoformat(),
                'initial_capital': result.initial_capital,
                'final_capital': result.final_capital,
                'total_trades': result.total_trades,
                'profitable_trades': result.profitable_trades,
                'win_rate': result.win_rate,
                'total_profit': result.total_profit,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
            }, f, indent=2)
        
        self.logger.info(f"📂 Resultados guardados en {results_file}")


async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description="Bot de Arbitraje USDT/ARS")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Modo prueba (sin operaciones reales)"
    )
    parser.add_argument(
        "--simulation",
        action="store_true",
        help="Modo SIMULACIÓN (monitorea y simula operaciones sin ejecutar)"
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Ejecutar backtesting"
    )
    parser.add_argument(
        "--backtest-days",
        type=int,
        default=30,
        help="Días para backtesting (default: 30)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=".env",
        help="Archivo de configuración (default: .env)"
    )

    args = parser.parse_args()

    # Cargar configuración
    config = Config(args.config)

    # Crear bot
    bot = ArbitrageBot(config, test_mode=args.test, simulation_mode=args.simulation)
    
    # Configurar señal de interrupción
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(bot.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    # Inicializar
    initialized = await bot.initialize()
    
    if not initialized:
        sys.exit(1)
    
    # Ejecutar
    try:
        if args.backtest:
            await bot.run_backtest(days=args.backtest_days)
        else:
            await bot.start()
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        bot.logger.error(f"Error fatal: {e}")
        await bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
