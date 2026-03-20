"""
Payment Gateway abstraction layer.

Each gateway implements the PaymentGateway protocol for:
- Creating invoices/charges (with billing type selection)
- Generating checkout URLs for user payment
- Checking payment status
- Processing webhook payloads
- Refunding payments
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    REFUNDED = "refunded"


class BillingType(str, Enum):
    BOLETO = "BOLETO"
    PIX = "PIX"
    CREDIT_CARD = "CREDIT_CARD"
    UNDEFINED = "UNDEFINED"  # Let gateway decide / show all options


@dataclass
class PaymentResult:
    gateway_id: str  # external payment/charge ID
    status: GatewayStatus
    amount: float
    raw_data: dict
    checkout_url: Optional[str] = None  # URL for user to complete payment
    pix_qr_code: Optional[str] = None  # PIX QR code (base64 image)
    pix_copy_paste: Optional[str] = None  # PIX copy-paste code
    boleto_url: Optional[str] = None  # Boleto PDF URL
    invoice_url: Optional[str] = None  # General invoice/payment URL


class PaymentGateway(ABC):
    """Protocol for payment gateway implementations."""

    @abstractmethod
    async def create_charge(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        customer_cpf: Optional[str] = None,
        billing_type: BillingType = BillingType.UNDEFINED,
    ) -> PaymentResult:
        ...

    @abstractmethod
    async def check_status(self, gateway_id: str) -> PaymentResult:
        ...

    @abstractmethod
    async def process_webhook(self, payload: dict) -> PaymentResult:
        ...

    async def refund(self, gateway_id: str, amount: Optional[float] = None) -> PaymentResult:
        raise NotImplementedError("Refund not supported by this gateway")


# ── ASAAS ──────────────────────────────────────────────────

class AsaasGateway(PaymentGateway):
    def __init__(self):
        self.api_key = settings.ASAAS_API_KEY
        self.timeout = getattr(settings, "ASAAS_TIMEOUT_SECONDS", 30)
        self.due_days = getattr(settings, "ASAAS_BILLING_DUE_DAYS", 1)

        # Resolve base URL: explicit override > sandbox flag > environment string
        explicit_url = getattr(settings, "ASAAS_BASE_URL", "")
        if explicit_url:
            self.base_url = explicit_url.rstrip("/")
        elif getattr(settings, "ASAAS_SANDBOX", True):
            self.base_url = "https://sandbox.asaas.com/api/v3"
        else:
            env = getattr(settings, "ASAAS_ENVIRONMENT", "sandbox")
            self.base_url = (
                "https://api.asaas.com/v3" if env == "production"
                else "https://sandbox.asaas.com/api/v3"
            )

    def _headers(self):
        return {"access_token": self.api_key, "Content-Type": "application/json"}

    async def _find_or_create_customer(
        self, client: httpx.AsyncClient, email: str, name: Optional[str] = None, cpf: Optional[str] = None
    ) -> str:
        """Find existing Asaas customer by email or create a new one."""
        search = await client.get(f"{self.base_url}/customers?email={email}", headers=self._headers())
        search.raise_for_status()
        customers = search.json().get("data", [])
        if customers:
            return customers[0]["id"]

        payload = {"name": name or email.split("@")[0], "email": email}
        if cpf:
            payload["cpfCnpj"] = cpf

        create = await client.post(f"{self.base_url}/customers", headers=self._headers(), json=payload)
        create.raise_for_status()
        return create.json()["id"]

    async def create_charge(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        customer_cpf: Optional[str] = None,
        billing_type: BillingType = BillingType.UNDEFINED,
        external_reference: Optional[str] = None,
        due_date_override: Optional[str] = None,  # "YYYY-MM-DD"
    ) -> PaymentResult:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            customer_id = await self._find_or_create_customer(
                client, customer_email, customer_name, customer_cpf
            )

            from datetime import datetime, timedelta
            due_date = due_date_override or (
                datetime.utcnow() + timedelta(days=self.due_days)
            ).strftime("%Y-%m-%d")

            asaas_billing = billing_type.value if billing_type != BillingType.UNDEFINED else "UNDEFINED"

            payment_payload = {
                "customer": customer_id,
                "billingType": asaas_billing,
                "value": amount,
                "dueDate": due_date,
                "description": description,
            }
            if external_reference:
                payment_payload["externalReference"] = external_reference

            resp = await client.post(
                f"{self.base_url}/payments", headers=self._headers(), json=payment_payload
            )
            resp.raise_for_status()
            payment = resp.json()

            result = PaymentResult(
                gateway_id=payment.get("id", ""),
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=payment,
                invoice_url=payment.get("invoiceUrl"),
                checkout_url=payment.get("invoiceUrl"),
            )

            # If PIX, fetch QR code
            if billing_type == BillingType.PIX and payment.get("id"):
                try:
                    pix_resp = await client.get(
                        f"{self.base_url}/payments/{payment['id']}/pixQrCode",
                        headers=self._headers(),
                    )
                    if pix_resp.status_code == 200:
                        pix_data = pix_resp.json()
                        result.pix_qr_code = pix_data.get("encodedImage")
                        result.pix_copy_paste = pix_data.get("payload")
                except Exception as e:
                    logger.warning(f"Failed to fetch PIX QR code: {e}")

            # If BOLETO, the invoiceUrl already contains the boleto
            if billing_type == BillingType.BOLETO:
                result.boleto_url = payment.get("bankSlipUrl") or payment.get("invoiceUrl")

            return result

    async def check_status(self, gateway_id: str) -> PaymentResult:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.base_url}/payments/{gateway_id}", headers=self._headers())
            resp.raise_for_status()
            payment = resp.json()

            status_map = {
                "CONFIRMED": GatewayStatus.PAID,
                "RECEIVED": GatewayStatus.PAID,
                "RECEIVED_IN_CASH": GatewayStatus.PAID,
                "REFUNDED": GatewayStatus.REFUNDED,
                "REFUND_REQUESTED": GatewayStatus.REFUNDED,
                "OVERDUE": GatewayStatus.PENDING,
            }
            status = status_map.get(payment.get("status", ""), GatewayStatus.PENDING)

            return PaymentResult(
                gateway_id=gateway_id,
                status=status,
                amount=payment.get("value", 0),
                raw_data=payment,
                invoice_url=payment.get("invoiceUrl"),
            )

    async def process_webhook(self, payload: dict) -> PaymentResult:
        event = payload.get("event", "")
        payment = payload.get("payment", {})

        event_status_map = {
            "PAYMENT_CONFIRMED": GatewayStatus.PAID,
            "PAYMENT_RECEIVED": GatewayStatus.PAID,
            "PAYMENT_OVERDUE": GatewayStatus.PENDING,
            "PAYMENT_REFUNDED": GatewayStatus.REFUNDED,
            "PAYMENT_DELETED": GatewayStatus.CANCELLED,
        }
        status = event_status_map.get(event, GatewayStatus.PENDING)

        return PaymentResult(
            gateway_id=payment.get("id", ""),
            status=status,
            amount=payment.get("value", 0),
            raw_data=payment,
        )

    async def refund(self, gateway_id: str, amount: Optional[float] = None) -> PaymentResult:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {}
            if amount:
                payload["value"] = amount

            resp = await client.post(
                f"{self.base_url}/payments/{gateway_id}/refund",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            return PaymentResult(
                gateway_id=gateway_id,
                status=GatewayStatus.REFUNDED,
                amount=amount or data.get("value", 0),
                raw_data=data,
            )


# ── Stripe ─────────────────────────────────────────────────

class StripeGateway(PaymentGateway):
    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY
        self.base_url = "https://api.stripe.com/v1"

    async def create_charge(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        customer_cpf: Optional[str] = None,
        billing_type: BillingType = BillingType.UNDEFINED,
    ) -> PaymentResult:
        async with httpx.AsyncClient(timeout=30) as client:
            customer_resp = await client.post(
                f"{self.base_url}/customers",
                data={"email": customer_email, "name": customer_name or ""},
                auth=(self.api_key, ""),
            )
            customer = customer_resp.json()

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

            await client.post(f"{self.base_url}/invoices/{invoice['id']}/finalize", auth=(self.api_key, ""))
            await client.post(f"{self.base_url}/invoices/{invoice['id']}/send", auth=(self.api_key, ""))

            return PaymentResult(
                gateway_id=invoice["id"],
                status=GatewayStatus.PENDING,
                amount=amount,
                raw_data=invoice,
                checkout_url=invoice.get("hosted_invoice_url"),
            )

    async def check_status(self, gateway_id: str) -> PaymentResult:
        async with httpx.AsyncClient(timeout=15) as client:
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


# ── Mercado Pago ───────────────────────────────────────────

class MercadoPagoGateway(PaymentGateway):
    def __init__(self):
        self.access_token = settings.MERCADOPAGO_ACCESS_TOKEN
        self.base_url = "https://api.mercadopago.com"

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def create_charge(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        customer_cpf: Optional[str] = None,
        billing_type: BillingType = BillingType.UNDEFINED,
    ) -> PaymentResult:
        async with httpx.AsyncClient(timeout=30) as client:
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
        async with httpx.AsyncClient(timeout=15) as client:
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

    async def create_charge(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        customer_cpf: Optional[str] = None,
        billing_type: BillingType = BillingType.UNDEFINED,
    ) -> PaymentResult:
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
