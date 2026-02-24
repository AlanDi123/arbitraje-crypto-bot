"""
Módulo de monitoreo de noticias en tiempo real.
Analiza noticias argentinas para predecir impacto en el precio USDT/ARS.
"""

import asyncio
import aiohttp
import feedparser
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import re

from ..utils import Config, setup_logger


class NewsSentiment(Enum):
    """Sentimiento de la noticia."""
    POSITIVE = "positive"  # Bueno para ARS (USDT baja)
    NEGATIVE = "negative"  # Malo para ARS (USDT sube)
    NEUTRAL = "neutral"


class NewsImpact(Enum):
    """Impacto esperado en el precio."""
    HIGH_UP = "high_up"  # USDT/ARS sube mucho
    MEDIUM_UP = "medium_up"  # USDT/ARS sube
    LOW_UP = "low_up"  # USDT/ARS sube poco
    NEUTRAL = "neutral"  # Sin impacto
    LOW_DOWN = "low_down"  # USDT/ARS baja poco
    MEDIUM_DOWN = "medium_down"  # USDT/ARS baja
    HIGH_DOWN = "high_down"  # USDT/ARS baja mucho


@dataclass
class NewsItem:
    """Representa una noticia."""
    title: str
    summary: str
    source: str
    url: str
    published: datetime
    sentiment: NewsSentiment
    impact: NewsImpact
    confidence: float
    keywords: List[str]


