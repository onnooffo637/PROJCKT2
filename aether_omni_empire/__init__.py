"""
Aether Omni Empire Unified Package.
Re-exports all architectural subsystems for V3.0, V4.0 and V5.0.
"""

import sys
import os

# Ensure workspace root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import multi_tenant_sandbox
import live_voip_call_engine
import admin_telemetry_and_archiver
import bot_factory
import official_bot_engine
import security_and_rbac
import mini_app_webapp

__all__ = [
    "multi_tenant_sandbox",
    "live_voip_call_engine",
    "admin_telemetry_and_archiver",
    "bot_factory",
    "official_bot_engine",
    "security_and_rbac",
    "mini_app_webapp",
]

