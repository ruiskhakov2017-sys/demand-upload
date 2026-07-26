from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx


class BrocardError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrocardSnapshotData:
    balance: float
    currency: str
    cards_total: int
    cards_active: int
    provider_payload: dict


class BrocardClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self) -> BrocardClient:
        return self

    def __exit__(self, *_args) -> None:
        self._client.close()

    def fetch_snapshot(self) -> BrocardSnapshotData:
        accounts, account_request_ids = self._list_all(
            "/api/v2/accounts",
            {"scope": "company"},
        )
        cards, card_request_ids = self._list_all(
            "/api/v2/cards",
            {"archived": "include"},
        )

        balances: dict[str, Decimal] = defaultdict(Decimal)
        available: dict[str, Decimal] = defaultdict(Decimal)
        for account in accounts:
            currency = str(account.get("currency") or "USD").upper()
            balances[currency] += _decimal(account.get("balance"))
            available[currency] += _decimal(account.get("available"))
        if len(balances) > 1:
            currencies = ", ".join(sorted(balances))
            raise BrocardError(f"Brocard вернул счета в нескольких валютах: {currencies}")

        currency = next(iter(balances), "USD")
        state_counts: Counter[str] = Counter()
        cards_active = 0
        for card in cards:
            state = card.get("state") if isinstance(card.get("state"), dict) else {}
            state_label = str(state.get("label") or "UNKNOWN").upper()
            state_counts[state_label] += 1
            if not card.get("archived") and state_label in {"ACTIVE", "ACTIVATED"}:
                cards_active += 1

        return BrocardSnapshotData(
            balance=float(balances.get(currency, Decimal(0))),
            currency=currency,
            cards_total=len(cards),
            cards_active=cards_active,
            provider_payload={
                "accounts_total": len(accounts),
                "available": str(available.get(currency, Decimal(0))),
                "card_states": dict(state_counts),
                "request_ids": account_request_ids + card_request_ids,
            },
        )

    def _list_all(self, path: str, params: dict[str, str]) -> tuple[list[dict], list[str]]:
        rows: list[dict] = []
        request_ids: list[str] = []
        page = 1
        while True:
            response = self._client.get(path, params={**params, "page": page, "per_page": 1000})
            payload = _response_payload(response)
            data = payload.get("data")
            if not isinstance(data, list):
                raise BrocardError("Brocard API вернул ответ без списка data")
            rows.extend(item for item in data if isinstance(item, dict))
            if payload.get("request_id"):
                request_ids.append(str(payload["request_id"]))
            try:
                last_page = int(payload.get("last_page") or 1)
            except (TypeError, ValueError) as exc:
                raise BrocardError("Brocard API вернул некорректную пагинацию") from exc
            if page >= last_page:
                return rows, request_ids
            if page >= 1000:
                raise BrocardError("Brocard API вернул слишком много страниц")
            page += 1


def _response_payload(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrocardError(f"Brocard API вернул не-JSON ответ ({response.status_code})") from exc
    if not response.is_success:
        message = payload.get("message") if isinstance(payload, dict) else None
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        suffix = f"; request ID: {request_id}" if request_id else ""
        raise BrocardError(f"Brocard API: {message or response.status_code}{suffix}")
    if not isinstance(payload, dict):
        raise BrocardError("Brocard API вернул некорректный JSON")
    return payload


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except InvalidOperation as exc:
        raise BrocardError(f"Brocard API вернул некорректную сумму: {value}") from exc
