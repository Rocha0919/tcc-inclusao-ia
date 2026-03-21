import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
    MODEL_NAME = "llama3"

    @classmethod
    def gerar_recomendacao(cls, prompt_text):
        payload = {
            "model": cls.MODEL_NAME,
            "prompt": prompt_text,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }

        try:
            resposta = requests.post(
                cls.OLLAMA_URL,
                json=payload,
                timeout=300
            )

            resposta.raise_for_status()
            dados = resposta.json()

            resposta_texto = dados.get("response")

            if not resposta_texto:
                logger.error("Resposta vazia da IA.")
                return None

            try:
                return json.loads(resposta_texto)
            except json.JSONDecodeError:
                pass

            inicio = resposta_texto.find("{")
            fim = resposta_texto.rfind("}") + 1

            if inicio == -1 or fim == -1:
                logger.error(f"Nenhum JSON encontrado na resposta da IA.\nTexto bruto: {resposta_texto}")
                return None

            json_texto = resposta_texto[inicio:fim]

            resultado_json = json.loads(json_texto)

            return resultado_json

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Erro de conexão com o Ollama. Verifique se ele está rodando. Erro: {e}"
            )
            return None

        except json.JSONDecodeError as e:
            logger.error(
                f"O modelo retornou JSON inválido. Erro: {e}\nTexto bruto: {resposta_texto}"
            )
            return None