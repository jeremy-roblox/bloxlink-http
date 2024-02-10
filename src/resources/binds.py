from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Unpack

from datetime import timedelta
import hikari
from bloxlink_lib import MemberSerializable, GuildSerializable, fetch_typed, StatusCodes, GuildBind, GuildData, get_binds, BaseModel, create_entity, count_binds, VALID_BIND_TYPES, BindCriteriaDict
from bloxlink_lib.database import fetch_user_data, update_user_data, update_guild_data
from pydantic import Field

from resources import restriction
from resources.api.roblox import users
from resources.bloxlink import instance as bloxlink
from resources.constants import GROUP_RANK_CRITERIA_TEXT, REPLY_CONT, REPLY_EMOTE, LIMITS, ORANGE_COLOR
from resources.exceptions import BloxlinkException, Message, RobloxAPIError, RobloxNotFound, BindConflictError, BindException, PremiumRequired, BloxlinkForbidden
from resources.ui.embeds import InteractiveMessage
from resources.premium import get_premium_status
from resources.ui.components import Button
from config import CONFIG

if TYPE_CHECKING:
    from resources.response import Response


logger = logging.getLogger()


# Set to True to remove the old bind fields from the database (groupIDs and roleBinds)
POP_OLD_BINDS: bool = False



class UpdateEndpointResponse(BaseModel):
    """The payload that is sent from the bind API when updating a user's roles and nickname."""

    nickname: str | None

    add_roles: list[int] = Field(alias="addRoles")
    remove_roles: list[int] = Field(alias="removeRoles")
    missing_roles: list[int] = Field(alias="missingRoles")


def convert_v3_binds_to_v4(items: dict, bind_type: ValidBindType) -> list:
    """Convert old bindings to the new bind format.

    Args:
        items (dict): The bindings to convert.
        bind_type (ValidBindType): Type of bind that is being made.

    Returns:
        list: The binds in the new format.
    """
    output = []

    for bind_id, data in items.items():
        group_rank_binding = data.get("binds") or data.get("ranges")

        if bind_type != "group" or not group_rank_binding:
            bind_data = {
                "roles": data.get("roles"),
                "removeRoles": data.get("removeRoles"),
                "nickname": data.get("nickname"),
                "bind": {"type": bind_type, "id": int(bind_id)},
            }
            output.append(bind_data)
            continue

        # group rank bindings
        if data.get("binds"):
            for rank_id, sub_data in data["binds"].items():
                bind_data = {}

                bind_data["bind"] = {"type": bind_type, "id": int(bind_id)}
                bind_data["roles"] = sub_data.get("roles")
                bind_data["nickname"] = sub_data.get("nickname")
                bind_data["removeRoles"] = sub_data.get("removeRoles")

                # Convert to an int if possible beforehand.
                try:
                    rank_id = int(rank_id)
                except ValueError:
                    pass

                if rank_id == "all":
                    bind_data["bind"]["everyone"] = True
                elif rank_id == 0:
                    bind_data["bind"]["guest"] = True
                elif rank_id < 0:
                    bind_data["bind"]["min"] = abs(rank_id)
                else:
                    bind_data["bind"]["roleset"] = rank_id

                output.append(bind_data)

        # group rank ranges
        if data.get("ranges"):
            for range_item in data["ranges"]:
                bind_data = {}

                bind_data["bind"] = {"type": bind_type, "id": int(bind_id)}
                bind_data["roles"] = range_item.get("roles")
                bind_data["nickname"] = range_item.get("nickname")
                bind_data["removeRoles"] = range_item.get("removeRoles")

                bind_data["bind"]["min"] = int(range_item.get("low"))
                bind_data["bind"]["max"] = int(range_item.get("high"))

                output.append(bind_data)

    return output


