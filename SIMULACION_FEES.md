# 📊 SIMULACIÓN DE ARBITRAJE CON FEES REALES

## ⚙️ CONFIGURACIÓN ACTUAL

### Fees de los Exchanges (2025-2026)

| Exchange | Retiro USDT (TRC20) | Retiro ARS | Depósito ARS | Trading Fee | Promo |
|----------|---------------------|------------|--------------|-------------|-------|
| **Binance** | 1.0 USDT | $0 | $0 | 0.10% | ✅ Hasta Dic 2025 |
| **MEXC** | 1.0 USDT | $0 | $0 | 0.05% | ✅ Hasta Feb 20, 2026 |
| **CryptoMarket** | 2.0 USDT | $0 | $0 | 0.50% | ❌ |
| **Bitso** | 5.0 USDT | $0 | $0 | 0.50% | ❌ |

### Fees Totales por Ciclo (Binance ↔ MEXC)

```
Fee Fijo: 2 USDT (1 USDT Binance + 1 USDT MEXC)
Fee Variable: 0.15% (0.10% Binance + 0.05% MEXC)
```

---

## 🧮 SIMULACIONES CON DIFERENTES MONTOS

### Escenario 1: Capital BAJO (7 USDT = ~$10,500 ARS)

```
DATOS:
  Capital: 7 USDT
  Precio Binance: $1,458 ARS/USDT
  Precio MEXC: $1,470 ARS/USDT
  Spread: 0.82%

OPERACIÓN:
  1. Compras 7 USDT en Binance: 7 × $1,458 = $10,206 ARS
  2. Trading fee Binance (0.10%): $10.21 ARS
  3. Transfieres 7 USDT a MEXC
  4. Withdrawal fee (1 USDT): 1 USDT = $1,470 ARS
  5. Vendes 6 USDT en MEXC (7 - 1 fee): 6 × $1,470 = $8,820 ARS
  6. Trading fee MEXC (0.05%): $4.41 ARS

RESULTADO:
  Invertido: $10,206 ARS
  Recibido: $8,820 - $4.41 = $8,815.59 ARS
  Profit BRUTO: $8,820 - $10,206 = -$1,386 ARS ❌
  Fees TOTALES: $10.21 + $1,470 + $4.41 = $1,484.62 ARS
  Profit NETO: -$1,386 - $1,484.62 = -$2,870.62 ARS ❌❌❌
  
  PERDIDA: -28.1% del capital
  
CONCLUSIÓN: ❌ NO RENTABLE
  Con 7 USDT, los fees fijos (2 USDT) representan 28.6% del capital.
  Necesitas un spread de AL MENOS 29% para recuperar, lo cual es imposible.
```

---

### Escenario 2: Capital MEDIO (100 USDT = ~$150,000 ARS)

```
DATOS:
  Capital: 100 USDT
  Precio Binance: $1,458 ARS/USDT
  Precio MEXC: $1,470 ARS/USDT
  Spread: 0.82%

OPERACIÓN:
  1. Compras 100 USDT en Binance: 100 × $1,458 = $145,800 ARS
  2. Trading fee Binance (0.10%): $145.80 ARS
  3. Transfieres 100 USDT a MEXC
  4. Withdrawal fee (1 USDT): 1 USDT = $1,470 ARS
  5. Vendes 99 USDT en MEXC (100 - 1 fee): 99 × $1,470 = $145,530 ARS
  6. Trading fee MEXC (0.05%): $72.77 ARS

RESULTADO:
  Invertido: $145,800 ARS
  Recibido: $145,530 - $72.77 = $145,457.23 ARS
  Profit BRUTO: $145,530 - $145,800 = -$270 ARS
  Fees TOTALES: $145.80 + $1,470 + $72.77 = $1,688.57 ARS
  Profit NETO: -$270 - $1,688.57 = -$1,958.57 ARS
  
  PERDIDA: -1.34% del capital
  
CONCLUSIÓN: ❌ NO RENTABLE
  Con 100 USDT, los fees fijos (2 USDT) representan 2% del capital.
  El spread de 0.82% no cubre los fees fijos + variables.
  Necesitas AL MENOS 2.2% de spread para ser rentable.
```

---

### Escenario 3: Capital MÍNIMO RECOMENDADO (333 USDT = ~$500,000 ARS)

