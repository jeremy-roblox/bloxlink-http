from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
import hikari


@bloxlink.command(
    category="Miscellaneous",
    developer_only=True,
    defer=True,
    defer_with_ephemeral=True,
)
class RolesCleanupCommand(GenericCommand):
    """clean up any roles without a color"""

    async def __main__(self, ctx: CommandContext):
        guild_id = ctx.guild_id

        roles = await bloxlink.fetch_roles(guild_id)

        for role in roles.values():
            if str(role.color) == "#000000" and not role.is_managed and role.name != "@everyone":
                try:
                    await bloxlink.rest.delete_role(guild_id, role.id)
                except hikari.ForbiddenError:
                    pass

        await ctx.response.send("Roles cleaned up.")
