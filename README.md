# 🤖 Bot de Arbitraje USDT/ARS

Bot de trading automatizado que ejecuta operaciones de **arbitraje real** entre **múltiples exchanges**, aprovechando las diferencias de precio del par USDT/ARS.

## ⚠️ ADVERTENCIAS IMPORTANTES

1. **Riesgo de Pérdida**: El trading de criptomonedas conlleva riesgos significativos. Puedes perder todo tu capital.
2. **Capital Mínimo**: Con 7 USDT estás por debajo del mínimo de Binance (~5-10 USDT por orden). Considera depositar más fondos.
3. **Configuración Requerida**: Necesitas APIs configuradas en al menos 2 exchanges.
4. **No es Consejo Financiero**: Este software es solo para fines educativos.

## 🚀 Características

- **Arbitraje Multi-Exchange**: Opera entre Binance, Bybit, OKX, KuCoin, Gate.io, y exchanges argentinos
- **Detección Automática**: Encuentra oportunidades entre TODOS los exchanges configurados
- **Análisis de Noticias**: Monitoreo en tiempo real de noticias argentinas (Infobae, Clarín, Página/12)
- **Machine Learning**: Modelo que aprende de operaciones anteriores usando scikit-learn
- **Dashboard TUI**: Interfaz en consola con información en tiempo real
- **Notificaciones Telegram**: Alertas de operaciones, errores y resúmenes
- **Backtesting**: Evalúa la estrategia con datos históricos
- **Gestión de Riesgo**: Stop-loss del 5%, cooldown entre operaciones
- **Logs Detallados**: Registro completo de todas las operaciones
- **Cifrado de Credenciales**: Las API keys se cifran con contraseña maestra

## 📋 Requisitos

- Python 3.9+
- Linux, Windows o macOS
- Cuentas en al menos 2 exchanges
- API Keys con permisos de trading
- Bot de Telegram y Chat ID

## 🔧 Instalación

### 1. Clonar/Crear el proyecto

```bash
cd /path/to/Prueba
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

**Nota**: TA-Lib puede requerir instalación previa del sistema:
```bash
# Ubuntu/Debian
sudo apt-get install libta-lib

# macOS
brew install ta-lib

# Windows: Descargar de https://github.com/cgohlke/talib-builds
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

```env
# Binance (requerido)
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret
BINANCE_TESTNET=true

# Exchange Argentino (opcional)
ARGENTINE_EXCHANGE=buenbit
ARGENTINE_API_KEY=tu_api_key
ARGENTINE_API_SECRET=tu_api_secret

# Exchanges Adicionales (opcional - añade más oportunidades)
BYBIT_API_KEY=tu_api_key
BYBIT_API_SECRET=tu_api_secret

OKX_API_KEY=tu_api_key
OKX_API_SECRET=tu_api_secret

# Telegram
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id

# Cifrado
ENCRYPTION_PASSWORD=tu_contraseña_maestra
```

### 5. Ejecutar el bot

```bash
python main.py
```

O con auto-reinicio:

```bash
./run_bot.sh
```

## 📖 Comandos

| Comando | Descripción |
|---------|-------------|
| `python main.py` | Iniciar el bot en modo normal |
| `python main.py --test` | Modo prueba (sin operaciones reales) |
| `python main.py --backtest` | Ejecutar backtesting (30 días) |
| `python main.py --backtest --backtest-days=60` | Backtest de 60 días |
| `python main.py --config=.env.prod` | Usar archivo de configuración alternativo |

## 🏗️ Estructura del Proyecto

```
Prueba/
├── main.py                 # Punto de entrada principal
├── requirements.txt        # Dependencias
├── .env.example           # Ejemplo de configuración
├── .env                   # Configuración real (no commitear)
├── .gitignore            # Archivos ignorados por git
├── src/
│   ├── api/
│   │   └── exchanges.py   # Conexión con Binance y exchanges AR
│   ├── arbitrage/
│   │   ├── engine.py      # Motor de arbitraje
│   │   └── backtester.py  # Sistema de backtesting
│   ├── news/
│   │   └── analyzer.py    # Análisis de noticias
│   ├── ml/
│   │   └── trader.py      # Modelo de ML
│   ├── tui/
│   │   └── dashboard.py   # Dashboard en consola
│   └── utils/
│       ├── crypto_config.py  # Cifrado y configuración
│       ├── logger.py         # Sistema de logs
│       └── telegram.py       # Notificaciones
├── data/
│   ├── logs/            # Logs del bot
│   ├── models/          # Modelos de ML guardados
│   └── cache/           # Caché de datos históricos
└── tests/               # Tests (futuros)
```

## 📊 Dashboard TUI

El dashboard muestra en tiempo real:

- **Estado del bot**: Running/Stopped
- **Balances**: USDT y ARS en cada exchange
- **Posiciones activas**: Operaciones en curso
- **Estadísticas**: Total trades, win rate, profit
- **Análisis de mercado**: Sentimiento e impacto de noticias
- **Machine Learning**: Estado del modelo y predicciones
- **Noticias recientes**: Últimas noticias con sentimiento

## 📰 Fuentes de Noticias

El bot monitorea automáticamente:

