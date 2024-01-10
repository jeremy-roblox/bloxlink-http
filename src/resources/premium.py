from resources.bloxlink import instance as bloxlink
import hikari
from attrs import define
from typing import Literal

from .constants import SKU_TIERS


@define(slots=True, kw_only=True)
class PremiumStatus:
    active: bool = False
    type: str = None
    payment_source: Literal["Discord Billing", "Bloxlink Dashboard"] = None
    payment_source_url: str = None
    tier: str = None
    term: str = None
    features: set = None

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
    def payment_name_url(self):
        return f"[{self.payment_source}]({self.payment_source_url})"


def get_user_facing_tier(tier_name):
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


def get_merged_features(premium_data, tier):
    features = {"premium"}

    if tier == "pro" or premium_data.get("patreon") or "pro" in tier:
        features.add("pro")

    return features


async def get_premium_status(
    *, guild_id: int | str = None, user_id: int | str = None, interaction: hikari.CommandInteraction=None
) -> PremiumStatus:
    if guild_id:
        premium_data = (await bloxlink.fetch_guild_data(str(guild_id), "premium")).premium

        if interaction:
            for entitlement in interaction.entitlements:
                if entitlement.id in SKU_TIERS:
                    tier, term = get_user_facing_tier(SKU_TIERS[entitlement.id])
                    features = get_merged_features(premium_data, SKU_TIERS[entitlement.id])

                    return PremiumStatus(
                        active=True,
                        type="guild",
                        payment_source="Discord Billing",
                        payment_source_url="https://support.discord.com/hc/en-us/articles/9359445233303-Premium-App-Subscriptions-FAQ",
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
                payment_source_url=f"https://blox.link/dashboard/guilds/{guild_id}/premium",
                tier=tier,
                term=term,
                features=features,
            )
    else:
        # user premium
        raise NotImplementedError()

    return PremiumStatus(active=False)
