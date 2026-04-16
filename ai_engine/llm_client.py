import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
    # Removemos a constante MODEL_NAME fixa para passar dinamicamente

    @classmethod
    def gerar_recomendacao(cls, prompt_text, model_name="llama3"):
        payload = {
            "model": model_name, # Agora recebe o modelo por parâmetro
            "prompt": prompt_text,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }

        try:
            print(f"🔵 Enviando requisição para IA ({model_name})...")

            resposta = requests.post(
                cls.OLLAMA_URL,
                json=payload,
                timeout=300
            )

            print(f"🟢 Status ({model_name}):", resposta.status_code)
            resposta.raise_for_status()

            dados = resposta.json()
            resposta_texto = dados.get("response")

            if not resposta_texto:
                logger.error(f"Resposta vazia da IA ({model_name}).")
                return None

            try:
                return json.loads(resposta_texto)
            except json.JSONDecodeError:
                print(f"⚠️ JSON direto falhou no {model_name}, tentando extrair...")

            inicio = resposta_texto.find("{")
            fim = resposta_texto.rfind("}") + 1

            if inicio == -1 or fim == -1:
                logger.error(f"Nenhum JSON encontrado ({model_name}).\nTexto: {resposta_texto}")
                return None

            json_texto = resposta_texto[inicio:fim]

            try:
                resultado_json = json.loads(json_texto)
                return resultado_json
            except Exception as e:
                print(f"❌ Erro ao parsear JSON ({model_name}):", e)
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão com o Ollama: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado: {e}")
            return None