from urllib.parse import urlsplit

from app.core.config import settings


# GOAT inclusion snapshot: https://commandcode.ai/docs/plans/goat, 2026-11-10.
GOAT_MODELS = frozenset("""
gpt-6-luna
gpt-5.6-luna
gpt-5.6-sol
google/gemini-3.8-flash
google/gemini-3.7-flash
deepseek/deepseek-v4.1-flash
deepseek/deepseek-v4.1-flash-fast
deepseek/deepseek-v4.1-flash-ultrafast
deepseek/deepseek-v4-flash
deepseek/deepseek-v4-flash-fast
deepseek/deepseek-v4-flash-vision-exp
deepseek/deepseek-v4-pro
Qwen/Qwen3.8-Max-Prime
Qwen/Qwen3.8-Max-0902
Qwen/Qwen3.8-Max
Qwen/Qwen3.8-Flash
Qwen/Qwen3.8-Omni-Flash
Qwen/Qwen3.8-27B
Qwen/Qwen3.7-Flash
Qwen/Qwen3.7-Max
Qwen/Qwen3.7-Plus
Qwen/Qwen3.6-Max-Preview
Qwen/Qwen3.6-Plus
MiniMaxAI/MiniMax-M2.5
MiniMaxAI/MiniMax-M2.7
MiniMaxAI/MiniMax-M3
minimax/minimax-m3.1-flash
moonshotai/Kimi-K2.5
moonshotai/Kimi-K2.6
moonshotai/Kimi-K2.7-Code
moonshotai/Kimi-K2.7-Code-Highspeed
moonshotai/Kimi-K3
moonshotai/Kimi-K3.1-Pro
zai-org/GLM-5
zai-org/GLM-5.1
zai-org/GLM-5.2
zai-org/GLM-5.2-Fast
zai-org/GLM-5.3
z-ai/glm-5.3-flash
z-ai/glm-5.3-flashx
inclusionai/ling-3.1-flash
inclusionai/ling-3.1-flash-1019
meta/muse-ember
meta/muse-spark-1.2
meta/muse-spark-1.2-contributor
meta/muse-spark-1.3
meta/muse-spark-1.3-contributor
meta/muse-spark-open
meituan/LongCat-2.0
mistral/mistral-large-4
nvidia/nemotron-3-ultra-550b-a55b
nvidia/nemotron-3.5-super-vl
ornith/ornith-1.5-122b
stealth/crouton-alpha
stealth/glyph-cluster:free
stepfun/Step-3.5-Flash
stepfun/Step-3.7-Flash
stepfun/Step-5-Preview
tencent/hy3-paid
tencent/hy4-preview
thinkingmachines/inkling
thinkingmachines/inkling-small
xai/grok-4.5
xai/grok-4.6
xai/grok-4.7
xiaomi/mimo-v2.6-flash
xiaomi/mimo-v2.6-pro
xiaomi/mimo-v2.6-pro-ultraspeed
""".split())


def active_plan():
    if settings.AI_PROVIDER == "api" and urlsplit(settings.AI_API_BASE_URL).hostname == "api.commandcode.ai":
        return settings.COMMANDCODE_PLAN
    return "catalog"


def model_allowed(model):
    return active_plan() != "goat" or model in GOAT_MODELS
