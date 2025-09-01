# ⚡️ High-Throughput API Gateway with Rate Limiting, Retry, and Circuit Breaking

A lightweight, production-ready **ASGI-compatible API Gateway** written in Python using **Starlette + httpx**, supporting per-route configuration, observability, and robust failure handling.

---

## 🚀 Overview

This project is a fully-functional, async-native API Gateway that acts as a **reverse proxy**, forwarding incoming requests to the correct backend while applying features like:

- ✅ Path-based routing
- ⏱ Timeout & retry logic
- 🔌 Circuit breaking
- 🚫 Rate limiting (Redis)
- 🧠 Per-route configuration
- 📊 Prometheus-compatible `/__metrics` endpoint
- 🔎 Admin endpoints: `/__health`, `/__routes`, `/__circuit`, `/__limits`
- 📊 Logging and trace ID propagation
- 🧪 100% test coverage with `pytest` + `httpx.ASGITransport`

This is designed to be a **real-world learning project** and a showcase for high-quality backend engineering.

---

## 🧱 Architecture

```
+-------------+       +----------------+       +------------------+
|  Client     | <---> |  API Gateway   | <---> | Backend Service   |
+-------------+       +----------------+       +------------------+
                          |     |     |
                          |     |     |
                 +--------+     |     +-----------+
                 |              |                 |
        +----------------+   +---------------+   +---------------+
        | Rate Limiter   |   | Retry/Circuit |   | Observability |
        | (Redis)        |   | Layer         |   | + Logging     |
        +----------------+   +---------------+   +---------------+
```

- All requests pass through routing, observability, rate limiting, and retry logic
- Behavior is customized per-route using a config table
- Admin endpoints expose internal state for debugging and monitoring

---

## ✨ Features

### 🔁 Routing
- Match routes using prefix logic
- Forward request to appropriate backend URL
- Supports per-route overrides

### ⏳ Timeout & Retry
- Set timeout per route
- Retry on transient errors using exponential backoff

### 💥 Circuit Breaking
- Open circuit after `n` failures
- Prevent overloading failing services
- Auto-close after cooldown

### 🧮 Rate Limiting
- Token bucket algorithm using Redis
- Per-route and per-client limits
- Returns `429 Too Many Requests` if limit exceeded

### 🧪 Observability
- Logs incoming requests with trace IDs
- Adds headers like `X-Trace-ID` to all responses
- `/__metrics`: Prometheus-compatible metrics
- `/__circuit`, `/__limits`: live introspection of internal states

---

## ⚙️ Per-Route Configuration

Each route in the `route_table` can be configured with:

```python
{
  "/users": {
    "backend": "http://localhost:5001",
    "timeout": 3,
    "retries": 2,
    "rate_limit": 100,        # requests per minute
    "circuit_threshold": 5,   # consecutive failures
    "circuit_cooldown": 30    # seconds
  }
}
```

---

## 🔧 Setup & Run

### 🐍 Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 🚀 Run the gateway

```bash
uvicorn app.main:build_app --reload --port 8080
```

> Make sure your backend services (e.g., `localhost:5001`) are running.

---

## 🧪 Run Tests

```bash
pytest tests/
```

Tests are written with `pytest-asyncio` and run directly against the ASGI app using `httpx.ASGITransport`. All major components are tested: routing, rate limiting, retries, observability, and admin endpoints.

---

## 📊 Admin & Observability Endpoints

| Endpoint        | Description                          |
|------------------|--------------------------------------|
| `/__health`      | Returns `200 OK` if gateway is alive |
| `/__routes`      | Dumps current routing table          |
| `/__circuit`     | Shows open/closed circuits per route |
| `/__limits`      | Shows rate/concurrency info          |
| `/__metrics`     | Prometheus-compatible metrics        |

---

## 📦 Directory Structure

```
api_gateway/
├── app/
│   ├── __init__.py
│   ├── main.py               # Entrypoint
│   ├── gateway_router.py     # Core proxy logic
│   ├── config.py             # Route table + config
│   ├── rate_limit.py         # Redis rate limiting
│   ├── circuit_breaker.py    # Circuit breaker state
│   ├── retry.py              # Retry wrapper
│   ├── observability.py      # Trace ID + logging
│   ├── metrics.py            # Prometheus exporter
│   ├── admin_routes.py       # /__health, /__routes, etc
│   ├── utils.py              # Helper functions
├── tests/
│   ├── test_gateway.py
│   ├── test_limits.py
│   ├── test_circuit.py
│   ├── test_metrics.py
│   └── ...
└── requirements.txt
```

---

## 💡 Why I Built This

I wanted to go beyond CRUD apps and build something that mimics real production infrastructure. This project helped me learn:

- Async Python at scale
- Systems-level resilience patterns
- How to structure configurable, testable backend systems
- How real-world APIs deal with failures, overload, and observability

This is the **first of four backend projects** I’m building to grow into a strong production-level engineer.

---

## 🧠 Learnings & Tradeoffs

- Used Starlette instead of FastAPI to **stay closer to ASGI** and reduce dependencies
- Avoided external circuit breaker libraries to **implement logic myself**
- Kept Redis interactions simple and idiomatic
- Designed for extensibility: middleware stack could support auth, compression, etc

---

## 📊 Example Metrics Output

```
# HELP gateway_requests_total Total number of processed requests
# TYPE gateway_requests_total counter
gateway_requests_total{route="/users",status="200"} 1324

# HELP gateway_request_duration_seconds Duration of requests
# TYPE gateway_request_duration_seconds histogram
gateway_request_duration_seconds_bucket{route="/users",le="0.1"} 742
...

# HELP gateway_rate_limited_total Total number of rate-limited responses
# TYPE gateway_rate_limited_total counter
gateway_rate_limited_total{route="/users"} 12
```

---

## 🧰 Future Enhancements

- Config hot-reloading from file or Redis
- Admin UI panel to visualize circuit/rate state
- WebSocket and gRPC support
- JWT authentication & header filters
- Cloud-native deployment template (Docker + Kubernetes)

---

## 👋 Contact

**Built by:** [C NASIR](https://www.linkedin.com/in/cnasir2/)  
**Location:** Madison, WI  
**Role Target:** Early–Mid Backend Engineer (Python, Infra, Systems)

Let’s connect if you’re passionate about resilient systems or enjoy building infrastructure from first principles.

---

