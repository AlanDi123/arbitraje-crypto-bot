# 🤖 BOT DE ARBITRAJE - ESTADO ACTUAL Y CONFIGURACIÓN

## ✅ IMPLEMENTADO Y FUNCIONANDO

### 1. Motor de Arbitraje con Fees Reales
- ✅ Calcula fees de transferencia (2 USDT por ciclo)
- ✅ Calcula fees de trading (0.15% total)
- ✅ Solo opera si profit > fees
- ✅ Muestra profit NETO después de fees

### 2. Sistema de Alertas FLASH
- ✅ Monitorea spreads > 10%
- ✅ Alerta cada 5 minutos para no spamear
- ✅ Calcula profit potencial con tu capital
- ✅ Te avisa si es rentable con 7 USDT

### 3. Exchanges Soportados
- ✅ Binance (principal)
- ✅ MEXC (exchange argentino recomendado)
- ✅ CryptoMarket, Bitso, Ripio (alternativos)
- ✅ CriptoYa (consulta de precios)

---

## 📊 TU SITUACIÓN ACTUAL

### Capital Disponible
```
Tienes: 7.25 USDT en Binance
Necesitas: 333 USDT mínimo para operar
Falta: 325.75 USDT (~$490,000 ARS)
```

### ¿Por qué no operar ahora?
```
Con 7 USDT:
  - Fees fijos: 2 USDT (28.6% del capital)
  - Spread promedio: 0.82%
  - Resultado: -$2,870 ARS por ciclo ❌

Con 333 USDT:
  - Fees fijos: 2 USDT (0.6% del capital)
  - Spread promedio: 0.82%
  - Resultado: +$326 ARS por ciclo ✅
```

---

## 🎯 RESPUESTA: ¿333 USDT en ambos exchanges o solo en uno?

### SOLO EN UNO (Binance)

**Flujo correcto:**
```
ANTES DE OPERAR:
  Binance: $500,000 ARS (para comprar USDT)
  MEXC:    0 USDT (no necesitas nada)

DURANTE LA OPERACIÓN:
  1. Binance: Compras 333 USDT con ARS
  2. Transfieres 333 USDT a MEXC (fee: 1 USDT)
  3. MEXC: Vendes 332 USDT por ARS
  4. Profit: ~$326 ARS

DESPUÉS DE OPERAR:
  Binance: 0 ARS (usaste todo)
  MEXC:    ~$488,000 ARS (tu capital + profit)

PARA EL PRÓXIMO CICLO:
  Opción A: Rebalancear (MEXC → Binance)
  Opción B: Operar en reversa (MEXC → Binance)
```

**Conclusión:** Solo necesitas ARS en el exchange donde INICIAS. NO en ambos.

---

## ⚡ SISTEMA DE ALERTAS FLASH

### Configuración Actual
```
Umbral de alerta: Spread > 10%
Frecuencia máxima: 1 alerta cada 5 minutos
Exchanges monitoreados: 20+ (vía CriptoYa)
```

### ¿Qué pasa si detecta una oportunidad?
```
[WARNING] ======================================================================
[WARNING] ⚡⚡⚡ ALERTA FLASH DETECTADA ⚡⚡⚡
[WARNING] ======================================================================
[WARNING] 🔥 Spread: 15.50% (>10%)
[WARNING] 📊 Comprar en Binance: $1,458.00
[WARNING] 📊 Vender en MEXC: $1,684.00
[WARNING] 💰 CON 7 USDT:
[WARNING]    Profit: $1,500.00 ARS (14.50%)
[WARNING]    ✅ ES RENTABLE - EJECUTAR AHORA!
[WARNING]    ⚠️ La oportunidad puede desaparecer en segundos
[WARNING] ======================================================================
```

### Frecuencia de alertas
- **Spread > 10%**: Muy raro (1 vez cada semanas/meses)
- **Spread > 20%**: Extremadamente raro (1 vez cada año)
- **Spread > 50%**: Casi imposible en exchanges formales

