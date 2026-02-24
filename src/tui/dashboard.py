"""
Dashboard TUI (Text User Interface) para el bot de arbitraje.
Usa Rich para una interfaz de consola moderna y informativa.
"""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from ..utils import Config, setup_logger


class TUIDashboard:
    """
    Dashboard en consola para monitorear el bot.
    
    Muestra:
    - Estado del bot
    - Balances
    - Posiciones activas
    - Estadísticas
    - Últimas noticias
    - Logs recientes
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.console = Console()
        self.logger = setup_logger("tui.dashboard")
        
        self.is_running = False
        self.data: Dict = self._get_empty_data()
        self.update_interval = 1  # Segundos
    
    def _get_empty_data(self) -> Dict:
        """Devuelve estructura vacía de datos."""
        return {
            'bot_status': 'stopped',
            'uptime': '00:00:00',
            'binance_balance': {'USDT': 0, 'ARS': 0},
            'argentine_balance': {'USDT': 0, 'ARS': 0},
            'total_balance_usdt': 0,
            'active_positions': [],
            'statistics': {
                'total_trades': 0,
                'profitable_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'total_volume': 0,
                'avg_profit_per_trade': 0,
            },
            'market_analysis': {
                'sentiment': 'neutral',
                'impact': 'neutral',
                'confidence': 0,
                'recommendation': 'HOLD',
            },
            'recent_news': [],
            'ml_stats': {
                'is_trained': False,
                'training_data_size': 0,
                'recent_win_rate': 0,
            },
            'last_update': datetime.now(),
        }
    
    def update_data(self, data: Dict) -> None:
        """Actualiza los datos del dashboard."""
        self.data.update(data)
        self.data['last_update'] = datetime.now()
    
    def _create_header(self) -> Panel:
        """Crea el encabezado del dashboard."""
        status_color = "green" if self.data['bot_status'] == 'running' else "red"
        status_text = f"[{status_color}]●[/{status_color}]"
        
        title = Text()
        title.append("🤖 ARBITRAGE BOT - USDT/ARS ", style="bold blue")
        title.append(status_text)
        title.append(f" {self.data['bot_status'].upper()}", style=status_color)
        
        subtitle = Text()
        subtitle.append(f"Uptime: {self.data['uptime']} | ", style="dim")
        subtitle.append(f"Última actualización: {self.data['last_update'].strftime('%H:%M:%S')}", style="dim")
        
        header = Panel(
            Text.assemble(title, "\n", subtitle),
            title="ARBITRAGE BOT",
            subtitle="Linux/Windows/Mac Compatible",
            box=box.DOUBLE,
        )
        
        return header
    
    def _create_balance_panel(self) -> Panel:
        """Crea el panel de balances."""
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("Exchange", style="cyan")
        table.add_column("USDT", justify="right", style="green")
        table.add_column("ARS", justify="right", style="yellow")
        
        binance = self.data['binance_balance']
        argentine = self.data['argentine_balance']
        
        table.add_row(
            "Binance",
            f"{binance.get('USDT', 0):.2f}",
            f"{binance.get('ARS', 0):.2f}",
        )
        table.add_row(
            f"{self.config.argentine_exchange.title()}",
            f"{argentine.get('USDT', 0):.2f}",
            f"{argentine.get('ARS', 0):.2f}",
        )
        
        total_usdt = self.data['total_balance_usdt']
        initial = self.config.initial_capital
        profit = total_usdt - initial
        profit_color = "green" if profit >= 0 else "red"
        
        summary = Text()
        summary.append(f"\nTotal: ", style="bold")
        summary.append(f"{total_usdt:.2f} USDT", style="bold white")
        summary.append(f" | Inicial: {initial} USDT", style="dim")
        summary.append(f" | P/L: ", style="dim")
        summary.append(f"{profit:+.2f} USDT", style=profit_color)

        # Usar Group para combinar tabla y texto en el Panel
        from rich.console import Group
        return Panel(
            Group(table, summary),
            title="💰 BALANCES",
            box=box.ROUNDED,
        )
    
    def _create_statistics_panel(self) -> Panel:
        """Crea el panel de estadísticas."""
        stats = self.data['statistics']
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right", style="white")
        
        win_rate_color = "green" if stats['win_rate'] >= 50 else "yellow"
        profit_color = "green" if stats['total_profit'] >= 0 else "red"
        
        table.add_row("Total Trades:", str(stats['total_trades']))
        table.add_row("Win Rate:", f"[{win_rate_color}]{stats['win_rate']:.1f}%[/{win_rate_color}]")
        table.add_row("Profitable:", str(stats['profitable_trades']))
        table.add_row("Total Profit:", f"[{profit_color}]{stats['total_profit']:+.2f} USDT[/{profit_color}]")
        table.add_row("Volume:", f"{stats['total_volume']:.2f} USDT")
        table.add_row("Avg Profit/Trade:", f"{stats['avg_profit_per_trade']:.3f} USDT")
        
        return Panel(table, title="📊 ESTADÍSTICAS", box=box.ROUNDED)
    
    def _create_positions_panel(self) -> Panel:
        """Crea el panel de posiciones activas."""
        positions = self.data['active_positions']
        
        if not positions:
            return Panel(
                Text("No hay posiciones activas", style="dim italic"),
                title="📈 POSICIONES ACTIVAS",
                box=box.ROUNDED,
            )
        
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("ID", style="cyan")
        table.add_column("Tipo", style="yellow")
        table.add_column("Monto", justify="right", style="white")
        table.add_column("Profit", justify="right", style="green")
        
        for pos in positions:
            profit_color = "green" if pos.get('profit', 0) >= 0 else "red"
            table.add_row(
                pos.get('id', 'N/A'),
                pos.get('type', 'N/A'),
                f"{pos.get('entry_amount', 0):.2f} USDT",
                f"[{profit_color}]{pos.get('profit', 0):+.2f}[/{profit_color}]",
            )
        
        return Panel(
            table,
            title=f"📈 POSICIONES ACTIVAS ({len(positions)})",
            box=box.ROUNDED,
        )
    
    def _create_market_panel(self) -> Panel:
        """Crea el panel de análisis de mercado."""
        analysis = self.data['market_analysis']
        
        sentiment_colors = {
            'positive': 'green',
            'negative': 'red',
            'neutral': 'yellow',
        }
        
        impact_colors = {
            'high_up': 'red',
            'medium_up': 'orange_red1',
            'low_up': 'yellow',
            'neutral': 'white',
            'low_down': 'light_green',
            'medium_down': 'green',
            'high_down': 'dark_green',
        }
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right")
        
        sentiment_color = sentiment_colors.get(analysis.get('sentiment', 'neutral'), 'white')
        impact_color = impact_colors.get(analysis.get('impact', 'neutral'), 'white')
        
        table.add_row("Sentimiento:", f"[{sentiment_color}]{analysis.get('sentiment', 'N/A').upper()}[/{sentiment_color}]")
        table.add_row("Impacto:", f"[{impact_color}]{analysis.get('impact', 'N/A').upper()}[/{impact_color}]")
        table.add_row("Confianza:", f"{analysis.get('confidence', 0):.1%}")
        
        rec = analysis.get('recommendation', 'HOLD')
        rec_color = 'green' if rec == 'BUY_USDT' else 'red' if rec == 'SELL_USDT' else 'yellow'
        table.add_row("Recomendación:", f"[{rec_color}]{rec}[/{rec_color}]")
        
        return Panel(table, title="📰 ANÁLISIS DE MERCADO", box=box.ROUNDED)
    
    def _create_ml_panel(self) -> Panel:
        """Crea el panel de ML."""
        ml_stats = self.data['ml_stats']
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right", style="white")
        
        trained_color = "green" if ml_stats.get('is_trained', False) else "yellow"
        
        table.add_row("Estado:", f"[{trained_color}]{'ENTRENADO' if ml_stats.get('is_trained') else 'NO ENTRENADO'}[/{trained_color}]")
        table.add_row("Datos:", str(ml_stats.get('training_data_size', 0)))
        table.add_row("Win Rate Reciente:", f"{ml_stats.get('recent_win_rate', 0):.1%}")
        
        return Panel(table, title="🤖 MACHINE LEARNING", box=box.ROUNDED)
    
    def _create_news_panel(self) -> Panel:
        """Crea el panel de noticias recientes."""
        news = self.data.get('recent_news', [])
        
        if not news:
            return Panel(
                Text("Sin noticias recientes", style="dim italic"),
                title="📰 NOTICIAS",
                box=box.ROUNDED,
            )
        
        news_text = Text()
        for i, n in enumerate(news[:5], 1):  # Máximo 5 noticias
            sentiment_color = "green" if n.get('sentiment') == 'positive' else "red" if n.get('sentiment') == 'negative' else "yellow"
            
            news_text.append(f"{i}. ", style="dim")
            news_text.append(f"[{n.get('source', 'Unknown').upper()}] ", style="cyan")
            news_text.append(f"[{sentiment_color}]{n.get('title', 'Sin título')[:50]}...[/{sentiment_color}]", style="white")
            news_text.append("\n", style="")
        
        return Panel(news_text, title="📰 NOTICIAS RECIENTES", box=box.ROUNDED)
    
    def _create_layout(self) -> Layout:
        """Crea el layout principal del dashboard."""
        layout = Layout()
        
        # Dividir en secciones
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )
        
        # Columna izquierda
        layout["left"].split(
            Layout(name="balances"),
            Layout(name="statistics"),
            Layout(name="positions"),
        )
        
        # Columna derecha
        layout["right"].split(
            Layout(name="market"),
            Layout(name="ml"),
            Layout(name="news"),
        )
        
        return layout
    
    def _render(self) -> Layout:
        """Renderiza el dashboard completo."""
        layout = self._create_layout()
        
        layout["header"].update(self._create_header())
        layout["balances"].update(self._create_balance_panel())
        layout["statistics"].update(self._create_statistics_panel())
        layout["positions"].update(self._create_positions_panel())
        layout["market"].update(self._create_market_panel())
        layout["ml"].update(self._create_ml_panel())
        layout["news"].update(self._create_news_panel())
        
        return layout
    
    async def start(self) -> None:
        """Inicia el dashboard en modo live."""
        self.is_running = True
        self.logger.info("🖥️ Dashboard TUI iniciado")
        
        with Live(self._render(), console=self.console, refresh_per_second=1, screen=True) as live:
            while self.is_running:
                await asyncio.sleep(self.update_interval)
                live.update(self._render())
    
    async def stop(self) -> None:
        """Detiene el dashboard."""
        self.is_running = False
        self.logger.info("🖥️ Dashboard TUI detenido")
    
    def print_summary(self) -> None:
        """Imprime un resumen estático (para logs)."""
        self.console.print("\n" + "=" * 60)
        self.console.print("[bold blue]ARBITRAGE BOT - RESUMEN[/bold blue]")
        self.console.print("=" * 60)
        
        stats = self.data['statistics']
        self.console.print(f"\n[bold]Total Trades:[/bold] {stats['total_trades']}")
        self.console.print(f"[bold]Win Rate:[/bold] {stats['win_rate']:.1f}%")
        self.console.print(f"[bold]Total Profit:[/bold] {'green' if stats['total_profit'] >= 0 else 'red'}]{stats['total_profit']:+.2f} USDT[/]")
        self.console.print(f"[bold]Active Positions:[/bold] {len(self.data['active_positions'])}")
        
        self.console.print("\n" + "=" * 60)