class NewsAnalyzer:
    """
    Analiza noticias argentinas para predecir impacto en USDT/ARS.
    
    Fuentes gratuitas:
    - Infobae (RSS)
    - Clarín (RSS)
    - Página/12 (RSS)
    - Twitter (limitado sin API)
    """
    
    # Fuentes de RSS gratuitas
    RSS_FEEDS = {
        'infobae': {
            'url': 'https://www.infobae.com/arc/feeds/1.0/rss/home/latest/',
            'economy_url': 'https://www.infobae.com/arc/feeds/1.0/rss/economia/latest/',
        },
        'clarin': {
            'url': 'https://www.clarin.com/rss/portada/',
            'economy_url': 'https://www.clarin.com/rss/economia/',
        },
        'pagina12': {
            'url': 'https://www.pagina12.com.ar/rss/seccion/portada',
            'economy_url': 'https://www.pagina12.com.ar/rss/seccion/economia',
        },
    }
    
    # Palabras clave para clasificación
    KEYWORDS_POSITIVE_ARS = [
        'superávit', 'reservas suben', 'dólar baja', 'peso se fortalece',
        'acuerdo FMI', 'inversión extranjera', 'exportaciones suben',
        'recolección récord', 'industria crece', 'empleo aumenta',
        'inflación desacelera', 'riesgo país baja', 'bonos suben',
        'calificación crediticia', 'grado inversor', 'estabilidad económica',
        'medida favorable', 'anuncio positivo', 'éxito económico',
    ]
    
    KEYWORDS_NEGATIVE_ARS = [
        'déficit', 'reservas caen', 'dólar sube', 'peso se debilita',
        'default', 'cesación de pagos', 'crisis económica', 'recesión',
        'inflación acelera', 'devaluación', 'cepo cambiario', 'corralito',
        'riesgo país sube', 'bonos caen', 'fuga de capitales',
        'medida impopular', 'protesta económica', 'huelga', 'paro',
        'FMI rechaza', 'suspensión de pagos', 'emergencia económica',
    ]
    
    # Eventos de alto impacto
    HIGH_IMPACT_EVENTS = [
        'elecciones', 'presidente', 'ministro economía', 'BCRA', 'Banco Central',
        'FMI', 'deuda', 'default', 'restructuración', 'acuerdo',
        'devaluación', 'cepo', 'medida económica', 'anuncio económico',
        'presupuesto', 'impuestos', 'retenciones', 'exportación', 'importación',
    ]
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger("news.analyzer")
        self.session: Optional[aiohttp.ClientSession] = None
        self.news_cache: List[NewsItem] = []
        self.last_check: Optional[datetime] = None
        self.market_sentiment = NewsSentiment.NEUTRAL
        self.market_impact = NewsImpact.NEUTRAL
        self.confidence = 0.0
    
    async def start(self) -> None:
        """Inicia el analizador de noticias."""
        self.session = aiohttp.ClientSession()
        self.logger.info("📰 Analizador de noticias iniciado")
        
        while True:
            try:
                await self.check_news()
                await asyncio.sleep(self.config.news_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error en el loop de noticias: {e}")
                await asyncio.sleep(60)
    
    async def stop(self) -> None:
        """Detiene el analizador de noticias."""
        if self.session:
            await self.session.close()
        self.logger.info("📰 Analizador de noticias detenido")
    
    async def check_news(self) -> List[NewsItem]:
        """Verifica nuevas noticias en todas las fuentes."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        new_news = []
        
        for source, urls in self.RSS_FEEDS.items():
            try:
                # Verificar feed principal y de economía
                for feed_type, url in urls.items():
                    entries = await self._fetch_feed(url)
                    
                    for entry in entries:
                        news = self._parse_entry(entry, source)
                        
                        if news and self._is_new(news):
                            new_news.append(news)
                            self.logger.info(
                                f"📰 Nueva noticia de {source}: {news.title[:50]}... | "
                                f"Sentimiento: {news.sentiment.value} | "
                                f"Impacto: {news.impact.value}"
                            )
                
            except Exception as e:
                self.logger.error(f"Error verificando noticias de {source}: {e}")
        
        # Actualizar caché
        self.news_cache.extend(new_news)
        
        # Mantener solo últimas 100 noticias
        if len(self.news_cache) > 100:
            self.news_cache = self.news_cache[-100:]
        
        # Actualizar sentimiento del mercado
        if new_news:
            self._update_market_sentiment(new_news)
        
        self.last_check = datetime.now()
        
        return new_news
    
    async def _fetch_feed(self, url: str) -> List[Dict]:
        """Obtiene entradas de un feed RSS."""
        try:
            async with self.session.get(url, timeout=10) as response:
                content = await response.text()
                feed = feedparser.parse(content)
                
                return [
                    {
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', entry.get('description', '')),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                    }
                    for entry in feed.entries[:20]  # Últimas 20 entradas
                ]
        except Exception as e:
            self.logger.error(f"Error obteniendo feed {url}: {e}")
            return []
    
    def _parse_entry(self, entry: Dict, source: str) -> Optional[NewsItem]:
        """Analiza una entrada y determina sentimiento e impacto."""
        title = entry.get('title', '')
        summary = entry.get('summary', '')
        text = f"{title} {summary}".lower()
        
        # Determinar sentimiento
        sentiment, sentiment_confidence = self._analyze_sentiment(text)
        
        # Determinar impacto
        impact, impact_confidence = self._analyze_impact(text)
        
        # Calcular confianza combinada
        confidence = (sentiment_confidence + impact_confidence) / 2
        
        # Extraer keywords
        keywords = self._extract_keywords(text)
        
        # Parsear fecha
        published = self._parse_date(entry.get('published', ''))
        
        return NewsItem(
            title=title,
            summary=summary,
            source=source,
            url=entry.get('link', ''),
            published=published,
            sentiment=sentiment,
            impact=impact,
            confidence=confidence,
            keywords=keywords,
        )
    
    def _analyze_sentiment(self, text: str) -> Tuple[NewsSentiment, float]:
        """
        Analiza el sentimiento de una noticia.
        Returns: (sentimiento, confianza)
        """
        positive_count = sum(1 for kw in self.KEYWORDS_POSITIVE_ARS if kw in text)
        negative_count = sum(1 for kw in self.KEYWORDS_NEGATIVE_ARS if kw in text)
        
        total = positive_count + negative_count
        
        if total == 0:
            return NewsSentiment.NEUTRAL, 0.5
        
        # Calcular confianza basada en cantidad de keywords encontradas
        confidence = min(total / 5, 1.0)  # Máximo 1.0 con 5+ keywords
        
        if positive_count > negative_count:
            return NewsSentiment.POSITIVE, confidence
        elif negative_count > positive_count:
            return NewsSentiment.NEGATIVE, confidence
        else:
            return NewsSentiment.NEUTRAL, 0.5
    
    def _analyze_impact(self, text: str) -> Tuple[NewsImpact, float]:
        """
        Analiza el impacto esperado en el precio USDT/ARS.
        Returns: (impacto, confianza)
        """
        # Verificar eventos de alto impacto
        high_impact_count = sum(1 for event in self.HIGH_IMPACT_EVENTS if event.lower() in text)
        
        # Determinar dirección basada en sentimiento
        sentiment, sentiment_conf = self._analyze_sentiment(text)
        
        # Calcular confianza
        confidence = min(high_impact_count / 3, 1.0)
        confidence = max(confidence, sentiment_conf * 0.8)
        
        if high_impact_count >= 3:
            if sentiment == NewsSentiment.NEGATIVE:
                return NewsImpact.HIGH_UP, confidence  # USDT sube mucho
            elif sentiment == NewsSentiment.POSITIVE:
                return NewsImpact.HIGH_DOWN, confidence  # USDT baja mucho
        elif high_impact_count >= 1:
            if sentiment == NewsSentiment.NEGATIVE:
                return NewsImpact.MEDIUM_UP, confidence
            elif sentiment == NewsSentiment.POSITIVE:
                return NewsImpact.MEDIUM_DOWN, confidence
        
        # Impacto bajo o neutral
        if sentiment == NewsSentiment.NEGATIVE:
            return NewsImpact.LOW_UP, confidence * 0.5
        elif sentiment == NewsSentiment.POSITIVE:
            return NewsImpact.LOW_DOWN, confidence * 0.5
        
        return NewsImpact.NEUTRAL, 0.5
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extrae keywords relevantes del texto."""
        found_keywords = []
        
        all_keywords = self.KEYWORDS_POSITIVE_ARS + self.KEYWORDS_NEGATIVE_ARS + self.HIGH_IMPACT_EVENTS
        
        for kw in all_keywords:
            if kw in text and kw not in found_keywords:
                found_keywords.append(kw)
        
        return found_keywords[:10]  # Máximo 10 keywords
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parsea una fecha de string a datetime."""
        formats = [
            '%a, %d %b %Y %H:%M:%S %Z',
            '%a, %d %b %Y %H:%M:%S %z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Convertir a naive datetime (sin timezone) para comparaciones consistentes
                if parsed.tzinfo is not None:
                    return parsed.replace(tzinfo=None)
                return parsed
            except ValueError:
                continue

        return datetime.now()

    def _is_new(self, news: NewsItem) -> bool:
        """Verifica si una noticia es nueva (últimos 30 minutos)."""
        thirty_min_ago = datetime.now() - timedelta(minutes=30)
        # Asegurar que ambas fechas sean naive para comparación
        news_date = news.published
        if news_date.tzinfo is not None:
            news_date = news_date.replace(tzinfo=None)
        return news_date > thirty_min_ago
    
    def _update_market_sentiment(self, new_news: List[NewsItem]) -> None:
        """Actualiza el sentimiento del mercado basado en noticias recientes."""
        if not new_news:
            return
        
        # Calcular promedio de sentimiento
        positive_count = sum(1 for n in new_news if n.sentiment == NewsSentiment.POSITIVE)
        negative_count = sum(1 for n in new_news if n.sentiment == NewsSentiment.NEGATIVE)
        
        total = len(new_news)
        
        # Determinar sentimiento predominante
        if positive_count > negative_count * 1.5:
            self.market_sentiment = NewsSentiment.POSITIVE
        elif negative_count > positive_count * 1.5:
            self.market_sentiment = NewsSentiment.NEGATIVE
        else:
            self.market_sentiment = NewsSentiment.NEUTRAL
        
        # Calcular impacto promedio
        impact_scores = {
            NewsImpact.HIGH_UP: 3,
            NewsImpact.MEDIUM_UP: 2,
            NewsImpact.LOW_UP: 1,
            NewsImpact.NEUTRAL: 0,
            NewsImpact.LOW_DOWN: -1,
            NewsImpact.MEDIUM_DOWN: -2,
            NewsImpact.HIGH_DOWN: -3,
        }
        
        avg_impact = sum(impact_scores.get(n.impact, 0) for n in new_news) / total
        
        if avg_impact >= 2:
            self.market_impact = NewsImpact.HIGH_UP
        elif avg_impact >= 1:
            self.market_impact = NewsImpact.MEDIUM_UP
        elif avg_impact >= 0.5:
            self.market_impact = NewsImpact.LOW_UP
        elif avg_impact <= -2:
            self.market_impact = NewsImpact.HIGH_DOWN
        elif avg_impact <= -1:
            self.market_impact = NewsImpact.MEDIUM_DOWN
        elif avg_impact <= -0.5:
            self.market_impact = NewsImpact.LOW_DOWN
        else:
            self.market_impact = NewsImpact.NEUTRAL
        
        # Calcular confianza promedio
        self.confidence = sum(n.confidence for n in new_news) / total
    
    def get_market_analysis(self) -> Dict:
        """
        Obtiene el análisis actual del mercado.
        Returns:
            Diccionario con sentimiento, impacto y recomendación
        """
        # Determinar recomendación de trading
        recommendation = "HOLD"
        
        if self.market_sentiment == NewsSentiment.POSITIVE:
            # ARS se fortalece, USDT baja - buen momento para comprar USDT
            if self.market_impact in [NewsImpact.MEDIUM_DOWN, NewsImpact.HIGH_DOWN]:
                recommendation = "BUY_USDT"
        elif self.market_sentiment == NewsSentiment.NEGATIVE:
            # ARS se debilita, USDT sube - buen momento para vender USDT
            if self.market_impact in [NewsImpact.MEDIUM_UP, NewsImpact.HIGH_UP]:
                recommendation = "SELL_USDT"
        
        return {
            'sentiment': self.market_sentiment.value,
            'impact': self.market_impact.value,
            'confidence': self.confidence,
            'recommendation': recommendation,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'recent_news_count': len([n for n in self.news_cache if self._is_new(n)]),
        }
    
    def should_pause_trading(self) -> bool:
        """
        Determina si el trading debe pausarse por noticias de alto impacto.
        """
        # Pausar si hay noticias de muy alto impacto con alta confianza
        if self.market_impact in [NewsImpact.HIGH_UP, NewsImpact.HIGH_DOWN]:
            if self.confidence > 0.8:
                self.logger.warning(
                    f"⚠️ PAUSANDO TRADING | Impacto: {self.market_impact.value} | "
                    f"Confianza: {self.confidence:.2f}"
                )
                return True
        
        return False
    
    def get_recent_news(self, limit: int = 10) -> List[Dict]:
        """Obtiene las noticias recientes."""
        recent = [n for n in self.news_cache if self._is_new(n)]
        recent.sort(key=lambda x: x.published, reverse=True)
        
        return [
            {
                'title': n.title,
                'source': n.source,
                'sentiment': n.sentiment.value,
                'impact': n.impact.value,
                'published': n.published.isoformat(),
                'url': n.url,
            }
            for n in recent[:limit]
        ]
