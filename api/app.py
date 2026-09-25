from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, status
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = BASE_DIR / "products.csv"
DEFAULT_LOW_STOCK_THRESHOLD = 5

app = FastAPI(title="Inventory API", version="0.1.0")


class ProductCreate(BaseModel):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    unit: str = Field(min_length=1)


class StockUpdate(BaseModel):
    delta: int


class Product(BaseModel):
    id: int
    name: str
    quantity: int
    unit: str


class AlertsResponse(BaseModel):
    threshold: int
    low_stock: list[Product]
    out_of_stock: list[Product]


def _ensure_products_file() -> None:
    if not PRODUCTS_FILE.exists():
        PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PRODUCTS_FILE.open("w", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=["id", "name", "quantity", "unit"]).writeheader()


def _read_products() -> list[Product]:
    _ensure_products_file()
    try:
        with PRODUCTS_FILE.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            required = {"id", "name", "quantity", "unit"}
            if reader.fieldnames is None or set(reader.fieldnames) != required:
                raise ValueError("products.csv no tiene las columnas esperadas")
            products = []
            for row in reader:
                products.append(
                    Product(
                        id=int(row["id"]),
                        name=row["name"],
                        quantity=int(row["quantity"]),
                        unit=row["unit"],
                    )
                )
            return products
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo leer products.csv: {exc}") from exc


def _write_products(products: list[Product]) -> None:
    fieldnames = ["id", "name", "quantity", "unit"]
    try:
        PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=PRODUCTS_FILE.parent, delete=False
        ) as temporary:
            writer = csv.DictWriter(temporary, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(product.model_dump() for product in products)
            temporary_name = temporary.name
        os.replace(temporary_name, PRODUCTS_FILE)
    except OSError as exc:
        if "temporary_name" in locals():
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"No se pudo escribir products.csv: {exc}") from exc


@app.get("/inventory", response_model=list[Product])
def list_inventory() -> list[Product]:
    return _read_products()


@app.post("/inventory", response_model=Product, status_code=status.HTTP_201_CREATED)
def add_product(product_data: ProductCreate) -> Product:
    products = _read_products()
    product = Product(
        id=max((item.id for item in products), default=0) + 1,
        name=product_data.name.strip(),
        quantity=product_data.quantity,
        unit=product_data.unit.strip(),
    )
    if not product.name or not product.unit:
        raise HTTPException(status_code=422, detail="name y unit no pueden estar vacíos")
    products.append(product)
    _write_products(products)
    return product


@app.patch("/inventory/{product_id}", response_model=Product)
def update_stock(
    product_id: Annotated[int, PathParam(ge=1)], update: StockUpdate
) -> Product:
    products = _read_products()
    product = next((item for item in products if item.id == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail=f"No existe el producto con id {product_id}")
    new_quantity = product.quantity + update.delta
    if new_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail=f"La operación dejaría el stock negativo ({new_quantity})",
        )
    updated = Product(
        id=product.id, name=product.name, quantity=new_quantity, unit=product.unit
    )
    products[products.index(product)] = updated
    _write_products(products)
    return updated


@app.get("/inventory/alerts", response_model=AlertsResponse)
def inventory_alerts(
    threshold: Annotated[int, Query(ge=1)] = DEFAULT_LOW_STOCK_THRESHOLD,
) -> AlertsResponse:
    products = _read_products()
    return AlertsResponse(
        threshold=threshold,
        low_stock=[product for product in products if 0 < product.quantity <= threshold],
        out_of_stock=[product for product in products if product.quantity == 0],
    )
