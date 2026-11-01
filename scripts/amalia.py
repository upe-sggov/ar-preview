"""Acesso ao Amália — o mesmo esquema do Radar de Notícias: pesos abertos (Apache 2.0) descarregados do Hugging Face,
conversão quantizada de ~5,5 GB que corre no próprio servidor do GitHub, sem placa gráfica nem serviço externo
(llama-cpp, create_chat_completion). O modelo fica em cache (~/.cache/huggingface) entre corridas.
Para usar outro ficheiro local: AMALIA_GGUF=/caminho/modelo.gguf"""
import json, os, re

REPO_GGUF = 'layerx-labs/AMALIA-9B-0626-DPO-GGUF'          # o mesmo do Radar de Notícias (sintese_ia.py)
FICHEIRO_GGUF = 'AMALIA-9B-0626-DPO-Q4_K_M.gguf'

_MODELO = None
def modelo():
    global _MODELO
    if _MODELO is None:
        from llama_cpp import Llama
        caminho = os.environ.get('AMALIA_GGUF')
        if not caminho or not os.path.exists(caminho):
            from huggingface_hub import hf_hub_download
            caminho = hf_hub_download(repo_id=REPO_GGUF, filename=FICHEIRO_GGUF)
        _MODELO = Llama(model_path=caminho, n_ctx=8192, n_threads=os.cpu_count() or 4, verbose=False)
    return _MODELO

def perguntar(sistema, utilizador, max_tokens=800):
    r = modelo().create_chat_completion(
        messages=[{'role': 'system', 'content': sistema}, {'role': 'user', 'content': utilizador}],
        temperature=0, max_tokens=max_tokens)
    return r['choices'][0]['message']['content']

def json_da_resposta(texto):
    """O Amália por vezes embrulha o JSON em texto ou em ```; extrai o primeiro objeto/lista válido."""
    m = re.search(r'(\{.*\}|\[.*\])', texto or '', re.S)
    try: return json.loads(m.group(1)) if m else None
    except Exception: return None
