import os
from dotenv import load_dotenv
load_dotenv(".env")

from app.tracing import get_langfuse_client, tracing_enabled, LANGFUSE_SDK_AVAILABLE
from langfuse import Langfuse

print(f"LANGFUSE_PUBLIC_KEY: {os.getenv('LANGFUSE_PUBLIC_KEY')[:20]}...")
print(f"LANGFUSE_SECRET_KEY: {os.getenv('LANGFUSE_SECRET_KEY')[:20]}...")
print(f"LANGFUSE_SDK_AVAILABLE: {LANGFUSE_SDK_AVAILABLE}")
print(f"tracing_enabled(): {tracing_enabled()}")
client = get_langfuse_client()
print(f"Client type: {type(client).__name__}")
print(f"Has flush: {hasattr(client, 'flush')}")
if hasattr(client, 'flush_async'):
    print(f"Has flush_async: True")
else:
    print(f"Has flush_async: False - using flush() only")
try:
    result = client.auth_check()
    print(f"auth_check result: {result}")
except Exception as e:
    print(f"auth_check error: {e}")