```
DATOS:
  Capital: 333 USDT
  Precio Binance: $1,458 ARS/USDT
  Precio MEXC: $1,470 ARS/USDT
  Spread: 0.82%

OPERACIÓN:
  1. Compras 333 USDT en Binance: 333 × $1,458 = $485,514 ARS
  2. Trading fee Binance (0.10%): $485.51 ARS
  3. Transfieres 333 USDT a MEXC
  4. Withdrawal fee (1 USDT): 1 USDT = $1,470 ARS
  5. Vendes 332 USDT en MEXC (333 - 1 fee): 332 × $1,470 = $488,040 ARS
  6. Trading fee MEXC (0.05%): $244.02 ARS

RESULTADO:
  Invertido: $485,514 ARS
  Recibido: $488,040 - $244.02 = $487,795.98 ARS
  Profit BRUTO: $488,040 - $485,514 = $2,526 ARS
  Fees TOTALES: $485.51 + $1,470 + $244.02 = $2,199.53 ARS
  Profit NETO: $2,526 - $2,199.53 = $326.47 ARS
  
  GANANCIA: +0.067% del capital
  
CONCLUSIÓN: ⚠️ MARGINALMENTE RENTABLE
  Con 333 USDT, los fees fijos (2 USDT) representan 0.6% del capital.
  El spread de 0.82% apenas cubre los fees.
  Profit muy bajo, pero positivo.
```

---

### Escenario 4: Capital ÓPTIMO (1,000 USDT = ~$1,500,000 ARS)

```
DATOS:
  Capital: 1,000 USDT
  Precio Binance: $1,458 ARS/USDT
  Precio MEXC: $1,470 ARS/USDT
  Spread: 0.82%

OPERACIÓN:
  1. Compras 1,000 USDT en Binance: 1,000 × $1,458 = $1,458,000 ARS
  2. Trading fee Binance (0.10%): $1,458 ARS
  3. Transfieres 1,000 USDT a MEXC
  4. Withdrawal fee (1 USDT): 1 USDT = $1,470 ARS
  5. Vendes 999 USDT en MEXC (1,000 - 1 fee): 999 × $1,470 = $1,468,530 ARS
  6. Trading fee MEXC (0.05%): $734.27 ARS

RESULTADO:
  Invertido: $1,458,000 ARS
  Recibido: $1,468,530 - $734.27 = $1,467,795.73 ARS
  Profit BRUTO: $1,468,530 - $1,458,000 = $10,530 ARS
  Fees TOTALES: $1,458 + $1,470 + $734.27 = $3,662.27 ARS
  Profit NETO: $10,530 - $3,662.27 = $6,867.73 ARS
  
  GANANCIA: +0.47% del capital (~$10,000 ARS / ciclo)
  
CONCLUSIÓN: ✅ RENTABLE
  Con 1,000 USDT, los fees fijos (2 USDT) representan 0.2% del capital.
  El spread de 0.82% cubre holgadamente los fees.
  Profit neto de 0.47% por ciclo.
  
  Si haces 5 ciclos por día: ~$34,000 ARS/día = ~$1,000,000 ARS/mes
```

---

### Escenario 5: Capital ALTO (5,000 USDT = ~$7,500,000 ARS)

```
DATOS:
  Capital: 5,000 USDT
  Precio Binance: $1,458 ARS/USDT
  Precio MEXC: $1,470 ARS/USDT
  Spread: 0.82%

OPERACIÓN:
  1. Compras 5,000 USDT en Binance: 5,000 × $1,458 = $7,290,000 ARS
  2. Trading fee Binance (0.10%): $7,290 ARS
  3. Transfieres 5,000 USDT a MEXC
  4. Withdrawal fee (1 USDT): 1 USDT = $1,470 ARS
  5. Vendes 4,999 USDT en MEXC: 4,999 × $1,470 = $7,348,530 ARS
  6. Trading fee MEXC (0.05%): $3,674.27 ARS

RESULTADO:
  Invertido: $7,290,000 ARS
  Recibido: $7,348,530 - $3,674.27 = $7,344,855.73 ARS
  Profit BRUTO: $7,348,530 - $7,290,000 = $58,530 ARS
  Fees TOTALES: $7,290 + $1,470 + $3,674.27 = $12,434.27 ARS
  Profit NETO: $58,530 - $12,434.27 = $46,095.73 ARS
  
  GANANCIA: +0.63% del capital
  
CONCLUSIÓN: ✅ MUY RENTABLE
  Con 5,000 USDT, los fees fijos (2 USDT) representan 0.04% del capital.
  El spread de 0.82% genera profit neto de 0.63%.
  
  Si haces 3 ciclos por día: ~$138,000 ARS/día = ~$4,000,000 ARS/mes
```

---

## 📈 GRÁFICO DE RENTABILIDAD VS CAPITAL

