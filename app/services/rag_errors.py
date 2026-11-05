class RagDependencyError(Exception):
    def __init__(self, service: str):
        self.service = service
        self.detail = {
            "embedding": "Layanan embedding belum siap. Pastikan Ollama berjalan dan model embedding tersedia.",
            "qdrant": "Database knowledge (Qdrant) tidak terhubung. Jalankan Docker Desktop dan layanan Qdrant, lalu coba lagi.",
        }[service]
        super().__init__(self.detail)