async def convert_v4_binds_to_v3(items: list) -> dict:
    """Convert binds of the new format to the old bind format.

    This does not include the names of groups/other bind types.

    GuildBind and GroupBind types are supported, along with the dict representation.

    Args:
        items (list): The list of new bindings to convert.

    Returns:
        dict: Bindings in their old format.
    """
    role_binds = {
        "gamePasses": defaultdict(dict),
        "assets": defaultdict(dict),
        "badges": defaultdict(dict),
        "groups": defaultdict(dict),
    }
    entire_groups = {}

    for bind in items:
        if isinstance(bind, GuildBind):
            bind = asdict(bind)

        sub_data = bind["bind"]
        bind_type = sub_data["type"]
        bind_id = str(sub_data["id"])

        bind_entity = create_entity(bind_type, bind_id)
        try:
            await bind_entity.sync()
        except RobloxNotFound:
            pass

        if bind_type in ("asset", "badge", "gamepass"):
            if bind_type == "gamepass":
                bind_type = "gamePasses"
            else:
                bind_type += "s"

            role_binds[bind_type][bind_id] = {
                "displayName": bind_entity.name,
                "roles": bind.get("roles", []),
                "removeRoles": bind.get("removeRoles", []),
                "nickname": bind.get("nickname"),
            }

        elif bind_type == "group":
            # No specific roles to give = entire group bind
            if not bind["roles"]:
                entire_groups[bind_id] = {
                    "groupName": bind_entity.name,
                    "removeRoles": bind.get("removeRoles"),
                    "nickname": bind.get("nickname"),
                }

                continue

            roleset = sub_data.get("roleset")
            min_rank = sub_data.get("min")
            max_rank = sub_data.get("max")
            guest = sub_data.get("guest")
            everyone = sub_data.get("everyone")

            group_data: dict = role_binds["groups"][bind_id]
            if not group_data.get("groupName"):
                group_data["groupName"] = bind_entity.name

            rank_bindings: dict = group_data.get("binds", {})
            range_bindings: list = group_data.get("ranges", [])

            if roleset is not None:
                rank_bindings[str(roleset)] = {
                    "roles": bind.get("roles", []),
                    "nickname": bind.get("nickname"),
                    "removeRoles": bind.get("removeRoles", []),
                }
            elif everyone:
                rank_bindings["all"] = {
                    "roles": bind.get("roles", []),
                    "nickname": bind.get("nickname"),
                    "removeRoles": bind.get("removeRoles", []),
                }
            elif guest:
                rank_bindings["0"] = {
                    "roles": bind.get("roles", []),
                    "nickname": bind.get("nickname"),
                    "removeRoles": bind.get("removeRoles", []),
                }
            elif (min_rank and max_rank) or (max_rank):
                min_rank = min_rank or 1
                range_bindings.append(
                    {
                        "roles": bind.get("roles", []),
                        "nickname": bind.get("nickname"),
                        "removeRoles": bind.get("removeRoles", []),
                        "low": min_rank,
                        "high": max_rank,
                    }
                )
            elif min_rank:
                rank_bindings[str(-abs(min_rank))] = {
                    "roles": bind.get("roles", []),
                    "nickname": bind.get("nickname"),
                    "removeRoles": bind.get("removeRoles", []),
                }

            group_data["binds"] = rank_bindings
            group_data["ranges"] = range_bindings

    return {"roleBinds": role_binds, "groupIDs": entire_groups}


async def get_bind_desc(
    guild_id: int | str,
    bind_id: int | str = None,
    bind_type: VALID_BIND_TYPES = None,
) -> str:
    """Get a string-based representation of all bindings (matching the bind_id and bind_type).

    Output is limited to 5 bindings, after that the user is told to visit the website to see the rest.

    Args:
        guild_id (int | str): ID of the guild.
        bind_id (int | str, optional): The entity ID to filter binds from. Defaults to None.
        bind_type (ValidBindType, optional): The type of bind to filter the response by.
            Defaults to None.

    Returns:
        str: Sentence representation of the first five binds matching the filters.
    """
    guild_binds = await get_binds(guild_id, category=bind_type, bind_id=bind_id)

    bind_strings = [await bind_description_generator(bind) for bind in guild_binds[:5]]
    output = "\n".join(bind_strings)

    if len(guild_binds) > 5:
        output += (
            f"\n_... and {len(guild_binds) - 5} more. "
            f"Click [here](https://www.blox.link/dashboard/guilds/{guild_id}/binds) to view the rest!_"
        )
    return output


