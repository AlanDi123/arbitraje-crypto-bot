"""
Módulo de backtesting para evaluar estrategias con datos históricos.
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import json

from ..utils import Config, setup_logger
from ..api import ExchangeManager


@dataclass
class BacktestResult:
    """Resultado de una simulación de backtest."""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_trades: int
    profitable_trades: int
    win_rate: float
    total_profit: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Dict]


class Backtester:
    """
    Realiza backtesting de la estrategia de arbitraje.
    
    Usa datos históricos de precios para simular operaciones
    y evaluar el rendimiento potencial.
    """
    
    def __init__(self, config: Config, exchange_manager: ExchangeManager):
        self.config = config
        self.exchange_manager = exchange_manager
        self.logger = setup_logger("backtester")
        
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
    ) -> BacktestResult:
        """
        Ejecuta el backtesting en el período especificado.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            initial_capital: Capital inicial en USDT
        
        Returns:
            Resultado del backtest
        """
        self.logger.info(
            f"🧪 Iniciando backtest: {start_date.date()} a {end_date.date()} | "
            f"Capital: {initial_capital} USDT"
        )
        
        # Obtener datos históricos
        klines_data = await self._fetch_historical_data(
            start_date, end_date
        )
        
        if not klines_data:
            self.logger.error("No se pudieron obtener datos históricos")
            return self._empty_result(start_date, end_date, initial_capital)
        
        # Simular operaciones
        trades = []
        capital = initial_capital
        peak_capital = initial_capital
        max_drawdown = 0
        
        for i in range(1, len(klines_data)):
            prev_data = klines_data[i - 1]
            curr_data = klines_data[i]
            
            # Calcular spread simulado (usando diferencia entre exchanges)
            # En backtest real, necesitaríamos datos de ambos exchanges
            spread_percent = self._calculate_simulated_spread(prev_data, curr_data)
            
            # Verificar si hay oportunidad
            if spread_percent > self.config.min_profit_percent:
                # Simular operación
                profit_percent = spread_percent - 0.2  # Restar comisiones estimadas
                
                if profit_percent > 0:
                    profit = capital * (profit_percent / 100)
                    capital += profit
                    
                    trades.append({
                        'timestamp': datetime.fromtimestamp(curr_data['timestamp'] / 1000).isoformat(),
                        'spread': spread_percent,
                        'profit': profit,
                        'profit_percent': profit_percent,
                        'capital_after': capital,
                    })
                    
                    # Actualizar peak y drawdown
                    if capital > peak_capital:
                        peak_capital = capital
                    
                    drawdown = (peak_capital - capital) / peak_capital * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
        
        # Calcular estadísticas
        total_trades = len(trades)
        profitable_trades = sum(1 for t in trades if t['profit'] > 0)
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        total_profit = capital - initial_capital
        
        # Calcular Sharpe Ratio (simplificado)
        if trades:
            returns = [t['profit_percent'] for t in trades]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=capital,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            win_rate=win_rate,
            total_profit=total_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
        )
        
        self.logger.info(
            f"✅ Backtest completado | "
            f"Trades: {total_trades} | Win Rate: {win_rate:.1f}% | "
            f"Profit: {total_profit:+.2f} USDT | Sharpe: {sharpe_ratio:.2f}"
        )
        
        return result
    
    async def _fetch_historical_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Obtiene datos históricos de klines."""
        # Intentar cargar desde caché
        cache_file = self.cache_dir / f"klines_{start_date.date()}_{end_date.date()}.json"
        
        if cache_file.exists():
            self.logger.info(f"📂 Cargando datos desde caché: {cache_file}")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Obtener datos de la API
        self.logger.info("📡 Obteniendo datos históricos de la API...")
        
        all_klines = []
        current_date = start_date
        
        while current_date < end_date:
            try:
                # Obtener klines de 1 hora
                klines = await self.exchange_manager.binance.get_klines(
                    symbol='USDT/ARS',
                    interval='1h',
                    limit=500
                )
                
                if klines:
                    all_klines.extend(klines)
                
                # Avanzar aproximadamente 500 horas
                current_date += timedelta(hours=500)
                
                # Rate limit
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error obteniendo klines: {e}")
                break
        
        # Guardar en caché
        if all_klines:
            with open(cache_file, 'w') as f:
                json.dump(all_klines, f)
        
        return all_klines
    
    def _calculate_simulated_spread(
        self,
        prev_data: Dict,
        curr_data: Dict
    ) -> float:
        """
        Calcula un spread simulado basado en volatilidad.
        
        En un backtest real, se necesitarían datos de ambos exchanges.
        Esta es una aproximación basada en la volatilidad del precio.
        """
        # Calcular volatilidad
        price_change = abs(curr_data['close'] - prev_data['close']) / prev_data['close'] * 100
        
        # Simular spread como función de la volatilidad
        # En arbitraje real, el spread depende de la diferencia entre exchanges
        base_spread = 0.5  # Spread base mínimo
        volatility_factor = price_change * 2  # La volatilidad aumenta oportunidades
        
        simulated_spread = base_spread + volatility_factor
        
        return simulated_spread
    
    def _empty_result(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float
    ) -> BacktestResult:
        """Devuelve un resultado vacío cuando no hay datos."""
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_trades=0,
            profitable_trades=0,
            win_rate=0,
            total_profit=0,
            max_drawdown=0,
            sharpe_ratio=0,
            trades=[],
        )
    
    def print_results(self, result: BacktestResult) -> None:
        """Imprime los resultados del backtest de forma formateada."""
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        
        console.print("\n[bold blue]═══════════════════════════════════════════════════════[/bold blue]")
        console.print("[bold blue]           RESULTADOS DEL BACKTESTING[/bold blue]")
        console.print("[bold blue]═══════════════════════════════════════════════════════[/bold blue]\n")
        
        # Tabla de resumen
        table = Table(show_header=False, box=None)
        table.add_column("Concepto", style="cyan")
        table.add_column("Valor", justify="right", style="white")
        
        table.add_row("Período:", f"{result.start_date.date()} a {result.end_date.date()}")
        table.add_row("Capital Inicial:", f"{result.initial_capital:.2f} USDT")
        table.add_row("Capital Final:", f"{result.final_capital:.2f} USDT")
        
        profit_color = "green" if result.total_profit >= 0 else "red"
        table.add_row("Ganancia Total:", f"[{profit_color}]{result.total_profit:+.2f} USDT[/{profit_color}]")
        table.add_row("Retorno:", f"[{profit_color}]{(result.total_profit/result.initial_capital)*100:+.2f}%[/{profit_color}]")
        
        table.add_row("", "")  # Espacio
        table.add_row("Total Operaciones:", str(result.total_trades))
        table.add_row("Operaciones Ganadoras:", str(result.profitable_trades))
        
        win_color = "green" if result.win_rate >= 50 else "yellow"
        table.add_row("Win Rate:", f"[{win_color}]{result.win_rate:.1f}%[/{win_color}]")
        
        table.add_row("", "")  # Espacio
        table.add_row("Máximo Drawdown:", f"{result.max_drawdown:.2f}%")
        table.add_row("Sharpe Ratio:", f"{result.sharpe_ratio:.2f}")
        
        console.print(table)
        
        # Gráfico simple de capital
        if result.trades:
            console.print("\n[bold]Evolución del Capital:[/bold]")
            
            capitals = [result.initial_capital] + [t['capital_after'] for t in result.trades]
            min_cap = min(capitals)
            max_cap = max(capitals)
            range_cap = max_cap - min_cap if max_cap > min_cap else 1
            
            for i, cap in enumerate(capitals[::max(1, len(capitals)//20)]):  # Máximo 20 puntos
                normalized = (cap - min_cap) / range_cap * 20
                bar = "█" * int(normalized)
                console.print(f"[dim]{i*len(capitals)//20:3d}[/dim] {bar} [green]{cap:.2f}[/green]")
        
        console.print("\n[bold blue]═══════════════════════════════════════════════════════[/bold blue]\n")
