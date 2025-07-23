#!/usr/bin/env python3
"""
UNIFIED PRODUCTION COORDINATOR API
Flask API wrapper for the unified production coordinator.
Provides monitoring and control endpoints.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
from datetime import datetime

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the unified coordinator
from backend.unified_production_coordinator import UnifiedProductionCoordinator
from backend.core.port_config import get_port

# Create Flask app
app = Flask(__name__)
CORS(app)

# Global coordinator instance
coordinator = None
coordinator_thread = None

def get_coordinator():
    """Get or create the coordinator instance"""
    global coordinator
    if coordinator is None:
        coordinator = UnifiedProductionCoordinator()
    return coordinator

@app.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        coord = get_coordinator()
        health_status = coord.get_health_status()
        return jsonify({
            "status": "healthy",
            "coordinator": health_status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/status")
def get_status():
    """Get detailed pipeline status"""
    try:
        coord = get_coordinator()
        status = coord.get_pipeline_status()
        return jsonify({
            "status": "ok",
            "data": status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/start", methods=["POST"])
def start_pipeline():
    """Start the unified production pipeline"""
    try:
        coord = get_coordinator()
        if coord.running:
            return jsonify({
                "status": "already_running",
                "message": "Pipeline is already running"
            })
        
        coord.start_pipeline()
        return jsonify({
            "status": "started",
            "message": "Unified production pipeline started successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route("/stop", methods=["POST"])
def stop_pipeline():
    """Stop the unified production pipeline"""
    try:
        coord = get_coordinator()
        if not coord.running:
            return jsonify({
                "status": "not_running",
                "message": "Pipeline is not running"
            })
        
        coord.stop_pipeline()
        return jsonify({
            "status": "stopped",
            "message": "Unified production pipeline stopped successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route("/restart", methods=["POST"])
def restart_pipeline():
    """Restart the unified production pipeline"""
    try:
        coord = get_coordinator()
        
        # Stop if running
        if coord.running:
            coord.stop_pipeline()
            time.sleep(1)  # Brief pause
        
        # Start pipeline
        coord.start_pipeline()
        
        return jsonify({
            "status": "restarted",
            "message": "Unified production pipeline restarted successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route("/performance")
def get_performance():
    """Get performance statistics"""
    try:
        coord = get_coordinator()
        stats = coord.performance_stats
        
        # Calculate additional metrics
        success_rate = (
            stats["successful_cycles"] / max(1, stats["total_cycles"]) * 100
        )
        
        return jsonify({
            "status": "ok",
            "data": {
                "total_cycles": stats["total_cycles"],
                "successful_cycles": stats["successful_cycles"],
                "failed_cycles": stats["failed_cycles"],
                "success_rate_percent": round(success_rate, 2),
                "average_cycle_time": round(stats["average_cycle_time"], 3),
                "last_successful_cycle": stats["last_successful_cycle"],
                "consecutive_failures": coord.consecutive_failures
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route("/")
def index():
    """API information endpoint"""
    return jsonify({
        "service": "Unified Production Coordinator API",
        "version": "1.0.0",
        "endpoints": {
            "GET /health": "Health check",
            "GET /status": "Detailed pipeline status",
            "POST /start": "Start pipeline",
            "POST /stop": "Stop pipeline", 
            "POST /restart": "Restart pipeline",
            "GET /performance": "Performance statistics"
        },
        "timestamp": datetime.now().isoformat()
    })

def main():
    """Main function to run the API server"""
    port = get_port("unified_production_coordinator")
    print(f"[UNIFIED_COORDINATOR_API] 🚀 Starting API server on port {port}")
    
    # Start the coordinator automatically
    coord = get_coordinator()
    coord.start_pipeline()
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main() 