async def create_bind(
    guild_id: int | str,
    bind_type: VALID_BIND_TYPES,
    bind_id: int,
    *,
    roles: list[str] = None,
    remove_roles: list[str] = None,
    nickname: str = None,
    **bind_data: Unpack[BindCriteriaDict],
):
    """Creates a new guild bind. If it already exists, the roles will be appended to the existing entry.

    Upon bind creation role IDs are checked to ensure that the roles being given by the binding are valid
    IDs.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (ValidBindType): The type of bind being created.
        bind_id (int): The ID of the entity this bind is for.
        roles (list[str], optional): Role IDs to be given to users for this bind. Defaults to None.
        remove_roles (list[str], optional): Role IDs to be removed from users for this bind. Defaults to None.
        nickname (str, optional): The nickname template for this bind. Defaults to None.

    Raises:
        BindConflictError: When a duplicate binding is found in the database,
        BindException: _description_
        BindException: _description_
    """

    bind_count = await count_binds(guild_id)

    if bind_count >= LIMITS["BINDS"]["FREE"]:
        premium_status = await get_premium_status(guild_id=guild_id)

        if bind_count >= LIMITS["BINDS"]["MAX"]:
            raise BindException("You have reached the maximum number of binds for this server.")

        if (bind_count >= LIMITS["BINDS"]["FREE"] and not premium_status.active) or (
            bind_count >= LIMITS["BINDS"]["PREMIUM"] and premium_status.active and premium_status.tier != "pro"  # fmt: skip
        ):
            raise PremiumRequired()

    guild_binds = await get_binds(str(guild_id))

    new_bind = GuildBind(
        roles=roles,
        removeRoles=remove_roles,
        nickname=nickname,
        criteria={
            "type": bind_type,
            "id": bind_id,
            **bind_data,
        }
    )

    # Check to see if there is a binding in place matching the given input
    existing_binds = []

    for bind in guild_binds:
        if bind == new_bind:
            existing_binds.append(bind)

    if not existing_binds:
        guild_binds.append(new_bind)

        await update_guild_data(guild_id, binds=[b.model_dump() for b in guild_binds])

        return

    # # merge the bind data
    # if bind_id:
    #     # group, badge, gamepass, and asset binds
    #     if len(existing_binds) > 1:
    #         # invalid bind. binds with IDs should only have one entry in the db.
    #         raise BindConflictError(
    #             "Binds with IDs should only have one entry. More than one duplicate was found."
    #         )

    #     if roles:
    #         # Remove invalid guild roles
    #         guild_roles = set((await bloxlink.fetch_roles(guild_id)).keys())
    #         existing_roles = set(existing_binds[0].get("roles", []) + roles)

    #         # Moves binding to the end of the array, if we wanted order to stay could get the
    #         # index, then remove, then insert again at that index.
    #         guild_binds.remove(existing_binds[0])

    #         existing_binds[0]["roles"] = list(guild_roles & existing_roles)
    #         guild_binds.append(existing_binds[0])

    #     if remove_roles:
    #         # Override roles to remove rather than append.
    #         guild_binds.remove(existing_binds[0])

    #         existing_binds[0]["removeRoles"] = remove_roles
    #         guild_binds.append(existing_binds[0])

    #     await update_guild_data(guild_id, binds=guild_binds)

    # else:
    #     # everything else
    #     raise BindException("No bind_id was passed when trying to make a bind.")


async def delete_bind(
    guild_id: int | str,
    bind_type: ValidBindType,
    bind_id: int,
    **bind_data,
):
    """Remove a bind from the database.

    This works through performing a $pull from the binds array in the database.
    Alternatively you could update the entire binds array to have everything except the binding(s) being
    removed.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (ValidBindType): The type of binding that is being removed.
        bind_id (int): The ID of the entity that this bind is for.
    """
    subquery = {
        "binds": {
            "bind": {
                "type": bind_type,
                "id": int(bind_id),
                **bind_data,
            }
        }
    }

    await bloxlink.mongo.bloxlink["guilds"].update_one({"_id": str(guild_id)}, {"$pull": subquery})


async def calculate_bound_roles(guild: hikari.RESTGuild, member: hikari.Member | MemberSerializable, roblox_user: users.RobloxAccount = None) -> UpdateEndpointResponse:
    # Get user roles + nickname
    update_data, update_data_response = await fetch_typed(
        f"{CONFIG.BIND_API_NEW}/binds/{guild.id}/{member.id}",
        UpdateEndpointResponse,
        method="POST",
        headers={"Authorization": CONFIG.BIND_API_AUTH},
        body={
            "guild_roles": GuildSerializable.from_hikari(guild).model_dump(by_alias=True)["roles"],
            "guild_name": guild.name,
            "member": MemberSerializable.from_hikari(member).model_dump(by_alias=True),
            "roblox_user": roblox_user.model_dump(by_alias=True) if roblox_user else None,
        },
    )

    if update_data_response.status != StatusCodes.OK:
        raise Message("Something went wrong internally when trying to update this user!")

    return update_data


