# RealTREM Discord Bot

Bot de Discord para sistema de filas RealTREM con soporte completo para 1v1, 2v2, 3v3 y 4v4.

## 🚀 Características

- ✅ **Modos de juego completos:** 1v1, 2v2, 3v3, 4v4
- ✅ **Modo por defecto:** 2v2 (como RealTREM)
- ✅ **Contadores dinámicos:** Botones que muestran [jugadores/capacidad]
- ✅ **Mensajes públicos:** Todos pueden ver las colas
- ✅ **Confirmaciones privadas:** Solo visibles para el usuario
- ✅ **Custom IDs únicos:** Cada usuario tiene su cola independiente
- ✅ **Sistema completo RealTREM:** Detección de canales, auto-movimiento, etc.

## 🔧 Configuración en Railway

### Variables de Entorno Requeridas

Antes de deployar, configura estas variables de entorno en Railway:

```
DISCORD_TOKEN=tu_discord_bot_token_aqui
```

### Pasos para configurar en Railway:

1. **Conectar repositorio:** `https://github.com/xpe-hub/realtrem-bot-final-clean`
2. **Variables de entorno:**
   - Ve a la sección "Variables" en Railway
   - Agrega: `DISCORD_TOKEN` = `tu_discord_bot_token_aqui`
3. **Deploy:** Railway detectará automáticamente:
   - `requirements.txt` para instalar dependencias
   - `nixpacks.toml` y `Procfile` para el comando de inicio
   - Ejecutará automáticamente `python bot.py`

## 📝 Comandos

- `!fila 2v2` - Crear cola en modo 2v2 (por defecto)
- `!fila 1v1` - Crear cola en modo 1v1
- `!fila 3v3` - Crear cola en modo 3v3
- `!fila 4v4` - Crear cola en modo 4v4

## 🔄 Funcionamiento

1. Usuario crea cola con comando
2. Bot envía mensaje público con botones interactivos
3. Otros usuarios pueden entrar/salir de la cola
4. Botones se actualizan dinámicamente con contadores
5. Cuando la cola se llena, se procede automáticamente

## 📁 Estructura

- `bot.py` - Código principal del bot
- `config.py` - Configuración del servidor y canales
- `requirements.txt` - Dependencias Python
- `nixpacks.toml` - Configuración de build y start para Railway
- `Procfile` - Comando de inicio alternativo para Railway
- `.gitignore` - Archivos ignorados por Git