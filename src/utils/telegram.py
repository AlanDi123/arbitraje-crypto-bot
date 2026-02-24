"""
Módulo de notificaciones por Telegram.
Envía alertas y actualizaciones del bot.
"""

import asyncio
from typing import Optional, Dict
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

from ..utils import Config, setup_logger


class TelegramNotifier:
    """
    Envía notificaciones a Telegram sobre el estado del bot.
    
    Notificaciones:
    - Inicio/parada del bot
    - Operaciones abiertas/cerradas
    - Errores críticos
    - Oportunidades de arbitraje
    - Resumen periódico
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger("telegram.notifier")
        
        self.bot: Optional[Bot] = None
        self.chat_id = config.telegram_chat_id
        self.token = config.telegram_token
        
        self.is_running = False
        self.enabled = bool(self.token and self.chat_id)
        
        if not self.enabled:
            self.logger.warning("⚠️ Telegram no configurado - notificaciones deshabilitadas")
    
    async def start(self) -> None:
        """Inicia el bot de Telegram."""
        if not self.enabled:
            return
        
        try:
            self.bot = Bot(token=self.token)
            
            # Verificar conexión
            await self.bot.get_me()
            
            self.is_running = True
            self.logger.info("📱 Telegram notifier iniciado")
            
            # Enviar mensaje de inicio
            await self.send_message(
                "🤖 *ARBITRAGE BOT INICIADO*\n\n"
                "El bot de arbitraje USDT/ARS está ahora en ejecución.\n"
                f"_Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
            )
            
        except TelegramError as e:
            self.logger.error(f"Error iniciando Telegram: {e}")
            self.enabled = False
    
    async def stop(self) -> None:
        """Detiene el bot de Telegram."""
        if not self.enabled or not self.is_running:
            return
        
        try:
            await self.send_message(
                "🛑 *ARBITRAGE BOT DETENIDO*\n\n"
                "El bot ha sido detenido.\n"
                f"_Parada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
            )
            
            if self.bot:
                await self.bot.close()
            
            self.is_running = False
            self.logger.info("📱 Telegram notifier detenido")
            
        except TelegramError as e:
            self.logger.error(f"Error deteniendo Telegram: {e}")
    
    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Envía un mensaje a Telegram."""
        if not self.enabled or not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            return True
            
        except TelegramError as e:
            self.logger.error(f"Error enviando mensaje: {e}")
            return False
    
    async def notify_trade_open(
        self,
        position_id: str,
        exchange_pair: str,
        amount: float,
        entry_price: float,
        estimated_profit: float,
        estimated_profit_percent: float,
    ) -> None:
        """Notifica la apertura de una operación."""
        message = (
            f"📈 *OPERACIÓN ABIERTA*\n\n"
            f"`{position_id}`\n\n"
            f"*Exchange:* {exchange_pair}\n"
            f"*Monto:* {amount:.2f} USDT\n"
            f"*Precio Entrada:* {entry_price:.2f} ARS\n\n"
            f"*Ganancia Estimada:*\n"
            f"`{estimated_profit:+.2f} USDT ({estimated_profit_percent:+.2f}%)`"
        )
        
        await self.send_message(message)
    
    async def notify_trade_close(
        self,
        position_id: str,
        exchange_pair: str,
        amount: float,
        entry_price: float,
        exit_price: float,
        profit: float,
        profit_percent: float,
    ) -> None:
        """Notifica el cierre de una operación."""
        emoji = "✅" if profit > 0 else "❌"
        profit_color = "🟢" if profit > 0 else "🔴"
        
        message = (
            f"{emoji} *OPERACIÓN CERRADA* {profit_color}\n\n"
            f"`{position_id}`\n\n"
            f"*Exchange:* {exchange_pair}\n"
            f"*Monto:* {amount:.2f} USDT\n"
            f"*Entrada:* {entry_price:.2f} ARS\n"
            f"*Salida:* {exit_price:.2f} ARS\n\n"
            f"*Resultado:*\n"
            f"`{profit:+.2f} USDT ({profit_percent:+.2f}%)`"
        )
        
        await self.send_message(message)
    
    async def notify_arbitrage_opportunity(
        self,
        buy_exchange: str,
        sell_exchange: str,
        spread_percent: float,
        estimated_profit_percent: float,
    ) -> None:
        """Notifica una oportunidad de arbitraje detectada."""
        message = (
            f"💰 *OPORTUNIDAD DETECTADA*\n\n"
            f"*Comprar:* {buy_exchange}\n"
            f"*Vender:* {sell_exchange}\n\n"
            f"*Spread:* {spread_percent:.2f}%\n"
            f"*Profit Est:* {estimated_profit_percent:.2f}%"
        )
        
        await self.send_message(message)
    
    async def notify_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None,
    ) -> None:
        """Notifica un error crítico."""
        context_str = f"\n*Contexto:* `{context}`" if context else ""
        
        message = (
            f"🚨 *ERROR CRÍTICO*\n\n"
            f"*Tipo:* {error_type}\n"
            f"*Mensaje:* `{error_message}`"
            f"{context_str}\n\n"
            f"_Requiere atención inmediata_"
        )
        
        await self.send_message(message)
    
    async def notify_market_analysis(
        self,
        sentiment: str,
        impact: str,
        recommendation: str,
        confidence: float,
    ) -> None:
        """Notifica el análisis de mercado."""
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(sentiment, "⚪")
        
        message = (
            f"📰 *ANÁLISIS DE MERCADO* {sentiment_emoji}\n\n"
            f"*Sentimiento:* {sentiment.upper()}\n"
            f"*Impacto:* {impact.upper()}\n"
            f"*Confianza:* {confidence:.1%}\n"
            f"*Recomendación:* `{recommendation}`"
        )
        
        await self.send_message(message)
    
    async def notify_daily_summary(
        self,
        total_trades: int,
        profitable_trades: int,
        total_profit: float,
        win_rate: float,
        total_volume: float,
    ) -> None:
        """Envía un resumen diario."""
        emoji = "📈" if total_profit > 0 else "📉"
        
        message = (
            f"{emoji} *RESUMEN DIARIO*\n\n"
            f"*Operaciones:* {total_trades}\n"
            f"*Ganadoras:* {profitable_trades}\n"
            f"*Win Rate:* {win_rate:.1f}%\n\n"
            f"*Volumen:* {total_volume:.2f} USDT\n"
            f"*Profit:* `{total_profit:+.2f} USDT`"
        )
        
        await self.send_message(message)
    
    async def notify_balance_update(
        self,
        total_balance: float,
        initial_balance: float,
        profit: float,
    ) -> None:
        """Notifica una actualización de balance."""
        emoji = "🟢" if profit >= 0 else "🔴"
        
        message = (
            f"💰 *ACTUALIZACIÓN DE BALANCE* {emoji}\n\n"
            f"*Total:* {total_balance:.2f} USDT\n"
            f"*Inicial:* {initial_balance:.2f} USDT\n"
            f"*P/L:* `{profit:+.2f} USDT ({(profit/initial_balance)*100:+.2f}%)`"
        )
        
        await self.send_message(message)
