import io
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class R2StorageService:
    """
    Serviço de integração com Cloudflare R2 (S3-compatible Object Storage).
    Responsável por listar e baixar materiais didáticos e arquivos de apoio.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.endpoint_url = endpoint_url or settings.R2_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.R2_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.R2_SECRET_ACCESS_KEY
        self.bucket_name = bucket_name or settings.R2_BUCKET_NAME
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.endpoint_url or not self.access_key_id or not self.secret_access_key:
                raise ValueError("Credenciais do Cloudflare R2 não estão configuradas nas variáveis de ambiente.")
            
            import boto3
            from botocore.config import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
                region_name="auto"
            )
        return self._client

    def list_files(self, prefix: str = "", extension: Optional[str] = ".pdf") -> List[Dict[str, Any]]:
        """
        Lista arquivos presentes no bucket R2, opcionalmente filtrando por prefixo e extensão.
        """
        try:
            logger.info(f"Listando arquivos no bucket R2 '{self.bucket_name}' com prefixo '{prefix}'...")
            paginator = self.client.get_paginator("list_objects_v2")
            files = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj.get("Key", "")
                    if extension and not key.lower().endswith(extension.lower()):
                        continue
                    files.append({
                        "key": key,
                        "size": obj.get("Size", 0),
                        "last_modified": obj.get("LastModified"),
                        "etag": obj.get("ETag", "").strip('"')
                    })
            
            logger.info(f"Encontrados {len(files)} arquivos no bucket R2.")
            return files
        except Exception as e:
            logger.error(f"Erro ao listar arquivos do bucket R2 '{self.bucket_name}': {e}")
            raise

    def download_file_bytes(self, file_key: str) -> bytes:
        """
        Baixa o conteúdo do arquivo do R2 em memória (bytes).
        """
        try:
            logger.info(f"Baixando arquivo '{file_key}' do bucket '{self.bucket_name}'...")
            response = self.client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read()
        except Exception as e:
            logger.error(f"Erro ao baixar arquivo '{file_key}' do R2: {e}")
            raise

    def download_file_to_path(self, file_key: str, dest_path: str) -> None:
        """
        Baixa o arquivo do R2 e grava em um caminho de destino local.
        """
        try:
            logger.info(f"Baixando '{file_key}' para '{dest_path}'...")
            self.client.download_file(self.bucket_name, file_key, dest_path)
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo '{file_key}' em '{dest_path}': {e}")
            raise
