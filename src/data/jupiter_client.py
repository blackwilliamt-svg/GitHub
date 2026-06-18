from __future__ import annotations
import httpx
import logging
from typing import Optional

from .models import TokenInfo

logger = logging.getLogger(__name__)

JUPITER_PRICE_V2 = "https://api.jup.ag/price/v2"
JUPITER_TOKENS = "https://tokens.jup.ag/tokens?tags=verified"
JUPITER_TOKEN_STRICT = "https://tokens.jup.ag/token/{mint}"
JUPITER_QUOTE = "https://api.jup.ag/swap/v1/quote"


class JupiterClient:
    """Client for Jupiter DEX APIs — token metadata, live prices, and quote routing."""

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(timeout=timeout)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_token_list(self) -> list[TokenInfo]:
        resp = self._client.get(JUPITER_TOKENS)
        resp.raise_for_status()
        tokens = []
        for t in resp.json():
            tokens.append(
                TokenInfo(
                    address=t["address"],
                    symbol=t.get("symbol", ""),
                    name=t.get("name", ""),
                    decimals=t.get("decimals", 9),
                    logo_uri=t.get("logoURI", ""),
                    tags=t.get("tags", []),
                    daily_volume=t.get("daily_volume", 0.0) or 0.0,
                )
            )
        logger.info("Fetched %d verified tokens from Jupiter", len(tokens))
        return tokens

    def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        resp = self._client.get(JUPITER_TOKEN_STRICT.format(mint=mint))
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        t = resp.json()
        return TokenInfo(
            address=t["address"],
            symbol=t.get("symbol", ""),
            name=t.get("name", ""),
            decimals=t.get("decimals", 9),
            logo_uri=t.get("logoURI", ""),
            tags=t.get("tags", []),
            daily_volume=t.get("daily_volume", 0.0) or 0.0,
        )

    def get_prices(self, mint_addresses: list[str]) -> dict[str, float]:
        if not mint_addresses:
            return {}
        ids_param = ",".join(mint_addresses)
        resp = self._client.get(JUPITER_PRICE_V2, params={"ids": ids_param})
        resp.raise_for_status()
        data = resp.json().get("data", {})
        prices = {}
        for mint, info in data.items():
            price = info.get("price")
            if price is not None:
                prices[mint] = float(price)
        return prices

    def get_price(self, mint: str) -> Optional[float]:
        prices = self.get_prices([mint])
        return prices.get(mint)

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> Optional[dict]:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
        }
        resp = self._client.get(JUPITER_QUOTE, params=params)
        if resp.status_code != 200:
            logger.warning("Quote failed: %s", resp.text)
            return None
        return resp.json()

    def resolve_symbol_to_mint(self, symbol: str, token_list: list[TokenInfo] | None = None) -> Optional[str]:
        if token_list is None:
            token_list = self.get_token_list()
        symbol_upper = symbol.upper()
        for t in token_list:
            if t.symbol.upper() == symbol_upper:
                return t.address
        return None
