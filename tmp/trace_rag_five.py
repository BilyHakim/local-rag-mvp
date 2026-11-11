import asyncio
import contextvars
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import rag_service as r
from app.services.model_service import chat_model_context
from app.services.ai_service import ai_service

question = '''Saya punya beberapa pertanyaan. Tolong dijawab dengan benar ya.

* Apa kode verifikasi knowledge Lentera Office?
* Berapa lama garansi elektronik Lampu Sora?
* Pesanan mana yang dibatalkan dan apa produknya?
* Berapa harga Meja Nara dan apa SKU-nya?
* Siapa pendiri Lentera Office dan kapan perusahaan didirikan?'''
current = contextvars.ContextVar('trace_question', default='')

async def main():
    chat_model_context.set('z-ai/glm-5.3-flash')
    original_single = r._answer_single_question
    original_chat = r.ollama_service.chat
    original_select = r.select_relevant_evidence
    original_grounded = r.is_answer_grounded

    async def single(q, top_k):
        current.set(q.splitlines()[-1])
        result = await original_single(q, top_k)
        print('FINAL', current.get(), repr(result['answer']), flush=True)
        return result

    async def chat(**kwargs):
        result = await original_chat(**kwargs)
        print('CHAT', current.get(), kwargs['system_prompt'].splitlines()[0], repr(result), flush=True)
        return result

    async def select(**kwargs):
        print('RETRIEVED', current.get(), [(s.get('filename'), s['text']) for s in kwargs['search_results']], flush=True)
        result = await original_select(**kwargs)
        print('EVIDENCE', current.get(), [s.get('_context_text') for s in result], flush=True)
        return result

    def grounded(*args, **kwargs):
        result = original_grounded(*args, **kwargs)
        print('GROUNDED', current.get(), result, repr(args[0]), flush=True)
        return result

    r._answer_single_question = single
    r.ollama_service.chat = chat
    r.select_relevant_evidence = select
    r.is_answer_grounded = grounded
    try:
        result = await r.answer_with_rag(question)
        print('RESULT', result['answer'], flush=True)
        print('CITED', [(c['filename'], c['evidence_text']) for c in result['citations']], flush=True)
    finally:
        await ai_service.close()
        await r.ollama_service.close()

asyncio.run(main())
