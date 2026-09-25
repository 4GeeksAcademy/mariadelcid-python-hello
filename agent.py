from __future__ import annotations

import json
import csv
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
API_BASE_URL = os.getenv("INVENTORY_API_URL", "http://127.0.0.1:8000").rstrip("/")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
LOG_FILE = Path(__file__).resolve().parent / "conversation_log.csv"
LOG_FIELDS = ["actor", "message", "tool_call", "timestamp"]


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_inventory",
            "description": "Lista todos los productos y sus cantidades actuales.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_product",
            "description": "Añade un producto nuevo al inventario. quantity puede ser 0 si está agotado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del producto"},
                    "quantity": {"type": "integer", "minimum": 0, "description": "Cantidad inicial"},
                    "unit": {"type": "string", "description": "Unidad, por ejemplo kg, cajas o unidades"},
                },
                "required": ["name", "quantity", "unit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_stock",
            "description": "Actualiza el stock. Usa delta positivo para entregas y negativo para ventas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "minimum": 1},
                    "delta": {"type": "integer", "description": "Cambio de stock: positivo entrada, negativo salida"},
                },
                "required": ["product_id", "delta"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_alerts",
            "description": "Consulta productos con stock bajo y productos agotados.",
            "parameters": {
                "type": "object",
                "properties": {"threshold": {"type": "integer", "minimum": 1, "default": 5}},
                "additionalProperties": False,
            },
        },
    },
]


def log_event(actor: str, message: str, tool_call: str = "") -> None:
    """Añade un evento al CSV de conversación sin sobrescribir eventos anteriores."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with LOG_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=LOG_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow({
            "actor": actor,
            "message": message,
            "tool_call": tool_call,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })




def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = httpx.request(method, f"{API_BASE_URL}{path}", timeout=10, **kwargs)
        if response.is_error:
            return {"error": response.json().get("detail", response.text)}
        return response.json()
    except httpx.RequestError as exc:
        return {"error": f"No se pudo conectar con la API: {exc}"}


def list_inventory() -> Any:
    return _request("GET", "/inventory")


def add_product(name: str, quantity: int, unit: str) -> Any:
    return _request("POST", "/inventory", json={"name": name, "quantity": quantity, "unit": unit})


def update_stock(product_id: int, delta: int) -> Any:
    return _request("PATCH", f"/inventory/{product_id}", json={"delta": delta})


def get_stock_alerts(threshold: int = 5) -> Any:
    return _request("GET", "/inventory/alerts", params={"threshold": threshold})


TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "list_inventory": list_inventory,
    "add_product": add_product,
    "update_stock": update_stock,
    "get_stock_alerts": get_stock_alerts,
}

SYSTEM_PROMPT = (
    "Eres un asistente de inventario. Usa las tools para consultar o modificar datos reales. "
    "No inventes productos ni cantidades. Para entregas usa delta positivo y para ventas delta negativo. "
    "Distingue siempre stock bajo de agotado en tus respuestas. Si faltan datos, pregunta al usuario."
)


@dataclass
class Agent:
    client: Any
    history: list[dict[str, Any]]
    max_iterations: int = 8

    @classmethod
    def create(cls) -> "Agent":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Falta GROQ_API_KEY. Configúrala en .env para usar el agente con Groq.")
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        return cls(client=client, history=[{"role": "system", "content": SYSTEM_PROMPT}])

    def respond(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        log_event("user", user_message)
        for _ in range(self.max_iterations):
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL, messages=self.history, tools=TOOLS, tool_choice="auto"
            )
            message = completion.choices[0].message
            assistant_message: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            if message.tool_calls:
                assistant_message["tool_calls"] = [call.model_dump() for call in message.tool_calls]
            self.history.append(assistant_message)
            if not message.tool_calls:
                final_text = message.content or ""
                log_event("agent", final_text)
                return final_text
            for tool_call in message.tool_calls:
                log_event("agent", message.content or f"Solicitando tool {tool_call.function.name}", tool_call.function.name)
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    result = TOOL_FUNCTIONS[tool_call.function.name](**arguments)
                except (KeyError, TypeError, ValueError) as exc:
                    result = {"error": f"Llamada de tool inválida: {exc}"}
                result_text = json.dumps(result, ensure_ascii=False)
                self.history.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": result_text}
                )
                log_event("tool", result_text, tool_call.function.name)
        raise RuntimeError("El agente alcanzó el máximo de iteraciones sin respuesta final.")


def main() -> None:
    agent = Agent.create()
    print("Agente listo. Escribe 'salir' para terminar.")
    while True:
        try:
            user_message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_message.lower() in {"salir", "exit", "quit"}:
            break
        if user_message:
            print(agent.respond(user_message))


if __name__ == "__main__":
    main()
