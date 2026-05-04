import json
import logging

try:
    import requests
except ModuleNotFoundError:
    requests = None


logger = logging.getLogger(__name__)


class LLMClient:
    OLLAMA_URL = "http://host.docker.internal:11434/api/generate"

    @classmethod
    def gerar_recomendacao(cls, prompt_text, model_name="llama3"):
        if requests is None:
            logger.error(
                "A biblioteca requests nao esta instalada. Nao foi possivel consultar o Ollama."
            )
            return None

        payload = {
            "model": model_name,
            "prompt": prompt_text,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }

        try:
            print(f"Enviando requisicao para IA ({model_name})...")

            response = requests.post(
                cls.OLLAMA_URL,
                json=payload,
                timeout=600
            )

            print(f"Status ({model_name}):", response.status_code)
            response.raise_for_status()

            data = response.json()
            response_text = data.get("response")

            if not response_text:
                logger.error(f"Resposta vazia da IA ({model_name}).")
                return None

            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                print(f"JSON direto falhou no {model_name}, tentando extrair...")

            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start == -1 or end == -1:
                logger.error(f"Nenhum JSON encontrado ({model_name}).\nTexto: {response_text}")
                return None

            json_text = response_text[start:end]

            try:
                return json.loads(json_text)
            except Exception as error:
                print(f"Erro ao parsear JSON ({model_name}):", error)
                return None

        except requests.exceptions.RequestException as error:
            logger.error(f"Erro de conexao com o Ollama: {error}")
            return None
        except Exception as error:
            logger.error(f"Erro inesperado: {error}")
            return None
