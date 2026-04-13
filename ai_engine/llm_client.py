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
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }

        try:
            print("🔵 Enviando requisição para IA...")

            resposta = requests.post(
                cls.OLLAMA_URL,
                json=payload,
                timeout=300
            )

            print("🟢 Status:", resposta.status_code)

            resposta.raise_for_status()

            dados = resposta.json()
            resposta_texto = dados.get("response")

            print("🟡 Resposta bruta da IA:")
            print(resposta_texto)

            if not resposta_texto:
                logger.error("Resposta vazia da IA.")
                return None

            # Tentativa direta
            try:
                return json.loads(resposta_texto)
            except json.JSONDecodeError:
                print("⚠️ JSON direto falhou, tentando extrair...")

            # Extrair JSON do meio do texto
            inicio = resposta_texto.find("{")
            fim = resposta_texto.rfind("}") + 1

            if inicio == -1 or fim == -1:
                logger.error(f"Nenhum JSON encontrado.\nTexto: {resposta_texto}")
                return None

            json_texto = resposta_texto[inicio:fim]

            try:
                resultado_json = json.loads(json_texto)
                return resultado_json
            except Exception as e:
                print("❌ Erro ao parsear JSON:", e)
                print("❌ Conteúdo recebido:", json_texto)
                return None

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Erro de conexão com o Ollama: {e}"
            )
            return None

        except Exception as e:
            logger.error(f"Erro inesperado: {e}")
            return None