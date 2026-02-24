"""
Rastreador de Oportunidades FLASH en CriptoYa.
Detecta spreads anormales (>10%, >20%, >50%) y alerta en tiempo real.
IMPORTANTE: La mayoría son errores de datos o P2P, no arbitraje real ejecutable.
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List


class CriptoYaFlashOpportunityTracker:
    """
    Rastrea oportunidades de arbitraje FLASH en CriptoYa.
    Detecta spreads anormales y los reporta en tiempo real.
    """

    def __init__(self):
        self.base_url = "https://criptoya.com/api"
        self.session = None
        self.exchanges = [
            'binance', 'lemoncash', 'buenbit', 'ripio', 'belobit',
            'letsbit', 'cryptomkt', 'bitso', 'fiwind', 'tiendacrypto',
            'eluter', 'universalcoin', 'p2p', 'huobi', 'kucoin',
            'bitget', 'coinex', 'bingx', 'weex', 'trubit'
        ]
        self.opportunities_found = []
        self.flash_thresholds = [10, 20, 30, 50]  # Umbrales de spread %

    async def start(self, duration_seconds=300):
        """Inicia el rastreo por N segundos."""
        print("=" * 80)
        print("🔍 RASTREADOR DE OPORTUNIDADES FLASH - CRIPTOYA")
        print("=" * 80)
        print(f"⏱️  Duración: {duration_seconds} segundos")
        print(f"📊 Exchanges monitoreados: {len(self.exchanges)}")
        print(f"🎯 Umbrales: {self.flash_thresholds}%")
        print("=" * 80)
        print()

        async with aiohttp.ClientSession() as self.session:
            start_time = datetime.now()
            iteration = 0

            while (datetime.now() - start_time).total_seconds() < duration_seconds:
                iteration += 1
                print(f"\n[{iteration}] {datetime.now().strftime('%H:%M:%S')} - Consultando precios...")

                # Obtener todos los precios
                prices = await self.get_all_prices()

                if prices:
                    # Buscar oportunidades
                    opportunities = self.find_opportunities(prices)

                    if opportunities:
                        for opp in opportunities:
                            self.opportunities_found.append(opp)
                            self.print_opportunity(opp)
                    else:
                        print("   No hay oportunidades >10%")

                await asyncio.sleep(5)  # Consultar cada 5 segundos

            # Resumen final
            self.print_summary()

    async def get_all_prices(self) -> Dict:
        """Obtiene precios de todos los exchanges."""
        prices = {}

        tasks = []
        for ex in self.exchanges:
            task = self.get_exchange_price(ex)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, dict) and result.get('ask', 0) > 0:
                prices[self.exchanges[i]] = result

        return prices

    async def get_exchange_price(self, exchange: str) -> Dict:
        """Obtiene precio de un exchange específico."""
        try:
            url = f"{self.base_url}/{exchange}/USDT/ARS/0.1"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await resp.json()
                        return {
                            'exchange': exchange,
                            'bid': float(data.get('bid', 0)),
                            'ask': float(data.get('ask', 0)),
                            'price': float(data.get('price', data.get('ask', 0))),
                            'timestamp': datetime.now(),
                        }
        except:
            pass

        return {}

    def find_opportunities(self, prices: Dict) -> List[Dict]:
        """Busca oportunidades con spread >10%."""
        opportunities = []

        if len(prices) < 2:
            return opportunities

        # Ordenar por precio de compra (ask)
        sorted_by_ask = sorted(prices.items(), key=lambda x: x[1]['ask'])
        sorted_by_bid = sorted(prices.items(), key=lambda x: x[1]['bid'], reverse=True)

        # Buscar mejor oportunidad
        cheapest = sorted_by_ask[0]
        most_expensive = sorted_by_bid[0]

        buy_price = cheapest[1]['ask']
        sell_price = most_expensive[1]['bid']

        if buy_price > 0 and sell_price > buy_price:
            spread = sell_price - buy_price
            spread_pct = (spread / buy_price) * 100

            # Solo reportar si spread > 10%
            if spread_pct >= 10:
                # Calcular con fees
                fees_usdt = 2  # Withdrawal fees
                fees_ars = fees_usdt * buy_price
                trading_fees = (buy_price * 0.001) + (sell_price * 0.0005)

                # Simular con 7 USDT
                capital_usdt = 7
                invested_ars = capital_usdt * buy_price
                received_ars = (capital_usdt - fees_usdt) * sell_price - trading_fees
                profit_ars = received_ars - invested_ars
                profit_pct = (profit_ars / invested_ars) * 100

                opp = {
                    'timestamp': datetime.now(),
                    'buy_exchange': cheapest[0],
                    'sell_exchange': most_expensive[0],
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'spread': spread,
                    'spread_percent': spread_pct,
                    'fees_ars': fees_ars + trading_fees,
                    'profit_ars_7usdt': profit_ars,
                    'profit_percent_7usdt': profit_pct,
                    'is_profitable': profit_ars > 0,
                }

                opportunities.append(opp)

        return opportunities

    def print_opportunity(self, opp: Dict):
        """Imprime una oportunidad encontrada."""
        icon = "✅" if opp['is_profitable'] else "❌"
        flash_icon = "⚡" if opp['spread_percent'] >= 50 else "🔶" if opp['spread_percent'] >= 20 else "🟡"

        print()
        print(f"{icon} {flash_icon} OPORTUNIDAD DETECTADA {flash_icon}")
        print(f"   Hora: {opp['timestamp'].strftime('%H:%M:%S')}")
        print(f"   Comprar en: {opp['buy_exchange'].upper()} a ${opp['buy_price']:.2f}")
        print(f"   Vender en:  {opp['sell_exchange'].upper()} a ${opp['sell_price']:.2f}")
        print(f"   Spread: {opp['spread_percent']:.2f}% (${opp['spread']:.2f})")
        print()
        print(f"   💰 CON 7 USDT:")
        print(f"      Fees: ${opp['fees_ars']:.2f} ARS")
        print(f"      Profit: ${opp['profit_ars_7usdt']:.2f} ARS ({opp['profit_percent_7usdt']:.2f}%)")
        print(f"      Resultado: {'✅ RENTABLE' if opp['is_profitable'] else '❌ NO RENTABLE'}")
        print("=" * 80)

    def print_summary(self):
        """Imprime resumen final."""
        print()
        print("=" * 80)
        print("📊 RESUMEN DEL RASTREO")
        print("=" * 80)
        print(f"Oportunidades encontradas: {len(self.opportunities_found)}")

        if self.opportunities_found:
            # Agrupar por umbral
            over_10 = [o for o in self.opportunities_found if o['spread_percent'] >= 10]
            over_20 = [o for o in self.opportunities_found if o['spread_percent'] >= 20]
            over_50 = [o for o in self.opportunities_found if o['spread_percent'] >= 50]
            profitable = [o for o in self.opportunities_found if o['is_profitable']]

            print(f"   >10% spread: {len(over_10)}")
            print(f"   >20% spread: {len(over_20)}")
            print(f"   >50% spread: {len(over_50)}")
            print(f"   ✅ Rentables: {len(profitable)}")

            if profitable:
                print()
                print("🏆 MEJORES OPORTUNIDADES RENTABLES:")
                profitable_sorted = sorted(profitable, key=lambda x: x['profit_ars_7usdt'], reverse=True)
                for i, opp in enumerate(profitable_sorted[:5], 1):
                    print(f"   {i}. {opp['buy_exchange']} → {opp['sell_exchange']}: ${opp['profit_ars_7usdt']:.2f} ARS")
            else:
                print()
                print("⚠️  NINGUNA oportunidad fue rentable con 7 USDT")
                print("   Razón: Fees fijos (2 USDT) > Spread")
        else:
            print("   No se encontraron oportunidades significativas")

        print("=" * 80)


async def main():
    tracker = CriptoYaFlashOpportunityTracker()
    await tracker.start(duration_seconds=120)  # 2 minutos de rastreo


if __name__ == '__main__':
    asyncio.run(main())
