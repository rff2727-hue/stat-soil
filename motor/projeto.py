"""
Arquivo de projeto (.estatexp): dados, delineamento, opções e estilos em um
único arquivo para reabrir a análise depois (como o .jasp/.omv).
"""
from __future__ import annotations

import dataclasses
import io
import json
import zipfile

import pandas as pd

from .anova import Opcoes
from .modelo import Especificacao, Fator

VERSAO = 1


def _spec_dict(spec):
    d = dataclasses.asdict(spec)
    return d


def _spec_de_dict(d):
    fatores = [Fator(**f) for f in d.pop("fatores", [])]
    return Especificacao(fatores=fatores, **d)


def _chaves_str(dic):
    """Converte dicionários com chaves-tupla para chaves JSON."""
    return [[json.dumps(k, ensure_ascii=False, default=str), v] for k, v in dic.items()]


def _chaves_tupla(lista):
    def tup(x):
        return tuple(tup(i) for i in x) if isinstance(x, list) else x
    return {tup(json.loads(k)): v for k, v in lista}


def _json_padrao(o):
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def _df_para_json(df: pd.DataFrame) -> str:
    """Serialização exata (floats pelo repr do Python, sem perda de dígitos)."""
    obj = df.astype(object).where(df.notna(), None)
    return json.dumps({"columns": [str(c) for c in df.columns], "index": [int(i) if str(i).lstrip("-").isdigit()
                                                                          else str(i) for i in df.index],
                       "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
                       "data": obj.values.tolist()}, ensure_ascii=False, default=_json_padrao)


def _df_de_json(txt: str) -> pd.DataFrame:
    d = json.loads(txt)
    if "dtypes" not in d:   # projetos antigos (pandas orient="split")
        return pd.read_json(io.StringIO(txt), orient="split")
    df = pd.DataFrame(d["data"], columns=d["columns"], index=d["index"])
    for c, t in d["dtypes"].items():
        try:
            if t.startswith("datetime"):
                df[c] = pd.to_datetime(df[c])
            elif t in ("object", "string", "str"):
                continue
            else:
                df[c] = df[c].astype(t)
        except (ValueError, TypeError):
            pass
    return df


def salvar(df, nome_arquivo, config, estado) -> bytes:
    """config: dict(spec, opcoes, separar, respostas); estado: dicionários de interface."""
    meta = {
        "plataforma": "Stat-Soil", "versao_projeto": VERSAO, "arquivo_dados": nome_arquivo,
        "spec": _spec_dict(config["spec"]), "opcoes": dataclasses.asdict(config["opcoes"]),
        "separar": config.get("separar"), "respostas": list(config.get("respostas") or []),
        "transf_var": estado.get("transf_var", {}),
        "modelo_escolhido": [[json.dumps(list(k), ensure_ascii=False, default=str), _chaves_str(v)]
                             for k, v in estado.get("modelo_escolhido", {}).items()],
        "rotulos_y": estado.get("rotulos_y", {}), "tema_preset": estado.get("tema_preset"),
        "tema_global": estado.get("tema_global", {}), "ajustes": estado.get("ajustes", {}),
        "painel_cfg": estado.get("painel_cfg"), "painel_tema": estado.get("painel_tema", {}),
        "excluir": {json.dumps(list(k), ensure_ascii=False): sorted(v) for k, v in estado.get("excluir", {}).items()},
        "multi_cfg": estado.get("multi_cfg"),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("projeto.json", json.dumps(meta, ensure_ascii=False, indent=1, default=str))
        z.writestr("dados.json", _df_para_json(df))
    return buf.getvalue()


def carregar(conteudo: bytes):
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        meta = json.loads(z.read("projeto.json").decode("utf-8"))
        df = _df_de_json(z.read("dados.json").decode("utf-8"))
    if meta.get("plataforma") not in ("Stat-Soil", "Estatística Experimental"):
        raise ValueError("Arquivo não é um projeto da plataforma.")
    spec = _spec_de_dict(dict(meta["spec"]))
    op = Opcoes(**meta["opcoes"])
    modelo = {}
    for k, v in meta.get("modelo_escolhido", []):
        chave = tuple(json.loads(k))
        modelo[chave] = _chaves_tupla(v)
    excluir = {tuple(json.loads(k)): set(v) for k, v in meta.get("excluir", {}).items()}
    estado = dict(transf_var=meta.get("transf_var", {}), modelo_escolhido=modelo, rotulos_y=meta.get("rotulos_y", {}),
                  tema_preset=meta.get("tema_preset"), tema_global=meta.get("tema_global", {}),
                  ajustes=meta.get("ajustes", {}), painel_cfg=meta.get("painel_cfg"),
                  painel_tema=meta.get("painel_tema", {}), excluir=excluir, multi_cfg=meta.get("multi_cfg"))
    config = dict(spec=spec, opcoes=op, separar=meta.get("separar"), respostas=meta.get("respostas", []))
    return df, meta.get("arquivo_dados"), config, estado
