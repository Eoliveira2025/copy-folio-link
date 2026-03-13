"""
Payment Gateway abstraction layer.

Each gateway implements the PaymentGateway protocol for:
- Creating invoices/charges
- Checking payment status
- Processing webhook payloads
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.services.payments")


class GatewayStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PaymentResult:
    gateway_id: str  # external payment/charge ID
    status: GatewayStatus
    amount: float
    raw_data: dict


class PaymentGateway(ABC):
    """Protocol for payment gateway implementations."""

    @abstractmethod
    async def create_charge(self, amount: float, currency: str, description: str, customer_email: str) -> PaymentResult:
        ...

    @abstractmethod
    async def check_status(self, gateway_id: str) -> PaymentResult:
        ...

    @abstractmethod
    async def process_webhook(self, payload: dict) -> PaymentResult:
        ...


# ── Stripe ─────────────────────────────────────────────────

class StripeGateway(PaymentGateway):
    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY
        self.base_url = "https://api.stripe.com/v1"

    async def create_charge(self, amount: float, currency: str, description: str, customer_email: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            # Create or find customer
            customer_resp = await client.post(
                f"{self.base_url}/customers",
                data={"email": customer_email},
                auth=(self.api_key, ""),
            )
            customer = customer_resp.json()

            # Create invoice
            invoice_resp = await client.post(
                f"{self.base_url}/invoices",
                data={
                    "customer": customer["id"],
                    "auto_advance": "true",
                    "collection_method": "send_invoice",
                    "days_until_due": 2,
                    "description": description,
                },
                auth=(self.api_key, ""),
            )
            invoice = invoice_resp.json()

            # Add invoice item
            await client.post(
                f"{self.base_url}/invoiceitems",
                data={
                    "customer": customer["id"],
                    "invoice": invoice["id"],
                    "amount": int(amount * 100),
                    "currency": currency.lower(),
                    "description": description,
                },
                auth=(self.api_key, ""),
            )

            # Finalize and send
            await client.post(f"{self.base_url}/invoices/{invoice['id']}/finalize", auth=(self.api_key, ""))
            await client.post(f"{self.base_url}/invoices/{invoice['id']}/send", auth=(self.api_key, ""))

            return PaymentResult(
                gateway_id=invoice["id"],
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=invoice,
            )

    async def check_status(self, gateway_id: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/invoices/{gateway_id}", auth=(self.api_key, ""))
            invoice = resp.json()
            status = GatewayStatus.PAID if invoice.get("paid") else GatewayStatus.PENDING
            return PaymentResult(
                gateway_id=gateway_id,
                status=status,
                amount=invoice.get("amount_due", 0) / 100,
                raw_data=invoice,
            )

    async def process_webhook(self, payload: dict) -> PaymentResult:
        event_type = payload.get("type", "")
        obj = payload.get("data", {}).get("object", {})
        if event_type == "invoice.paid":
            return PaymentResult(
                gateway_id=obj.get("id", ""),
                status=GatewayStatus.PAID,
                amount=obj.get("amount_paid", 0) / 100,
                raw_data=obj,
            )
        return PaymentResult(
            gateway_id=obj.get("id", ""),
            status=GatewayStatus.PENDING,
            amount=0,
            raw_data=obj,
        )


# ── ASAAS ──────────────────────────────────────────────────

class AsaasGateway(PaymentGateway):
    def __init__(self):
        self.api_key = settings.ASAAS_API_KEY
        self.base_url = "https://api.asaas.com/v3"

    def _headers(self):
        return {"access_token": self.api_key, "Content-Type": "application/json"}

    async def create_charge(self, amount: float, currency: str, description: str, customer_email: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            # Find or create customer
            search = await client.get(f"{self.base_url}/customers?email={customer_email}", headers=self._headers())
            customers = search.json().get("data", [])
            if customers:
                customer_id = customers[0]["id"]
            else:
                create = await client.post(
                    f"{self.base_url}/customers",
                    headers=self._headers(),
                    json={"name": customer_email, "email": customer_email},
                )
                customer_id = create.json()["id"]

            # Create payment
            from datetime import datetime, timedelta
            due_date = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
            resp = await client.post(
                f"{self.base_url}/payments",
                headers=self._headers(),
                json={
                    "customer": customer_id,
                    "billingType": "BOLETO",
                    "value": amount,
                    "dueDate": due_date,
                    "description": description,
                },
            )
            payment = resp.json()
            return PaymentResult(
                gateway_id=payment.get("id", ""),
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=payment,
            )

    async def check_status(self, gateway_id: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/payments/{gateway_id}", headers=self._headers())
            payment = resp.json()
            status_map = {"CONFIRMED": GatewayStatus.PAID, "RECEIVED": GatewayStatus.PAID}
            status = status_map.get(payment.get("status", ""), GatewayStatus.PENDING)
            return PaymentResult(
                gateway_id=gateway_id, status=status, amount=payment.get("value", 0), raw_data=payment,
            )

    async def process_webhook(self, payload: dict) -> PaymentResult:
        event = payload.get("event", "")
        payment = payload.get("payment", {})
        status = GatewayStatus.PAID if event == "PAYMENT_CONFIRMED" else GatewayStatus.PENDING
        return PaymentResult(
            gateway_id=payment.get("id", ""),
            status=status,
            amount=payment.get("value", 0),
            raw_data=payment,
        )


# ── Mercado Pago ───────────────────────────────────────────

class MercadoPagoGateway(PaymentGateway):
    def __init__(self):
        self.access_token = settings.MERCADOPAGO_ACCESS_TOKEN
        self.base_url = "https://api.mercadopago.com"

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def create_charge(self, amount: float, currency: str, description: str, customer_email: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/payments",
                headers=self._headers(),
                json={
                    "transaction_amount": amount,
                    "description": description,
                    "payment_method_id": "pix",
                    "payer": {"email": customer_email},
                },
            )
            payment = resp.json()
            return PaymentResult(
                gateway_id=str(payment.get("id", "")),
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=payment,
            )

    async def check_status(self, gateway_id: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/v1/payments/{gateway_id}", headers=self._headers())
            payment = resp.json()
            status = GatewayStatus.PAID if payment.get("status") == "approved" else GatewayStatus.PENDING
            return PaymentResult(
                gateway_id=gateway_id,
                status=status,
                amount=payment.get("transaction_amount", 0),
                raw_data=payment,
            )

    async def process_webhook(self, payload: dict) -> PaymentResult:
        action = payload.get("action", "")
        data = payload.get("data", {})
        payment_id = str(data.get("id", ""))
        if action == "payment.updated" and payment_id:
            return await self.check_status(payment_id)
        return PaymentResult(gateway_id=payment_id, status=GatewayStatus.PENDING, amount=0, raw_data=payload)


# ── Celcoin ────────────────────────────────────────────────

class CelcoinGateway(PaymentGateway):
    def __init__(self):
        self.client_id = settings.CELCOIN_CLIENT_ID
        self.client_secret = settings.CELCOIN_CLIENT_SECRET
        self.base_url = "https://api.celcoin.com.br"
        self._token: Optional[str] = None

    async def _authenticate(self) -> str:
        if self._token:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v5/token",
                data={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"},
            )
            self._token = resp.json().get("access_token", "")
            return self._token

    def _headers(self, token: str):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def create_charge(self, amount: float, currency: str, description: str, customer_email: str) -> PaymentResult:
        token = await self._authenticate()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v5/transactions/billpayments/pix",
                headers=self._headers(token),
                json={"amount": amount, "description": description, "payer": {"email": customer_email}},
            )
            data = resp.json()
            return PaymentResult(
                gateway_id=str(data.get("transactionId", "")),
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=data,
            )

    async def check_status(self, gateway_id: str) -> PaymentResult:
        token = await self._authenticate()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/v5/transactions/{gateway_id}",
                headers=self._headers(token),
            )
            data = resp.json()
            status = GatewayStatus.PAID if data.get("status") in ("CONFIRMED", "COMPLETED") else GatewayStatus.PENDING
            return PaymentResult(gateway_id=gateway_id, status=status, amount=data.get("amount", 0), raw_data=data)

    async def process_webhook(self, payload: dict) -> PaymentResult:
        tx_id = str(payload.get("transactionId", ""))
        status = GatewayStatus.PAID if payload.get("status") in ("CONFIRMED", "COMPLETED") else GatewayStatus.PENDING
        return PaymentResult(
            gateway_id=tx_id, status=status, amount=payload.get("amount", 0), raw_data=payload,
        )


# ── Factory ────────────────────────────────────────────────

def get_gateway(provider: str) -> PaymentGateway:
    gateways = {
        "stripe": StripeGateway,
        "asaas": AsaasGateway,
        "mercadopago": MercadoPagoGateway,
        "celcoin": CelcoinGateway,
    }
    cls = gateways.get(provider.lower())
    if not cls:
        raise ValueError(f"Unknown payment provider: {provider}")
    return cls()