async def apply_binds(
    member: hikari.Member | MemberSerializable,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user=False,
    update_embed_for_unverified=False,
) -> InteractiveMessage:
    """Apply bindings to a user, (apply the Verified & Unverified roles, nickname template, and custom bindings).

    Args:
        member (hikari.Member | dict): Information of the member being updated.
            For dicts, the valid keys are as follows:
            "role_ids", "id", "username" (or "name"), "nickname", "avatar_url"
        guild_id (hikari.Snowflake): The ID of the guild where the user is being updated.
        roblox_account (users.RobloxAccount, optional): The linked account of the user if one exists. May
            or may not be their primary account, could be a guild-specific link. Defaults to None.
        moderate_user (bool, optional): Check if any restrictions (age limit, group lock,
            ban evasion, alt detection) apply to this user. Defaults to False.
        update_embed_for_unverified (bool, optional): Should the embed be updated to show the roles added/removed

    Raises:
        Message: Raised if there was an issue getting a server's bindings.
        RuntimeError: Raised if the nickname endpoint on the bot API encountered an issue.
        BloxlinkForbidden: Raised when Bloxlink does not have permissions to give roles to a user.

    Returns:
        InteractiveMessage: The embed that will be shown to the user, may or may not include the components that
            will be shown, depending on if the user is restricted or not.
    """

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)

    embed = hikari.Embed()
    components = []
    warnings = []

    add_roles: list[int] = None
    remove_roles: list[int] = None
    nickname: str = None

    # Check restrictions
    restriction_check = restriction.Restriction(member=member, guild_id=guild_id, roblox_user=roblox_account)
    await restriction_check.sync()

    # restriction_obj: restriction.Restriction = restriction_info["restriction"]
    # warnings.extend(restriction_info["warnings"])

    removed_user = False
    if restriction_check.restricted:
        # Don't tell the user which account they're evading with.
        if restriction_check.source == "banEvader":
            warnings.append(
                f"({restriction_check.source}): User is evading a ban from a previous Discord account."
            )
        else:
            warnings.append(f"({restriction_check.source}): {restriction_check.reason}")

        # Remove the user if we're moderating.
        if moderate_user:
            try:
                await restriction_check.moderate()
            except (hikari.ForbiddenError, hikari.NotFoundError):
                warnings.append("User could not be removed from the server.")
            else:
                warnings.append("User was removed from the server.")
                removed_user = True

        # User won't see the response. Stop early. Bot tries to DM them before they are removed.
        if removed_user:
            return InteractiveMessage(embed_description=(
                "Member was removed from this server as per this server's settings.\n"
                "> *Admins, confused? Check the Discord audit log for the reason why this user was removed from the server.*"
            ))

        return InteractiveMessage(embed_description=(
            "Sorry, you are restricted from verifying in this server. Server admins: please run `/restriction view` to learn why."
        ))


    update_payload = await calculate_bound_roles(
        guild=guild,
        member=member,
        roblox_user=roblox_account
    )

    add_roles = update_payload.add_roles
    remove_roles = update_payload.remove_roles
    nickname = update_payload.nickname

    if update_payload.missing_roles:
        for role_name in update_payload.missing_roles:
            try:
                new_role: hikari.Role = await bloxlink.rest.create_role(
                    guild_id, name=role_name, reason="Creating missing role"
                )
                add_roles.append(new_role.id)

            except hikari.ForbiddenError:
                return InteractiveMessage(embed_description=(
                    "I don't have permission to create roles on this server."
                ))

    # Apply roles to user
    if add_roles or remove_roles or nickname != member.nickname:
        try:
            await bloxlink.edit_user(member=member,
                                    guild_id=guild_id,
                                    add_roles=add_roles,
                                    remove_roles=remove_roles,
                                    nickname=nickname if member.nickname != update_payload.nickname else None)
        except hikari.ForbiddenError:
            raise BloxlinkForbidden("I don't have permission to add roles to this user.") from None

    # Build response embed
    if roblox_account or update_embed_for_unverified:
        if add_roles or remove_roles or warnings or nickname:
            embed.title = "Member Updated"
        else:
            embed.title = "Member Unchanged"

        embed.set_author(
            name=member.username,
            icon=member.avatar_url or None,
            url=roblox_account.profile_link if roblox_account else None,
        )

        if add_roles:
            embed.add_field(
                name="Added Roles",
                value=", ".join(["<@&" + str(r) + ">" for r in add_roles]),
                inline=True,
            )

        if remove_roles:
            embed.add_field(
                name="Removed Roles",
                value=",".join(["<@&" + str(r) + ">" for r in remove_roles]),
                inline=True,
            )

        if nickname:
            embed.add_field(name="Nickname", value=nickname, inline=True)

        if warnings:
            embed.add_field(name=f"Warning{'s' if len(warnings) >= 2 else ''}", value="\n".join(warnings))

    else:
        # Default msg for unverified users.
        components = [
            Button(
                label="Verify with Bloxlink",
                url=await users.get_verification_link(
                    user_id=member.id,
                    guild_id=guild_id,
                ),
            ),
            Button(
                label="Stuck? See a Tutorial",
                url="https://www.youtube.com/watch?v=SbDltmom1R8&list=PLz7SOP-guESE1V6ywCCLc1IQWiLURSvBE&index=1&ab_channel=Bloxlink",
            ),
        ]

    return InteractiveMessage(
        content="To verify with Bloxlink, click the link below." if not roblox_account else None,
        embed=embed,
        action_rows=components,
    )


