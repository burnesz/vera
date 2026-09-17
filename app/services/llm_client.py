import time
import logging
from typing import Dict, Any, Optional, Tuple
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Exceção base para erros do cliente LLM."""
    pass


class LLMConnectionError(LLMError):
    """Exceção levantada quando o servidor local Ollama está inacessível (RN-INF02)."""
    pass


class LLMTimeoutError(LLMError):
    """Exceção levantada quando a requisição ao LLM excede o tempo limite (RN-INF03)."""
    pass


class LLMResponseError(LLMError):
    """Exceção levantada quando o LLM retorna status HTTP de erro ou formato inválido."""
    pass


class LLMClient:
    """
    Gateway de comunicação com o modelo de linguagem (Qwen 2.5) servido localmente via Ollama.
    Atende aos requisitos de infraestrutura e resiliência:
    - RN-INF01: URL e modelo configuráveis via settings / variáveis de ambiente.
    - RN-INF02: Health-check prévio via API do Ollama (/api/tags) para conferir status e modelo ativo.
    - RN-INF03: Retry com backoff exponencial para estabilidade operacional.
    - RN-INF06: Suporte a modo mock para desenvolvimento e testes desacoplados.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: int = 3,
        mock_mode: bool = False,
        **kwargs: Any
    ):
        self.endpoint_url = (endpoint_url or settings.LLM_ENDPOINT_URL).rstrip("/")
        self.model_name = model_name or getattr(settings, "LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries
        self.mock_mode = mock_mode

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json"
        }

    def _build_payload_and_url(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1
    ) -> Tuple[str, Dict[str, Any]]:
        resolved_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

        url = f"{self.endpoint_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": resolved_max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "repeat_penalty": repetition_penalty
            }
        }
        return url, payload

    def health_check(self) -> Dict[str, Any]:
        """
        Executa verificação de disponibilidade no servidor Ollama local (GET /api/tags).
        Retorna dicionário com status, modelo verificado e tempo de resposta.
        """
        if self.mock_mode or not self.endpoint_url:
            return {"status": "mock", "healthy": True, "message": "Modo Mock ativo"}

        url = f"{self.endpoint_url}/api/tags"
        start_time = time.time()
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=self.headers)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                if response.status_code == 200:
                    data = response.json() if response.text and response.headers.get("content-type", "").startswith("application/json") else {}
                    models = [m.get("name") for m in data.get("models", [])]
                    model_available = any(self.model_name in m for m in models) if self.model_name else True
                    return {
                        "status": "healthy",
                        "healthy": True,
                        "provider": "ollama",
                        "model": self.model_name,
                        "model_available": model_available,
                        "latency_ms": latency_ms,
                        "details": data
                    }
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "message": f"Servidor Ollama retornou HTTP {response.status_code}"
                }
        except httpx.TimeoutException:
            return {
                "status": "timeout",
                "healthy": False,
                "message": f"Tempo limite de conexão esgotado ao acessar {url}"
            }
        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "message": f"Falha de conexão com o servidor Ollama ({e})"
            }

    async def ahealth_check(self) -> Dict[str, Any]:
        """
        Versão assíncrona do health check do Ollama local.
        """
        if self.mock_mode or not self.endpoint_url:
            return {"status": "mock", "healthy": True, "message": "Modo Mock ativo"}

        url = f"{self.endpoint_url}/api/tags"
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                if response.status_code == 200:
                    data = response.json() if response.text and response.headers.get("content-type", "").startswith("application/json") else {}
                    models = [m.get("name") for m in data.get("models", [])]
                    model_available = any(self.model_name in m for m in models) if self.model_name else True
                    return {
                        "status": "healthy",
                        "healthy": True,
                        "provider": "ollama",
                        "model": self.model_name,
                        "model_available": model_available,
                        "latency_ms": latency_ms,
                        "details": data
                    }
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "message": f"Servidor Ollama retornou HTTP {response.status_code}"
                }
        except httpx.TimeoutException:
            return {
                "status": "timeout",
                "healthy": False,
                "message": f"Tempo limite de conexão esgotado ao acessar {url}"
            }
        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "message": f"Falha de conexão com o servidor Ollama ({e})"
            }

    def generate(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1
    ) -> str:
        """
        Gera resposta a partir de um prompt usando política de retry com backoff exponencial.
        """
        if self.mock_mode or not self.endpoint_url:
            return self._generate_mock_response(prompt)

        url, payload = self._build_payload_and_url(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty
        )

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Enviando requisição ao Ollama ({url}, tentativa {attempt}/{self.max_retries})...")
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, json=payload, headers=self.headers)

                    if response.status_code == 200:
                        data = response.json()
                        if "response" in data:
                            return data["response"]
                        raise LLMResponseError(f"Formato de resposta inesperado do Ollama: {data}")

                    if response.status_code in [502, 503, 504]:
                        logger.warning(f"Servidor retornou HTTP {response.status_code} na tentativa {attempt}.")
                    else:
                        raise LLMResponseError(
                            f"Erro retornado pelo LLM (HTTP {response.status_code}): {response.text}"
                        )

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout na tentativa {attempt}/{self.max_retries} ({e})")
                last_exception = LLMTimeoutError(f"Tempo limite de {self.timeout_seconds}s esgotado ao gerar resposta.")
            except httpx.RequestError as e:
                logger.warning(f"Erro de conexão na tentativa {attempt}/{self.max_retries} ({e})")
                last_exception = LLMConnectionError(f"Falha de comunicação com {url}: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado no cliente LLM: {e}")
                last_exception = e

            # Backoff exponencial antes da próxima tentativa
            if attempt < self.max_retries:
                sleep_time = (2 ** (attempt - 1)) * 1.5
                logger.info(f"Aguardando {sleep_time:.1f}s antes da nova tentativa...")
                time.sleep(sleep_time)

        if isinstance(last_exception, LLMError):
            raise last_exception
        raise LLMConnectionError(f"Não foi possível obter resposta do LLM após {self.max_retries} tentativas: {last_exception}")

    async def agenerate(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1
    ) -> str:
        """
        Versão assíncrona da geração de resposta no Ollama.
        """
        if self.mock_mode or not self.endpoint_url:
            return self._generate_mock_response(prompt)

        url, payload = self._build_payload_and_url(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty
        )

        import asyncio
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=self.headers)

                    if response.status_code == 200:
                        data = response.json()
                        if "response" in data:
                            return data["response"]
                        raise LLMResponseError(f"Formato de resposta inesperado do Ollama: {data}")

                    if response.status_code in [502, 503, 504]:
                        logger.warning(f"Servidor retornou HTTP {response.status_code} na tentativa {attempt}.")
                    else:
                        raise LLMResponseError(
                            f"Erro retornado pelo LLM (HTTP {response.status_code}): {response.text}"
                        )

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout assíncrono na tentativa {attempt}/{self.max_retries} ({e})")
                last_exception = LLMTimeoutError(f"Tempo limite de {self.timeout_seconds}s esgotado.")
            except httpx.RequestError as e:
                logger.warning(f"Erro de conexão na tentativa {attempt}/{self.max_retries} ({e})")
                last_exception = LLMConnectionError(f"Falha de comunicação assíncrona com {url}: {e}")
            except Exception as e:
                last_exception = e

            if attempt < self.max_retries:
                sleep_time = (2 ** (attempt - 1)) * 1.5
                await asyncio.sleep(sleep_time)

        if isinstance(last_exception, LLMError):
            raise last_exception
        raise LLMConnectionError(f"Não foi possível obter resposta assíncrona após {self.max_retries} tentativas: {last_exception}")

    def _generate_mock_response(self, prompt: str) -> str:
        """
        Gera resposta didática simulada para ambiente de desenvolvimento e testes unitários.
        """
        return (
            "### Análise da Questão e Diagnóstico do Erro\n\n"
            "1. **Identificação do Conceito:** A questão exige a aplicação direta das relações métricas "
            "e propriedades trigonométricas fundamentais abordadas no conteúdo de Matemática do ENEM.\n"
            "2. **Análise do Distrator Escolhido:** A alternativa assinalada pelo estudante reflete um erro conceitual "
            "comum na interpretação da proporção ou no sinal da função.\n"
            "3. **Resolução Passo a Passo:** Aplicando o conteúdo teórico correto, chegamos à alternativa do gabarito oficial.\n"
            "4. **Recomendação de Estudo:** Revise o material didático sobre o tema e pratique exercícios com foco na identificação de grandezas."
        )
