import csv

from fastapi.testclient import TestClient

from api import app as app_module


def client_with_temp_csv(tmp_path, monkeypatch):
    products_file = tmp_path / "products.csv"
    products_file.write_text("id,name,quantity,unit\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "PRODUCTS_FILE", products_file)
    return TestClient(app_module.app), products_file


def test_inventory_crud_and_zero_quantity(tmp_path, monkeypatch):
    client, products_file = client_with_temp_csv(tmp_path, monkeypatch)
    assert client.get("/inventory").json() == []
    response = client.post("/inventory", json={"name": "Leche", "quantity": 0, "unit": "cajas"})
    assert response.status_code == 201
    product = response.json()
    assert product["quantity"] == 0
    assert client.patch(f"/inventory/{product['id']}", json={"delta": 5}).json()["quantity"] == 5
    assert client.patch(f"/inventory/{product['id']}", json={"delta": -2}).json()["quantity"] == 3
    assert products_file.read_text(encoding="utf-8").count("Leche") == 1


def test_alerts_distinguish_low_and_out_of_stock(tmp_path, monkeypatch):
    client, _ = client_with_temp_csv(tmp_path, monkeypatch)
    client.post("/inventory", json={"name": "Arroz", "quantity": 5, "unit": "kg"})
    client.post("/inventory", json={"name": "Lentejas", "quantity": 6, "unit": "kg"})
    client.post("/inventory", json={"name": "Tomate", "quantity": 0, "unit": "latas"})
    alerts = client.get("/inventory/alerts").json()
    assert alerts["threshold"] == 5
    assert [item["name"] for item in alerts["low_stock"]] == ["Arroz"]
    assert [item["name"] for item in alerts["out_of_stock"]] == ["Tomate"]


def test_validation_and_errors(tmp_path, monkeypatch):
    client, _ = client_with_temp_csv(tmp_path, monkeypatch)
    assert client.post("/inventory", json={"name": "Error", "quantity": -1, "unit": "u"}).status_code == 422
    assert client.patch("/inventory/999", json={"delta": 1}).status_code == 404
    product = client.post("/inventory", json={"name": "Pan", "quantity": 1, "unit": "u"}).json()
    assert client.patch(f"/inventory/{product['id']}", json={"delta": -2}).status_code == 400
    assert client.get("/inventory/alerts?threshold=0").status_code == 422
