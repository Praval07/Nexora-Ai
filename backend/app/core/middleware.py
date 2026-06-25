import time
import logging
from flask import request, jsonify, g
from flask_jwt_extended import get_jwt
from backend.app.core.database import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)

def setup_middleware(app):
    @app.before_request
    def extract_tenant_context():
        """
        Runs before every request to determine the tenant context.
        """
        # Record start time for latency tracking
        g.start_time = time.time()
        
        tenant_id = None
        
        # 1. Try to extract from JWT if authenticated
        try:
            # We wrap this in try-except because get_jwt() raises error if JWT is missing
            claims = get_jwt()
            if claims and "tenant_id" in claims:
                tenant_id = claims["tenant_id"]
        except Exception:
            pass

        # 2. Fallback to HTTP header if not in JWT (useful for public registration or initial auth check)
        if not tenant_id:
            tenant_id = request.headers.get("X-Tenant-ID")

        # 3. Fallback to query parameter
        if not tenant_id:
            tenant_id = request.args.get("tenant_id")

        if tenant_id:
            set_current_tenant(tenant_id)
            g.tenant_id = tenant_id
        else:
            clear_current_tenant()
            g.tenant_id = None

    @app.after_request
    def log_request_performance(response):
        """
        Tracks performance latency and logs details of the completed request.
        """
        clear_current_tenant()  # Reset context-local storage to prevent memory leaks
        
        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            # Log slow requests (latency > 500ms) or standard request diagnostics
            tenant_str = f"Tenant: {g.tenant_id}" if getattr(g, "tenant_id", None) else "No Tenant"
            logger.info(
                f"[{response.status_code}] {request.method} {request.path} - {tenant_str} - Latency: {duration:.4f}s"
            )
            
            # Inject duration header for developer diagnostics
            response.headers["X-Response-Time-Seconds"] = f"{duration:.4f}"
            
        return response
