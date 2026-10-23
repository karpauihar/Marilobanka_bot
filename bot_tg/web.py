import logging

from flask import Flask, Response, request

from config import Settings, load_settings
from database import Database
from payments import parse_amount, verify_result_signature

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
) -> Flask:
    settings = settings or load_settings()
    database = database or Database(settings.database_path)
    database.init_schema()
    app = Flask(__name__)
    prefix = settings.url_prefix

    @app.route(f"{prefix}/robokassa/result", methods=["GET", "POST"])
    def robokassa_result() -> Response:
        if not settings.payment_configured:
            return Response(
                "payment is not configured", status=503, mimetype="text/plain"
            )
        out_sum = request.values.get("OutSum", "").strip()
        inv_id_raw = request.values.get("InvId", "").strip()
        signature = request.values.get("SignatureValue", "").strip()
        if not out_sum or not inv_id_raw or not signature:
            return Response("bad request", status=400, mimetype="text/plain")
        if not verify_result_signature(
            out_sum, inv_id_raw, signature, settings.password_2
        ):
            log.warning("Robokassa signature rejected inv_id=%s", inv_id_raw)
            return Response("bad sign", status=400, mimetype="text/plain")
        try:
            inv_id = int(inv_id_raw)
            amount = parse_amount(out_sum)
        except ValueError:
            return Response("bad request", status=400, mimetype="text/plain")
        result = database.mark_order_paid(inv_id, amount)
        if result == "not_found":
            return Response("order not found", status=404, mimetype="text/plain")
        if result == "amount_mismatch":
            return Response("amount mismatch", status=400, mimetype="text/plain")
        return Response(f"OK{inv_id}", status=200, mimetype="text/plain")

    @app.get(f"{prefix}/payment/success")
    @app.get(f"{prefix}/robokassa/success")
    def payment_success() -> str:
        return (
            "<h1>Оплата прошла успешно</h1>"
            "<p>Вернитесь в Telegram — бот подготовит доступ в закрытый канал.</p>"
        )

    @app.get(f"{prefix}/payment/fail")
    @app.get(f"{prefix}/robokassa/fail")
    def payment_fail() -> str:
        return (
            "<h1>Оплата не завершена</h1>"
            "<p>Вернитесь в Telegram и попробуйте снова.</p>"
        )

    @app.get(f"{prefix}/health")
    def health() -> dict[str, bool | str]:
        return {
            "status": "ok",
            "payments_configured": settings.payment_configured,
            "channel_configured": settings.channel_configured,
            "fiscalization_configured": settings.fiscalization_configured,
            "robokassa_test": settings.robokassa_test,
        }

    return app
