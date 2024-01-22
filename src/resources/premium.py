from resources.bloxlink import instance as bloxlink
from resources.secrets import DISCORD_APPLICATION_ID
from resources.redis import redis
import hikari
from attrs import define
from typing import Literal

from .constants import SKU_TIERS


__all__ = ("PremiumStatus", "get_premium_status")


@define(slots=True, kw_only=True)
class PremiumStatus:
    """Represents the premium status of a guild or user."""

    active: bool = False
    type: Literal["guild", "user"] = None
    payment_source: Literal["Discord Billing", "Bloxlink Dashboard"] = None
    payment_source_url: str = None
    tier: str = None
    term: str = None
    features: set = None
    guild_id: int = None # Does this premium belong to a guild?
    user_id: int = None # Does this premium belong to a user?

    def __str__(self):
        buffer = []

        if self.features:
            if "premium" in self.features:
                buffer.append("Basic - Premium commands")
            if "pro" in self.features:
                buffer.append(
                    "Pro - Unlocks the Pro bot and a few [enterprise features](https://blox.link/pricing)"
                )

        return "\n".join(buffer) or "Not premium"

    @property
    def payment_name_url(self) -> str | None:
        """Returns a string with the payment source and a link to the payment source if the premium is active."""

        if self.active:
            return f"[{self.payment_source}]({self.payment_source_url})"

        return None

    @property
    def payment_source_url(self) -> str | None:
        """Returns a link to the payment source if the premium is active."""

        if self.active:
            return "https://support.discord.com/hc/en-us/articles/9359445233303-Premium-App-Subscriptions-FAQ" if self.payment_source == "Discord Billing" else f"https://blox.link/dashboard/guilds/{self.guild_id}/premium"

        return None

def get_user_facing_tier(tier_name) -> tuple[str, str]:
    """Returns a user-facing tier name and term."""

    user_facing_tier = None
    term = None

    try:
        tier, term = tier_name.split("/")

        if tier == "basic":
            user_facing_tier = "Basic Premium"
        elif tier == "pro":
            user_facing_tier = "Pro"

    except ValueError:
        user_facing_tier = tier_name

    return user_facing_tier, term


def get_merged_features(premium_data, tier) -> set[str]:
    """Returns a set of features that the user has access to."""

    features = {"premium"}

    if tier == "pro" or premium_data.get("patreon") or "pro" in tier:
        features.add("pro")

    return features


async def get_premium_status(
    *, guild_id: int | str = None, _user_id: int | str = None, interaction: hikari.CommandInteraction=None
) -> PremiumStatus:
    """Returns a PremiumStatus object dictating whether the guild has premium."""

    if guild_id:
        premium_data = (await bloxlink.fetch_guild_data(str(guild_id), "premium")).premium

        if interaction:
            for entitlement in interaction.entitlements:
                if entitlement.sku_id in SKU_TIERS:
                    tier, term = get_user_facing_tier(SKU_TIERS[entitlement.sku_id])
                    features = get_merged_features(premium_data, SKU_TIERS[entitlement.sku_id])

                    return PremiumStatus(
                        active=True,
                        type="guild",
                        payment_source="Discord Billing",
                        payment_source_url="https://support.discord.com/hc/en-us/articles/9359445233303-Premium-App-Subscriptions-FAQ",
                        guild_id=guild_id,
                        tier=tier,
                        term=term,
                        features=features,
                    )
        else:
            # check discord through REST
            redis_discord_billing_premium_key = f"premium:discord_billing:{guild_id}"
            redis_discord_billing_tier: bytes = await redis.get(redis_discord_billing_premium_key)
            has_discord_billing = redis_discord_billing_tier not in (None, "false")

            if not redis_discord_billing_tier:
                entitlements = await bloxlink.rest.fetch_entitlements(
                    DISCORD_APPLICATION_ID,
                    guild=str(guild_id),
                    exclude_ended=True
                )

                has_discord_billing = bool(entitlements)
                redis_discord_billing_tier = SKU_TIERS[entitlements[0].sku_id] if has_discord_billing else None

                await redis.set(redis_discord_billing_premium_key, redis_discord_billing_tier if has_discord_billing else "false", ex=100)

            if has_discord_billing:
                redis_discord_billing_tier = redis_discord_billing_tier.decode()
                tier, term = get_user_facing_tier(redis_discord_billing_tier)
                features = get_merged_features(premium_data, redis_discord_billing_tier)

                return PremiumStatus(
                    active=True,
                    type="guild",
                    payment_source="Discord Billing",
                    guild_id=guild_id,
                    tier=tier,
                    term=term,
                    features=features,
                )

        # hit database for premium
        if premium_data and premium_data.get("active") and not premium_data.get("externalDiscord"):
            tier, term = get_user_facing_tier(premium_data["type"])
            features = get_merged_features(premium_data, premium_data.get("type", "basic/month"))

            return PremiumStatus(
                active=True,
                type="guild",
                payment_source="Bloxlink Dashboard",
                guild_id=guild_id,
                tier=tier,
                term=term,
                features=features,
            )

    else:
        # user premium
        raise NotImplementedError()

    return PremiumStatus(active=False)
