ROUTE_TABLE = {
    "/api": {
        "backend": "http://localhost:5001",
    },
    "/auth": {
        "backend": "http://localhost:5002",
        "retries": 5,
        "retry_delay": 0.2,
        "timeout": 2.0,
        "header_policy": {
            "remove": ["x-remove-this"],
            "set": {"x-api": "auth-service"},
            "append": {"x-version": "1.0"}
        }
    }
}