async def confirm_account(member: hikari.Member, guild_id: hikari.Snowflake, response: Response, roblox_account: users.RobloxAccount | None):
    """Send a request for the user to confirm their account"""

    if roblox_account:
        premium_status = await get_premium_status(guild_id=guild_id)

        roblox_accounts = (await fetch_user_data(member.id, "robloxAccounts")).robloxAccounts
        user_confirms = roblox_accounts.get("confirms", {})

        if not premium_status.active and str(guild_id) not in user_confirms:
            user_confirms[str(guild_id)] = roblox_account.id
            roblox_accounts["confirms"] = user_confirms
            await update_user_data(member.id, robloxAccounts=roblox_accounts)

            embed = hikari.Embed(
                title="Select Account",
                description="Please click the link below to select an account for this server.",
                color=ORANGE_COLOR
            )

            message = await response.send(
                embed=embed,
                components=[
                    Button(
                        label="Select Account",
                        url=f"https://blox.link/confirm/v2/{guild_id}"
                    ),
                ],
                ephemeral=True,
                fetch_message=True
            )

            try:
                await bloxlink.relay(f"account_confirm:{guild_id}:{roblox_account.id}", None, timedelta(minutes=2).seconds)
            except (TimeoutError, RuntimeError):
                pass

            try:
                await message.delete()
            except (hikari.ForbiddenError, hikari.NotFoundError):
                pass


def json_binds_to_guild_binds(bind_list: list, category: ValidBindType = None, id_filter: str = None) -> list:
    """Convert a bind from a dict/json representation to a GuildBind or GroupBind object.

    Args:
        bind_list (list): List of bindings to convert
        category (ValidBindType, optional): Category to filter the binds by. Defaults to None.
        id_filter (str, optional): ID to filter the binds by. Defaults to None.
            Applied after the category if both are given.

    Raises:
        BloxlinkException: When no matching bind type is found from the json input.

    Returns:
        list: The list of bindings as GroupBinds or GuildBinds, filtered by the category & id.
    """
    binds = []

    id_filter_str = str(id_filter).lower() if id_filter else None

    if id_filter:
        id_filter = None if id_filter_str in {"none", "view binds"} else str(id_filter)

    for bind in bind_list:
        bind_data = bind.get("bind")
        bind_type = bind_data.get("type")

        if category and bind_type != category:
            continue

        if id_filter and str(bind_data.get("id")) != id_filter:
            continue

        if bind_type == "group":
            classed_bind = GroupBind(**bind)
        elif bind_type:
            classed_bind = GuildBind(**bind)
        else:
            raise BloxlinkException("Invalid bind structure found.")

        binds.append(classed_bind)

    bind_list = list(binds)

    if id_filter is not None:
        bind_list.sort(key=lambda e: e.bind["id"])
    return bind_list


