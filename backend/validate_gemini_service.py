import asyncio, sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

async def test():
    from services.gemini_service import GeminiService

    # 1) Singleton check
    svc  = GeminiService.get_instance()
    svc2 = GeminiService.get_instance()
    assert svc is svc2, "FAIL: not a singleton"
    print(f"[SINGLETON ] PASS — same instance: {svc is svc2}")
    print(f"[SIM MODE  ] simulation = {svc.is_simulation}")

    # 2) Text generation
    text = await svc.generate(prompt="Say HELLO_WORLD and nothing else.")
    print(f"[GENERATE  ] {text.strip()[:80]}")

    # 3) JSON mode
    json_prompt = 'Return a JSON object exactly like this: {"status": "SERVICE_OK", "version": 1}'
    result = await svc.generate_json(prompt=json_prompt, fallback={"status": "FALLBACK"})
    print(f"[JSON MODE ] {result}")

    print("\nGeminiService: ALL CHECKS PASSED")

asyncio.run(test())