```
Capital (USDT)  |  Fees %  |  Spread  |  Profit Neto %  |  Conclusión
----------------|----------|----------|-----------------|-------------
7               |  28.6%   |  0.82%   |  -28.1%         |  ❌ PÉRDIDA
50              |   4.0%   |  0.82%   |   -3.2%         |  ❌ PÉRDIDA
100             |   2.0%   |  0.82%   |   -1.3%         |  ❌ PÉRDIDA
200             |   1.0%   |  0.82%   |   -0.3%         |  ❌ PÉRDIDA
333             |   0.6%   |  0.82%   |   +0.07%        |  ⚠️ MARGINAL
500             |   0.4%   |  0.82%   |   +0.25%        |  ✅ RENTABLE
1,000           |   0.2%   |  0.82%   |   +0.47%        |  ✅ RENTABLE
2,000           |   0.1%   |  0.82%   |   +0.57%        |  ✅ RENTABLE
5,000           |   0.04%  |  0.82%   |   +0.63%        |  ✅ MUY RENTABLE
```

---

## 🎯 CONCLUSIONES

### 1. Capital MÍNIMO para operar

**Con tus 7.25 USDT actuales: NO es rentable operar**
- Los fees fijos (2 USDT) representan ~28% del capital
- Necesitarías un spread de 30% para ganar, lo cual es imposible
- **Perderías ~$2,800 ARS por ciclo**

### 2. Capital MÍNIMO recomendado

**333 USDT (~$500,000 ARS) es el mínimo para empezar**
- Fees fijos representan 0.6% del capital
- Profit neto: 0.07% por ciclo (muy bajo pero positivo)
- **Ganarías ~$300 ARS por ciclo**

### 3. Capital ÓPTIMO

**1,000 USDT (~$1,500,000 ARS) es el punto óptimo**
- Fees fijos representan 0.2% del capital
- Profit neto: 0.47% por ciclo
- **Ganarías ~$7,000 ARS por ciclo**
- Con 3-5 ciclos/día: $20,000 - $35,000 ARS/día

### 4. Estrategia recomendada

```
FASE 1: Acumulación (1-2 semanas)
  - Deposita $500,000 - $1,000,000 ARS en Binance
  - Deposita $500,000 - $1,000,000 ARS en MEXC
  - No operes aún, solo ten fondos disponibles

FASE 2: Operativa inicial (2-4 semanas)
  - Opera con 300-500 USDT por ciclo
  - Objetivo: 2-3 ciclos/día
  - Profit estimado: $1,000 - $2,000 ARS/día
  - Reinvierte profits

FASE 3: Escalamiento (1-2 meses)
  - Aumenta a 1,000-2,000 USDT por ciclo
  - Objetivo: 3-5 ciclos/día
  - Profit estimado: $20,000 - $50,000 ARS/día
  - Retira profits mensualmente
```

---

## ⚠️ ADVERTENCIAS IMPORTANTES

### 1. Tiempos de transferencia

- **USDT TRC20**: 1-5 minutos entre exchanges
- **ARS (banco)**: 1-3 días hábiles para depositar/retirar
- **Durante la transferencia**: El precio puede cambiar (riesgo)

### 2. Promociones temporales

- **MEXC ARS deposit/withdrawal gratis**: Hasta Feb 20, 2026
- **Binance ARS withdrawal gratis**: Hasta Dic 31, 2025
- **Después de estas fechas**: Los fees de ARS aumentarán ~$500-1000 por operación

### 3. Límites de retiro

- **MEXC**: Límite diario de retiro según KYC
- **Binance**: Límite según verificación
- **Verifica tus límites** antes de operar con grandes montos

### 4. Volatilidad del spread

- El spread de 0.82% es PROMEDIO
- Puede variar de 0.1% a 2% durante el día
- El bot solo opera cuando spread > 0.6% (cubre fees)

---

## 💡 RECOMENDACIÓN FINAL

**Con tus 7.25 USDT actuales:**

1. ❌ **NO operes arbitraje todavía** - Perderás dinero
2. ✅ **Acumula al menos 333 USDT** (~$500,000 ARS)
3. ✅ **Ideal: 1,000 USDT** (~$1,500,000 ARS)
4. ✅ **Mientras tanto**: El bot puede monitorear oportunidades y mostrar profits potenciales en modo simulación

**Una vez tengas el capital:**
- El bot automáticamente calculará fees antes de cada operación
- Solo ejecutará si es rentable (profit > fees)
- Mostrará profit/loss NETO después de fees en tiempo real
