from resources.bloxlink import instance as bloxlink

from .constants import SKU_TIERS
from .models import GuildData, PremiumModel


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
    *, guild_id: int | str = None, user_id: int | str = None, interaction=None
) -> PremiumModel:
    if guild_id:
        premium_data = (await bloxlink.fetch_guild_data(str(guild_id), "premium")).premium

        if interaction:
            guild_skus = getattr(interaction, "entitlement_sku_ids", [])

            for sku_id, sku_tier in SKU_TIERS.items():
                if sku_id in guild_skus:
                    tier, term = get_user_facing_tier(sku_tier)
                    features = get_merged_features(premium_data, sku_tier)

                    return PremiumModel(
                        active=True,
                        type="guild",
                        payment_source="Discord Billing",
                        tier=tier,
                        term=term,
                        features=features,
                    )

        # hit database for premium
        if premium_data and premium_data.get("active") and not premium_data.get("externalDiscord"):
            tier, term = get_user_facing_tier(premium_data["type"])
            features = get_merged_features(premium_data, premium_data.get("type", "basic/month"))

            return PremiumModel(
                active=True,
                type="guild",
                payment_source=f"[Bloxlink Dashboard](https://blox.link/dashboard/guilds/{guild_id})/premium",
                tier=tier,
                term=term,
                features=features,
            )
    else:
        raise NotImplementedError()

    return PremiumModel(active=False)