def join_bind_strings(strings: list) -> str:
    """Helper method to use when joining all the strings for the viewbind embed.

    Uses emojis to display the strings in a tier-format where the top level is the "identifier" that the
    lower bind strings display as a subset of.

    Args:
        strings (list): List of string to join

    Returns:
        str: Tiered formatted string.
    """

    # Use REPLY_CONT for all but last element
    split_strings = [f"\n{REPLY_CONT}".join(strings[:-1]), strings[-1]] if len(strings) > 2 else strings
    return f"\n{REPLY_EMOTE}".join(split_strings)


async def bind_description_generator(bind: GroupBind | GuildBind) -> str:
    """Builds a sentence-formatted string for a binding.

    Results in the layout of: <USERS> <CONTENT ID/RANK> receive the role(s) <ROLE LIST>, and have the roles
    removed <REMOVE ROLE LIST>

    The remove role list is only appended if it there are roles to remove.

    Example output:
        All users in this group receive the role matching their group rank name.
        People with the rank Developers (200) receive the role @a
        People with a rank greater than or equal to Supporter (1) receive the role @b

    Args:
        bind (GroupBind | GuildBind): The binding to build the string for.

    Returns:
        str: The sentence description of this binding.
    """

    if bind.type == "group":
        if bind.subtype == "linked_group":
            return "- _All users in **this** group receive the role matching their group rank name._"

    if not bind.entity.synced:
        try:
            await bind.entity.sync()
        except (RobloxNotFound, RobloxAPIError):
            pass

    roles = bind.roles if bind.roles else []
    role_str = ", ".join(f"<@&{val}>" for val in roles)
    remove_roles = bind.remove_roles if bind.remove_roles else []
    remove_role_str = ", ".join(f"<@&{val}>" for val in remove_roles)

    prefix = _bind_desc_prefix_gen(bind)
    content = _bind_desc_content_gen(bind)

    return (
        f"- _{prefix} {f'**{content}**' if content else ''} receive the "
        f"role{'s' if len(roles) > 1  else ''} {role_str}"
        f"{'' if len(remove_roles) == 0 else f', and have these roles removed: {remove_role_str}'}_"
    )


def _bind_desc_prefix_gen(bind: GuildBind) -> str | None:
    """Generate the prefix string for a bind's description.

    Args:
        bind (GroupBind | GuildBind): Bind to generate the prefix for.

    Returns:
        str | None: The prefix if one should be set.
    """

    if bind.type != "group":
        return f"People who own the {bind.type}"

    prefix = None
    if bind.criteria.group.min and bind.criteria.group.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("rng")

    elif bind.criteria.group.min:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")

    elif bind.criteria.group.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("lte")

    elif bind.criteria.group.roleset:
        if bind.criteria.group.roleset < 0:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")
        else:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("equ")

    elif bind.criteria.group.guest:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gst")

    elif bind.criteria.group.everyone:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("all")

    return prefix


def _bind_desc_content_gen(bind: GuildData) -> str | None:
    """Generate the content string for a bind's description.

    This will be the content that describes the rolesets to be given,
    or the name of the other entity that the bind is for.

    Args:
        bind (GroupBind | GuildBind): Bind to generate the content for.

    Returns:
        str | None: The content if it should be set.
            Roleset bindings like guest and everyone do not have content to display,
            as the given prefix string contains the content.
    """

    if bind.type != "group":
        return str(bind.entity).replace("**", "")

    group = bind.entity
    content: str = None

    if bind.criteria.group.min and bind.criteria.group.max:
        min_str = group.roleset_name_string(bind.criteria.group.min, bold_name=False)
        max_str = group.roleset_name_string(bind.max, bold_name=False)
        content = f"{min_str}** and **{max_str}"

    elif bind.criteria.group.min:
        content = group.roleset_name_string(bind.criteria.group.min, bold_name=False)

    elif bind.criteria.group.max:
        content = group.roleset_name_string(bind.crigeria.group.max, bold_name=False)

    elif bind.criteria.group.roleset:
        content = group.roleset_name_string(abs(bind.criteria.group.roleset), bold_name=False)

    return content
