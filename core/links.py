# =====================================================
# core/links.py — Links de atleta firmados con HMAC
# Requiere en .streamlit/secrets.toml:  LINK_SECRET = "una-cadena-larga-y-aleatoria"
# =====================================================
import hmac
import hashlib
import base64
import urllib.parse

import streamlit as st


def _secreto() -> bytes:
    try:
        return str(st.secrets["LINK_SECRET"]).encode()
    except Exception:
        raise RuntimeError("Falta LINK_SECRET en st.secrets (secrets.toml).")


def firmar_link(entrenador: str, atleta: str) -> str:
    msg = f"{entrenador}|{atleta}".encode()
    sig = hmac.new(_secreto(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()[:32]


def verificar_link(entrenador: str, atleta: str, sig: str) -> bool:
    if not sig:
        return False
    return hmac.compare_digest(firmar_link(entrenador, atleta), sig)


def construir_link(base: str, entrenador: str, atleta: str) -> str:
    q = urllib.parse.urlencode({
        "entrenador": entrenador,
        "atleta": atleta,
        "sig": firmar_link(entrenador, atleta),
    })
    return f"{base.rstrip('/')}/?{q}"
