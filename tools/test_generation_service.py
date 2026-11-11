from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.fooocus_request import FooocusRequest
from services.fooocus_client import FooocusClient
from services.generation_service import GenerationService


client = FooocusClient()

service = GenerationService(client)

request = FooocusRequest(
    prompt="Hello PromptLAB"
)

service.generate(request)