**Nota:** Durante 2 minutos de test, NO se encontró NINGUNA oportunidad >10%.

---

## 📋 PLAN RECOMENDADO

### Fase 1: Acumulación (2-4 semanas)
```
Semana 1: Ahorrar $150,000 ARS → 100 USDT
Semana 2: Ahorrar $150,000 ARS → 100 USDT
Semana 3: Ahorrar $150,000 ARS → 100 USDT
Tus 7 USDT actuales → 7 USDT
────────────────────────────────────────────
Total: 307 USDT (casi listo!)
```

### Fase 2: Primera operación
```
1. Depositar $500,000 ARS en Binance
2. Configurar bot con capital: 333 USDT
3. Iniciar bot
4. Esperar oportunidad (spread > 0.6%)
5. Bot ejecuta automáticamente
6. Profit: ~$326 ARS por ciclo
```

### Fase 3: Reinversión
```
Ciclos 1-10: Reinvertir TODO el profit
Ciclo 11+: Retirar 50%, reinvertir 50%
```

---

## 📁 ARCHIVOS IMPORTANTES

### Código del Bot
- `main.py` - Archivo principal
- `src/arbitrage/smart_engine_fees.py` - Motor con cálculo de fees
- `src/api/argentine_exchanges.py` - Exchanges argentinos (MEXC, etc.)
- `verify_api_permissions.py` - Verificador de APIs

### Guías y Documentación
- `GUIA_ACUMULAR_CAPITAL.md` - Cómo juntar los 333 USDT
- `SIMULACION_FEES.md` - Simulaciones con diferentes capitales
- `README.md` - Documentación general

### Configuración
- `.env` - Tus credenciales (NO COMPARTIR)
- `.env.example` - Ejemplo de configuración

---

## 🚀 COMANDOS ÚTILES

### Iniciar el bot
```bash
cd /home/whiterman1/Prueba
./run_bot.sh
```

### Verificar estado de APIs
```bash
python3 verify_api_permissions.py
```

### Rastrear oportunidades FLASH (manual)
```bash
python3 flash_opportunity_tracker.py
```

### Ver logs en tiempo real
```bash
tail -f data/logs/bot_runner.log
```

### Detener el bot
```bash
pkill -f "python3 /home/whiterman1/Prueba/main.py"
```

---

## ⚠️ ADVERTENCIAS IMPORTANTES

### 1. No operar con menos de 333 USDT
- Perderás dinero con los fees
- El bot NO ejecutará automáticamente si no es rentable
- Pero NO intentes forzar operaciones manuales

### 2. Las alertas FLASH son MUY raras
- Spread > 10% ocurre una vez cada semanas/meses
- Spread > 50% es casi imposible en exchanges formales
- No bases tu estrategia en esperar estas alertas

### 3. Promociones temporales
- MEXC ARS deposit/withdrawal gratis: Hasta Feb 20, 2026
- Binance ARS withdrawal gratis: Hasta Dic 31, 2025
- Después de estas fechas, los fees aumentarán ~$500-1000 ARS

### 4. Riesgos
- Transferencias USDT: 1-5 minutos (precio puede cambiar)
- Liquidez: Asegúrate de haber volumen en el exchange
- API limits: No operar más de 5-10 ciclos/día al inicio

---

## 📞 SOPORTE

### Si tienes dudas:
1. Revisa `GUIA_ACUMULAR_CAPITAL.md` para acumular USDT
2. Revisa `SIMULACION_FEES.md` para entender fees
3. Ejecuta `python3 verify_api_permissions.py` para verificar APIs
4. Revisa los logs: `tail -f data/logs/bot_runner.log`

### Próximos pasos:
1. ✅ Bot configurado y funcionando
2. ✅ Alertas FLASH activas
3. ⏳ Acumular 333 USDT (2-4 semanas)
4. ⏳ Primera operación real
5. ⏳ Reinvertir profits primeros 10 ciclos
6. ⏳ Escalar a 1,000+ USDT

---

**¡ÉXITO! El bot está listo. Solo falta acumular el capital. 🚀**
