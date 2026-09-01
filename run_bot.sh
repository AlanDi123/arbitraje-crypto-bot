#!/bin/bash
# ===========================================
# Script de Auto-Reinicio para Arbitrage Bot
# ===========================================
# Este script ejecuta el bot y lo reinicia automáticamente
# si falla o se detiene inesperadamente.
#
# Uso:
#   ./run_bot.sh              # Ejecutar en foreground
#   ./run_bot.sh --daemon     # Ejecutar en background (daemon)
#   ./run_bot.sh --stop       # Detener el bot
#   ./run_bot.sh --status     # Ver estado
# ===========================================

set -e
set -o pipefail

# Configuración
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_SCRIPT="$BOT_DIR/main.py"
PYTHON_CMD="python3"
PID_FILE="$BOT_DIR/data/.bot.pid"
LOG_FILE="$BOT_DIR/data/logs/bot_runner.log"
MAX_RESTARTS=10
RESTART_DELAY=5

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones de logging
log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] $1" | tee -a "$LOG_FILE"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "${GREEN}[OK]${NC} $1"
}

log_warning() {
    log "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

# Verificar dependencias
check_dependencies() {
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python3 no encontrado. Intentando con 'python'..."
        PYTHON_CMD="python"
    fi
    
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python no encontrado. Por favor instala Python 3.9+"
        exit 1
    fi
    
    log_info "Python encontrado: $($PYTHON_CMD --version)"
}

# Verificar entorno virtual
check_venv() {
    if [ -d "$BOT_DIR/venv" ]; then
        log_info "Activando entorno virtual..."
        source "$BOT_DIR/venv/bin/activate"
    elif [ -d "$BOT_DIR/env" ]; then
        log_info "Activando entorno virtual..."
        source "$BOT_DIR/env/bin/activate"
    fi
}

# Verificar archivo .env
check_env() {
    if [ ! -f "$BOT_DIR/.env" ]; then
        log_warning ".env no encontrado. Copiando desde .env.example..."
        cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"
        log_warning "Por favor edita .env con tus credenciales antes de continuar"
        exit 1
    fi
}

# Obtener PID del bot
get_bot_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

# Verificar si el bot está corriendo
is_running() {
    local pid=$(get_bot_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

# Iniciar el bot. $1 = flags extra para pasarle a main.py.
start_bot() {
    local extra_args="$1"
    local restart_count=0
    
    log_info "=========================================="
    log_info "Iniciando Arbitrage Bot USDT/ARS"
    log_info "=========================================="
    
    while true; do
        # Guardar PID
        echo $$ > "$PID_FILE"
        
        log_info "Iniciando bot (intento $((restart_count + 1))/$MAX_RESTARTS)..."
        
        # Ejecutar bot
        cd "$BOT_DIR"
        # Permite capturar el fallo de Python para aplicar el reinicio.
        set +e
        $PYTHON_CMD "$BOT_SCRIPT" $extra_args 2>&1 | tee -a "$LOG_FILE"
        local exit_code=$?
        set -e
        
        # Limpiar PID
        rm -f "$PID_FILE"
        
        # Verificar código de salida
        if [ $exit_code -eq 0 ]; then
            log_success "Bot detenido normalmente"
            break
        elif [ $exit_code -eq 130 ]; then
            log_warning "Bot interrumpido por usuario (Ctrl+C)"
            break
        else
            log_error "Bot falló con código $exit_code"
            
            restart_count=$((restart_count + 1))
            
            if [ $restart_count -ge $MAX_RESTARTS ]; then
                log_error "Máximo de reinicios ($MAX_RESTARTS) alcanzado. Deteniendo."
                break
            fi
            
            log_warning "Reiniciando en $RESTART_DELAY segundos..."
            sleep $RESTART_DELAY
        fi
    done
    
    log_info "Bot completamente detenido"
}

# Detener el bot
stop_bot() {
    local pid=$(get_bot_pid)
    
    if [ -z "$pid" ]; then
        log_warning "No hay PID guardado"
        return 1
    fi
    
    if kill -0 "$pid" 2>/dev/null; then
        log_info "Deteniendo bot (PID: $pid)..."
        kill "$pid"
        
        # Esperar a que se detenga
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        if kill -0 "$pid" 2>/dev/null; then
            log_warning "Forzando detención..."
            kill -9 "$pid"
        fi
        
        rm -f "$PID_FILE"
        log_success "Bot detenido"
    else
        log_warning "El bot no está corriendo"
        rm -f "$PID_FILE"
    fi
}

# Mostrar estado
show_status() {
    local pid=$(get_bot_pid)
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}     Estado del Arbitrage Bot${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "Estado: ${GREEN}CORRIENDO${NC}"
        echo -e "PID: $pid"
        echo -e "Log: $LOG_FILE"
        
        # Mostrar últimas líneas del log
        echo ""
        echo -e "${YELLOW}Últimos logs:${NC}"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "No hay logs disponibles"
    else
        echo -e "Estado: ${RED}DETENIDO${NC}"
        echo -e "Log: $LOG_FILE"
    fi
    
    echo ""
}

# Ejecutar en daemon (background). $1 = flags a reenviarle al bot.
run_daemon() {
    local args="${1:-}"
    log_info "Iniciando en modo daemon..."

    nohup "$0" "$args" > /dev/null 2>&1 &

    sleep 2

    if is_running; then
        log_success "Bot iniciado en background"
    else
        log_error "Error iniciando en background"
    fi
}

# Mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCIÓN]"
    echo ""
    echo "Opciones:"
    echo "  (ninguna)      Ejecutar el bot en modo SIMULACIÓN (default seguro)"
    echo "  --daemon       Ejecutar en background, modo SIMULACIÓN (daemon)"
    echo "  --stop         Detener el bot"
    echo "  --status       Mostrar estado del bot"
    echo "  --simulation   Igual que (ninguna): modo SIMULACIÓN explícito"
    echo "  --real         Modo REAL — mueve dinero real. Pide confirmación."
    echo "  --backtest     Ejecutar backtesting (estimación aproximada)"
    echo "  --help         Mostrar esta ayuda"
    echo ""
    echo "Ejemplos:"
    echo "  $0                  # Simulación en foreground (default seguro)"
    echo "  $0 --daemon         # Simulación en background"
    echo "  $0 --real           # REAL — pide confirmación explícita antes de arrancar"
    echo "  $0 --stop           # Detener bot"
    echo "  $0 --status         # Ver estado"
}

# ===========================================
# Programa Principal
# ===========================================

case "${1:-}" in
    --daemon)
        check_dependencies
        check_venv
        check_env
        run_daemon "--simulation"
        ;;
    --stop)
        stop_bot
        ;;
    --status)
        show_status
        ;;
    --simulation)
        check_dependencies
        check_venv
        check_env
        log_info "=========================================="
        log_info "Iniciando en MODO SIMULACIÓN"
        log_info "=========================================="
        log_info "⚠️  LAS OPERACIONES SON SIMULADAS"
        log_info "💡 No se ejecutan órdenes reales"
        log_info "=========================================="
        start_bot "--simulation"
        ;;
    --real)
        check_dependencies
        check_venv
        check_env
        echo -e "${RED}=========================================="
        echo -e "⚠️  MODO REAL — ESTO MUEVE DINERO REAL ⚠️"
        echo -e "==========================================${NC}"
        echo "Además de esta confirmación, el bot exige CONFIRM_REAL_TRADING="
        echo "YES_I_UNDERSTAND_THE_RISK en tu .env, o arranca en simulación igual."
        read -r -p "Escribí 'SI' (en mayúsculas) para continuar: " confirm
        if [ "$confirm" != "SI" ]; then
            log_warning "Confirmación no recibida. Cancelando."
            exit 1
        fi
        start_bot ""
        ;;
    --backtest)
        check_dependencies
        check_venv
        check_env
        cd "$BOT_DIR"
        $PYTHON_CMD "$BOT_SCRIPT" --backtest 2>&1 | tee -a "$LOG_FILE"
        ;;
    --help|-h)
        show_help
        ;;
    "")
        check_dependencies
        check_venv
        check_env
        log_info "Sin flags: arrancando en modo SIMULACIÓN (usá --real para modo real)"
        start_bot "--simulation"
        ;;
    *)
        log_error "Opción desconocida: $1"
        show_help
        exit 1
        ;;
esac
