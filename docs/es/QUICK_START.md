# 🚀 Guía de Inicio Rápido

Comienza a usar la Plantilla Workspace de Antigravity en minutos.

## 📋 Requisitos Previos

- Python 3.9+
- pip o conda
- Git

## 🏃 Desarrollo Local

### 1. Instalar Dependencias
```bash
pip install -e .
```

### 2. Ejecutar el Agente
```bash
ag-engine
```

El agente ejecuta una tarea por invocación. Automáticamente:
- 🧠 Carga la memoria desde `memory/agent_memory.md`
- 🛠️ Descubre herramientas en `antigravity_engine/tools/`
- 📚 Ingiere contexto desde `.context/`

### 3. Ejemplo de Uso
```bash
ag-engine "Construye una función Python para calcular números Fibonacci"
```

El agente ejecutará esa tarea e imprimirá el resultado en stdout.

## 🐳 Despliegue con Docker

### Compilar y Ejecutar
```bash
docker-compose up --build
```

Esto:
- Instala todas las dependencias
- Inicia el agente en un entorno containerizado
- Monta tu workspace para edición de código en vivo

Accede al agente mediante la interfaz expuesta.

### Personalizar Docker
Edita `docker-compose.yml` para:
- Cambiar variables de entorno
- Montar volúmenes adicionales
- Exponer diferentes puertos

## 🔧 Configuración

### Variables de Entorno
Crea un archivo `.env`:

```bash
# Configuración de LLM
GOOGLE_API_KEY=tu-clave-api-aqui
GEMINI_MODEL_NAME=gemini-2.0-flash-exp

# Configuración de MCP
MCP_ENABLED=true

# Configuración personalizada
LOG_LEVEL=INFO
ARTIFACTS_DIR=artifacts
```

`ARTIFACTS_DIR` admite rutas absolutas o relativas. Las rutas relativas se
resuelven desde la raíz del repositorio.

### Gestión de Memoria
El agente gestiona la memoria con archivos markdown:
- `memory/agent_memory.md` (entradas crudas)
- `memory/agent_summary.md` (resumen comprimido)

Para reiniciar:

```bash
rm -f memory/agent_memory.md memory/agent_summary.md
ag-engine
```

## 📁 Referencia de Estructura del Proyecto

```
├── antigravity_engine/
│   ├── agent.py         # Bucle principal del agente
│   ├── config.py        # Gestión de configuración
│   ├── memory.py        # Motor de memoria
│   ├── agents/          # Agentes especialistas
│   └── tools/           # Implementaciones de herramientas
├── artifacts/           # Artefactos de salida
├── .context/            # Base de conocimiento
└── .antigravity/        # Reglas de Antigravity
```

Consulta [Estructura del Proyecto](../README.md#project-structure) para detalles.

## 🧪 Ejecutar Pruebas

```bash
# Ejecutar todas las pruebas
pytest

# Ejecutar prueba específica
pytest tests/test_agent.py -v

# Con cobertura
pytest --cov=antigravity_engine tests/
```

## 🐛 Solución de Problemas

### El agente no se inicia
```bash
# Verifica si las dependencias están instaladas
pip list | grep -Ei "google-genai|google-generativeai"

# Verifica que GOOGLE_API_KEY esté configurada
echo $GOOGLE_API_KEY
```

### Las herramientas no cargan
```bash
# Verifica que antigravity_engine/tools/ tenga archivos Python válidos
ls -la antigravity_engine/tools/

# Verifica errores de sintaxis
python -m py_compile antigravity_engine/tools/*.py
```

### Problemas de memoria
```bash
# Verifica el archivo de memoria
cat memory/agent_memory.md

# Limpia la memoria
rm -f memory/agent_memory.md memory/agent_summary.md
```

## 🔌 Integración de MCP

Para habilitar servidores MCP:

1. Configura `MCP_ENABLED=true` en `.env`
2. Configura servidores en `mcp_servers.json`
3. Reinicia el agente

Consulta [Guía de Integración de MCP](MCP_INTEGRATION.md) para configuración detallada.

## 📚 Próximos Pasos

- **Aprende Filosofía**: [Filosofía del Proyecto](PHILOSOPHY.md)
- **Explora MCP**: [Integración de MCP](MCP_INTEGRATION.md)
- **Multi-Agente**: [Protocolo de Swarm](SWARM_PROTOCOL.md)
- **Avanzado**: [Características Zero-Config](ZERO_CONFIG.md)
- **Hoja de Ruta**: [Hoja de Ruta de Desarrollo](ROADMAP.md)

---

**¿Preguntas?** Consulta el [Índice Completo](README.md) o abre un issue en GitHub.