- **Infobae** (RSS economía)
- **Clarín** (RSS economía)
- **Página/12** (RSS economía)

Analiza palabras clave para determinar:
- Sentimiento (positivo/negativo para ARS)
- Impacto esperado en USDT/ARS
- Eventos de alto impacto (elecciones, BCRA, FMI, etc.)

## 🤖 Machine Learning

El modelo:
- Usa **Random Forest Classifier** de scikit-learn
- Aprende de cada operación realizada
- Considera: spread, volumen, volatilidad, sentimiento de noticias
- Se reentrena automáticamente cada 24 horas (o con 50+ trades nuevos)
- Predice si una oportunidad será rentable

## 🔒 Seguridad

- **Cifrado**: Credenciales cifradas con contraseña maestra
- **.env en gitignore**: Las credenciales nunca se commitean
- **Sal única**: Cada instalación genera una sal única para cifrado
- **API restrictions**: Configura restricciones de IP en Binance

## ⚙️ Configuración Avanzada

### Parámetros de Trading

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `INITIAL_CAPITAL_USDT` | 7 | Capital inicial |
| `MAX_POSITIONS` | 1 | Operaciones simultáneas máximas |
| `STOP_LOSS_PERCENT` | 5 | Stop-loss porcentual |
| `MIN_PROFIT_PERCENT` | 0.5 | Ganancia mínima para operar |
| `COOLDOWN_SECONDS` | 30 | Espera entre operaciones |

### Parámetros de Noticias

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `NEWS_CHECK_INTERVAL_SECONDS` | 300 | Frecuencia de chequeo |
| `NEWS_SOURCES` | infobae,clarin,pagina12 | Fuentes a monitorear |

### Parámetros de ML

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `ML_MODEL_PATH` | data/models/arbitrage_model.pkl | Ruta del modelo |
| `RETRAIN_INTERVAL_HOURS` | 24 | Horas entre reentrenamientos |

## 📝 Logs

Los logs se guardan en `data/logs/arbitrage_bot.log` con formato JSON para fácil análisis.

Niveles de log:
- `DEBUG`: Información detallada de operaciones
- `INFO`: Operaciones abiertas/cerradas, oportunidades
- `WARNING`: Advertencias (noticias de alto impacto)
- `ERROR`: Errores que requieren atención

## 🆘 Solución de Problemas

### Error: "No hay suficientes fondos"
- Verifica que tienes USDT/ARS en ambos exchanges
- El mínimo de Binance es ~5-10 USDT por orden

### Error: "API key inválida"
- Verifica las credenciales en `.env`
- Asegúrate de tener permisos de trading habilitados
- Si usas testnet, las keys son diferentes

### Error: "TA-Lib no encontrado"
- Instala la librería del sistema (ver Instalación)
- O usa `pip install TA-Lib-binary` (Windows)

### El bot no detecta oportunidades
- El spread puede ser menor que `MIN_PROFIT_PERCENT`
- Verifica que los exchanges estén conectados
- Revisa los logs para más detalles

## 📈 Estrategia de Arbitraje

El bot busca diferencias de precio entre **todos los exchanges configurados**:

### Exchanges Soportados

**Internacionales:**
| Exchange | Mínimo Orden | Testnet |
|----------|--------------|---------|
| Binance | 5 USDT | ✅ |
| Bybit | 1 USDT | ✅ |
| OKX | 5 USDT | ❌ |
| KuCoin | 2 USDT | ❌ |
| Gate.io | 1 USDT | ❌ |
| Huobi (HTX) | 5 USDT | ❌ |
| Bitget | 2 USDT | ❌ |
| MEXC | 5 USDT | ❌ |
| Crypto.com | 10 USDT | ❌ |

**Argentinos:**
| Exchange | Mínimo Orden |
|----------|--------------|
| Buenbit | 1000 ARS |
| Ripio | 500 ARS |
| SatoshiTango | 1000 ARS |
| Lemon Cash | 500 ARS |
| Belo | 1000 ARS |

**Flujo típico:**
1. El bot compara precios entre TODOS los exchanges configurados
2. Detecta spread > mínimo configurado (ej: Binance → Bybit)
3. Compra USDT barato en Exchange A
4. Vende USDT caro en Exchange B
5. Registra ganancia (menos comisiones)

**Consideraciones:**
- Comisiones: ~0.1% por operación en cada exchange
- Spread mínimo recomendado: 0.5%+
- El arbitraje requiere fondos en AMBOS exchanges
- Más exchanges = más oportunidades de arbitraje

## 🎯 Próximos Pasos (Con 7 USDT)

1. **Usa testnet primero**: Configura `BINANCE_TESTNET=true`
2. **Deposita más fondos**: Mínimo recomendado 50-100 USDT
3. **Monitorea sin operar**: Ejecuta en modo observación
4. **Analiza backtest**: `python main.py --backtest`
5. **Ajusta parámetros**: Basado en resultados

## 📞 Soporte

Para issues o preguntas, revisar los logs en `data/logs/`.

## ⚖️ Licencia

Este proyecto es de código abierto para fines educativos.

---

**⚠️ ÚLTIMA ADVERTENCIA**: El arbitraje conlleva riesgos. Nunca inviertas más de lo que puedes permitirte perder. Este bot no garantiza ganancias.
