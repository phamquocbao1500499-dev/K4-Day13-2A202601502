import os
from dotenv import load_dotenv
load_dotenv(".env", override=True)

from app.tracing import get_langfuse_client, tracing_enabled

print(f"tracing_enabled(): {tracing_enabled()}")
client = get_langfuse_client()

# Try creating a trace using the correct method
print("Creating test trace...")
with client.start_as_current_span(name="test-trace"):
    print("Inside span context")
print("Span context ended")

# Flush
print("Flushing...")
client.flush()
print("Flush complete")
print("Done. Check Langfuse dashboard for trace named 'test-trace'")
