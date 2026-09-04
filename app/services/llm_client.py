import time
import logging
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Exceção base para erros do cliente LLM."""
    pass


class LLMConnectionError(LLMError):
    """Exceção levantada quando o túnel ou servidor remoto está inacessível (RN-INF02)."""
    pass


class LLMTimeoutError(LLMError):
    """Exceção levantada quando a requisição ao LLM excede o tempo limite (RN-INF03)."""
    pass


class LLMResponseError(LLMError):
    """Exceção levantada quando o LLM retorna status HTTP de erro ou formato inválido."""
    pass


class LLMClient:
    """
    Gateway de comunicação com o modelo de linguagem (Qwen 2.5) servido remotamente.
    Atende aos requisitos de infraestrutura e resiliência:
    - RN-INF01: URL dinâmica e configurável via settings.
    - RN-INF02: Health-check com fallback gracioso.
    - RN-INF03: Retry com backoff exponencial para estabilidade de rede.
    - RN-INF04: Autenticação via header X-API-Key.
    - RN-INF06: Suporte a modo mock para desenvolvimento/testes locais desacoplados.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: int = 3,
        mock_mode: bool = False
    ):
        self.endpoint_url = (endpoint_url or settings.LLM_ENDPOINT_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries
        self.mock_mode = mock_mode

    @property
    def headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "1"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def health_check(self) -> Dict[str, Any]:
        """
        Executa verificação de disponibilidade no endpoint remoto (GET /health).
        Retorna dicionário com status e tempo de resposta.
        """
        if self.mock_mode or not self.endpoint_url:
            return {"status": "mock", "healthy": True, "message": "Modo Mock ativo"}

        url = f"{self.endpoint_url}/health"
        start_time = time.time()
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=self.headers)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "details": response.json() if response.text else {}
                    }
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "message": f"Servidor remoto retornou HTTP {response.status_code}"
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
                "message": f"Falha de conexão com o túnel do LLM ({e})"
            }

    async def ahealth_check(self) -> Dict[str, Any]:
        """
        Versão assíncrona do health check.
        """
        if self.mock_mode or not self.endpoint_url:
            return {"status": "mock", "healthy": True, "message": "Modo Mock ativo"}

        url = f"{self.endpoint_url}/health"
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "details": response.json() if response.text else {}
                    }
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "message": f"Servidor remoto retornou HTTP {response.status_code}"
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
                "message": f"Falha de conexão com o túnel do LLM ({e})"
            }

    def generate(
        self,
        prompt: str,
        session_id: Optional[str] = "default",
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

        resolved_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

        url = f"{self.endpoint_url}/generate"
        payload = {
            "prompt": prompt,
            "session_id": session_id or "default",
            "max_tokens": resolved_max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty
        }

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Enviando requisição de geração ao LLM (tentativa {attempt}/{self.max_retries}, max_tokens={resolved_max_tokens})...")
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, json=payload, headers=self.headers)

                    if response.status_code == 200:
                        data = response.json()
                        if "response" in data:
                            return data["response"]
                        raise LLMResponseError(f"Formato de resposta inesperado do LLM: {data}")

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
        session_id: Optional[str] = "default",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1
    ) -> str:
        """
        Versão assíncrona da geração de resposta.
        """
        if self.mock_mode or not self.endpoint_url:
            return self._generate_mock_response(prompt)

        resolved_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

        url = f"{self.endpoint_url}/generate"
        payload = {
            "prompt": prompt,
            "session_id": session_id or "default",
            "max_tokens": resolved_max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty
        }

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
                        raise LLMResponseError(f"Formato de resposta inesperado do LLM: {data}")

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
