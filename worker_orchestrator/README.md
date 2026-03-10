# VulRL Worker Orchestrator

Distributed worker orchestration system for VulRL penetration testing training with SkyRL.

## 🏗️ Architecture

```
SkyRL Trainer (GPU-bound)
    ↓ HTTP REST API
Worker Router (FastAPI)
    ↓ Redis Queue
Worker Units (Subprocesses)
    ↓ Docker Containers
    ↓ HTTP API
SkyRL LLM Server (GPU-bound)
```

## 📁 Project Structure

```
worker_orchestrator/
├── worker_router/              # FastAPI server
│   ├── app.py                  # Main FastAPI app
│   ├── models.py               # Pydantic models
│   ├── config.py               # Config loader
│   ├── redis_client.py         # Redis wrapper
│   ├── worker_pool.py          # Worker subprocess management
│   ├── routes/
│   │   ├── rollout.py          # Rollout endpoints
│   │   └── workers.py          # Worker management endpoints
│   └── utils/
│       ├── logger.py           # File logging
│       └── exceptions.py       # Custom exceptions
├── worker_unit/                # Worker subprocess
│   ├── main.py                 # Worker entry point
│   ├── llm_client.py           # LLM HTTP client
│   ├── docker_manager.py       # Docker operations (demo)
│   └── reward_calculator.py    # Reward computation
├── logs/                       # Log files
├── config.yaml                 # Configuration
├── .env                        # Environment variables
├── requirements.txt            # Dependencies
├── start.sh                    # Startup script
└── stop.sh                     # Shutdown script
```

## 🚀 Quick Start

### 1. Setup Virtual Environment & Install Dependencies

```bash
cd E:\git_fork_folder\VulRL\worker_orchestrator  # Windows
# OR
cd /mnt/e/git_fork_folder/VulRL/worker_orchestrator  # WSL

# Run setup script (creates venv and installs dependencies)
bash setup.sh
```

### 2. Install Redis

**Windows**:
```bash
# Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
# Or use WSL/Docker
```

**Linux/Mac**:
```bash
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis                 # macOS
```

### 3. Configure

Edit `config.yaml` and `.env` as needed:

```yaml
# config.yaml
worker_router:
  port: 5000
  max_workers: 10

redis:
  host: localhost
  port: 6379
```

```bash
# .env
REDIS_PASSWORD=
```

### 4. Start Services

**Linux/Mac/WSL**:
```bash
# This will activate venv and start the server
bash start.sh
```

**Or manually**:
```bash
# Activate venv
source venv/bin/activate

# Start server
python -m uvicorn worker_router.app:app --host 0.0.0.0 --port 5000
```

**Windows (PowerShell)**:
```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Start Redis (in separate terminal)
redis-server

# Start server
python -m uvicorn worker_router.app:app --host 0.0.0.0 --port 5000
```

### 5. Test API

```bash
# Check health
curl http://localhost:5000/health

# Submit a rollout (example)
curl -X POST http://localhost:5000/api/rollout/execute \
  -H "Content-Type: application/json" \
  -d '{
    "cve_id": "CVE-2021-44228",
    "vulhub_path": "/data/vulhub/log4j/CVE-2021-44228",
    "prompt": "Exploit Log4Shell vulnerability",
    "llm_endpoint": "http://127.0.0.1:8001",
    "model_name": "Qwen/Qwen2.5-7B-Instruct"
  }'

# Get task status
curl http://localhost:5000/api/rollout/status/{task_id}

# Check workers
curl http://localhost:5000/api/workers/status
```

### 6. View API Documentation

Open in browser: http://localhost:5000/docs

## 📖 API Endpoints

### Rollout Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rollout/execute` | POST | Submit rollout task |
| `/api/rollout/status/{task_id}` | GET | Get task status/result |

### Worker Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/workers/status` | GET | Get all workers status |
| `/api/workers/{worker_id}/shutdown` | POST | Shutdown specific worker |

### Health & Info

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |

## 📝 Logging

All logs are written to `logs/worker_router.log` with the format:

```
time <timestamp>; request entry point: <function>; request: <input>
time <timestamp>; request entry point: <function>; request: <input>; return: <output>
```

Example:
```
time 2026-03-10 14:23:45.123; request entry point: execute_rollout; request: {"cve_id": "CVE-2021-44228", ...}
time 2026-03-10 14:23:45.456; request entry point: execute_rollout; request: {"cve_id": "CVE-2021-44228", ...}; return: {"task_id": "abc-123", "status": "running"}
```

## 🔧 Configuration

### Worker Router Settings

```yaml
worker_router:
  host: "0.0.0.0"          # Server host
  port: 5000               # Server port
  max_workers: 10          # Maximum worker subprocesses
  worker_timeout: 1800     # Worker timeout (seconds)
```

### Redis Settings

```yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  # password from .env
```

### LLM Settings

```yaml
llm:
  default_endpoint: "http://127.0.0.1:8001"
  default_model: "Qwen/Qwen2.5-7B-Instruct"
  default_temperature: 0.7
  default_max_tokens: 512
```

## 🛠️ Development

### Project Requirements

- Python 3.10+
- Redis 6.0+
- Docker (for actual rollouts)

### Running in Development Mode

```bash
# Start with auto-reload
uvicorn worker_router.app:app --reload --port 5000
```

### Testing Individual Components

```python
# Test Redis connection
from worker_router.redis_client import RedisClient
redis = RedisClient("localhost", 6379)
print(redis.ping())  # Should print True

# Test worker spawning
from worker_router.worker_pool import WorkerPool
pool = WorkerPool(redis, max_workers=2)
worker_id = pool.spawn_worker()
print(f"Spawned worker: {worker_id}")
```

## 📊 Monitoring

### Redis State

```bash
# Connect to Redis CLI
redis-cli

# List all keys
KEYS *

# Check worker status
HGETALL worker:{worker_id}

# Check task status
HGETALL task:{task_id}

# Get result
GET result:{task_id}
```

### Worker Processes

```bash
# List worker processes (Linux/Mac)
ps aux | grep worker_unit

# Kill specific worker
pkill -f "worker_unit.*worker-id"
```

## 🔍 Troubleshooting

### Redis Connection Error

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
redis-server --daemonize yes
```

### Worker Not Starting

Check logs in `logs/worker_router.log` for errors.

### Port Already in Use

Change port in `config.yaml` or `.env`:

```bash
WORKER_ROUTER_PORT=5001
```

## 📚 Documentation

For complete architecture and design details, see:

- `design/API_INPUT_OUTPUT.md` - Complete API specification
- `design/ARCHITECTURE_VISUAL.md` - Visual architecture diagrams
- `design/WORKER_MANAGEMENT_TECH_SPEC.md` - Technical specifications
- `design/README.md` - Design documentation index

## 🚧 Current Status

**Implementation Status**: ✅ Complete (v0.1.0)

- ✅ Worker Router FastAPI server
- ✅ Redis state management
- ✅ Worker subprocess management
- ✅ API endpoints (rollout, workers)
- ✅ File logging
- ✅ Demo worker with mocked Docker operations

**TODO for Production**:
- [ ] Replace mocked Docker operations with real docker-py
- [ ] Add authentication (JWT/API keys)
- [ ] Add task retry logic
- [ ] Add worker health monitoring
- [ ] Add metrics/Prometheus integration
- [ ] Add comprehensive error handling

## 📞 Support

For issues or questions:
1. Check the logs in `logs/worker_router.log`
2. Review API documentation at http://localhost:5000/docs
3. See design docs in `design/` directory

---

**Version**: 0.1.0  
**Last Updated**: 2026-03-10  
**Status**: Development
