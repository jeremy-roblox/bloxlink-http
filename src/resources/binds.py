from __future__ import annotations

import re
from attrs import define
from typing import Literal

import hikari

import resources.restriction as restriction
import resources.roblox.users as users
from resources.bloxlink import GuildData
from resources.bloxlink import instance as bloxlink
from resources.constants import GROUP_RANK_CRITERIA_TEXT, REPLY_CONT, REPLY_EMOTE
from resources.exceptions import BloxlinkException, BloxlinkForbidden, Message, RobloxAPIError, RobloxNotFound
from resources.response import EmbedPrompt
from resources.roblox.roblox_entity import RobloxEntity, create_entity
from resources.secrets import BIND_API, BIND_API_AUTH  # pylint: disable=E0611
from resources.utils import default_field, fetch

nickname_template_regex = re.compile(r"\{(.*?)\}")
any_group_nickname = re.compile(r"\{group-rank-(.*?)\}")
bracket_search = re.compile(r"\[(.*)\]")


@define(slots=True)
class GuildBind:
    """Represents a binding from the database.

    Post init it should be expected that the id, type, and entity types are not None.

    Attributes:
        nickname (str, optional): The nickname template to be applied to users. Defaults to None.
        roles (list): The IDs of roles that should be given by this bind.
        removeRole (list): The IDs of roles that should be removed when this bind is given.

        id (int, optional): The ID of the entity for this binding. Defaults to None.
        type (Literal[group, asset, gamepass, badge]): The type of binding this is representing.
        bind (dict): The raw data that the database stores for this binding.

        entity (RobloxEntity, optional): The entity that this binding represents. Defaults to None.
    """

    nickname: str = None
    roles: list = default_field(list())
    removeRoles: list = default_field(list())

    id: int = None
    type: Literal["group", "asset", "gamepass", "badge"] = Literal["group", "asset", "gamepass", "badge"]
    bind: dict = default_field({"type": "", "id": None})

    entity: RobloxEntity = None

    def __post_init__(self):
        self.id = self.bind.get("id")
        self.type = self.bind.get("type")

        self.entity = create_entity(self.type, self.id)


class GroupBind(GuildBind):
    """Represents additional attributes that only apply to group binds.

    Except for min and max (which are used for ranges), only one attribute should be considered to be
    not None at a time.

    Attributes:
        min (int, optional): The minimum rank that this bind applies to. Defaults to None.
        max (int, optional): The maximum rank that this bind applies to. Defaults to None.
        roleset (int, optional): The specific rank that this bind applies to. Defaults to None.
            Can be negative (in legacy format) to signify that specific rank and higher.
        everyone (bool, optional): Does this bind apply to everyone. Defaults to None.
        guest (bool, optional): Does this bind apply to guests. Defaults to None.
    """

    min: int = None
    max: int = None
    roleset: int = None
    everyone: bool = None
    guest: bool = None

    def __post_init__(self):
        self.min = self.bind.get("min", None)
        self.max = self.bind.get("max", None)
        self.roleset = self.bind.get("roleset", None)
        self.everyone = self.bind.get("everyone", None)
        self.guest = self.bind.get("guest", None)

        return super().__post_init__()

    @property
    def subtype(self) -> str:
        """The specific type of this group bind.

        Returns:
            str: "linked_group" or "group_roles" depending on if there
                are roles explicitly listed to be given or not.
        """
        if not self.roles or self.roles in ("undefined", "null"):
            return "linked_group"
        else:
            return "group_roles"


async def count_binds(guild_id: int | str, bind_id: int | str = None) -> int:
    """Count the number of binds that this guild_id has created.

    Args:
        guild_id (int | str): ID of the guild.
        bind_id (int | str, optional): ID of the entity to filter by when counting. Defaults to None.

    Returns:
        int: The number of bindings this guild has created.
    """
    guild_data: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "binds")

    return (
        len(guild_data.binds)
        if not bind_id
        else sum(1 for b in guild_data.binds if b["bind"].get("id") == int(bind_id)) or 0
    )


async def get_binds(guild_id: int | str, bind_id: int | str = None) -> list[GuildData.binds]:
    """Get the current guild binds.

    Args:
        guild_id (int | str): ID of the guild.
        bind_id (int | str, optional): ID of the entity to filter by when counting. Defaults to None.

    Returns:
        int: The number of bindings this guild has created.
    """

    guild_data: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "binds")

    return guild_data.binds if not bind_id else [b for b in guild_data.binds if b["bind"].get("id") == int(bind_id)]


async def get_bind_desc(
    guild_id: int | str,
    bind_id: int | str = None,
    bind_type: Literal["group", "asset", "badge", "gamepass"] = None,
) -> str:
    """Get a string-based representation of all bindings (matching the bind_id and bind_type).

    Output is limited to 5 bindings, after that the user is told to visit the website to see the rest.

    Args:
        guild_id (int | str): ID of the guild.
        bind_id (int | str, optional): The entity ID to filter binds from. Defaults to None.
        bind_type (Literal[group, asset, badge, gamepass], optional): The type of bind to filter the response by.
            Defaults to None.

    Returns:
        str: Sentence representation of the first five binds matching the filters.
    """
    guild_binds = (await bloxlink.fetch_guild_data(guild_id, "binds")).binds
    guild_binds = json_binds_to_guild_binds(guild_binds, category=bind_type, id_filter=bind_id)

    bind_strings = [await bind_description_generator(bind) for bind in guild_binds]

    output = "\n".join(bind_strings[:5])
    if len(bind_strings) > 5:
        output += (
            f"\n_... and {len(bind_strings) - 5} more. "
            f"Click [here](https://www.blox.link/dashboard/guilds/{guild_id}/binds) to view the rest!_"
        )
    return output


async def create_bind(
    guild_id: int | str,
    bind_type: Literal["group", "asset", "badge", "gamepass"],
    bind_id: int,
    *,
    roles: list[str] = None,
    remove_roles: list[str] = None,
    nickname: str = None,
    **bind_data,
):
    """Creates a new guild bind. If it already exists, the roles will be appended to the existing entry.

    Upon bind creation role IDs are checked to ensure that the roles being given by the binding are valid
    IDs.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (Literal[group, asset, badge, gamepass]): The type of bind being created.
        bind_id (int): The ID of the entity this bind is for.
        roles (list[str], optional): Role IDs to be given to users for this bind. Defaults to None.
        remove_roles (list[str], optional): Role IDs to be removed from users for this bind. Defaults to None.
        nickname (str, optional): The nickname template for this bind. Defaults to None.

    Raises:
        NotImplementedError: When a duplicate binding is found in the database,
        NotImplementedError: _description_
        NotImplementedError: _description_
    """

    guild_binds: list = (await bloxlink.fetch_guild_data(str(guild_id), "binds")).binds

    # Check to see if there is a binding in place matching the given input
    existing_binds = []

    for bind in guild_binds:
        b = bind["bind"]

        if b["type"] != bind_type or b["id"] != bind_id:
            continue

        if len(bind_data) > 0:
            bind_cond = (
                (b.get("roleset") == bind_data.get("roleset") if "roleset" in bind_data else False)
                or (b.get("min") == bind_data.get("min") if "min" in bind_data else False)
                or (b.get("max") == bind_data.get("max") if "max" in bind_data else False)
                or (b.get("guest") == bind_data.get("guest") if "guest" in bind_data else False)
                or (b.get("everyone") == bind_data.get("everyone") if "everyone" in bind_data else False)
            )

            if not bind_cond:
                continue

        elif len(b) > 2 and len(bind_data) == 0:
            continue

        existing_binds.append(bind)

    if not existing_binds:
        # Create the binding
        new_bind = {
            "roles": roles,
            "removeRoles": remove_roles,
            "nickname": nickname,
            "bind": {"type": bind_type, "id": bind_id, **bind_data},
        }

        guild_binds.append(new_bind)

        await bloxlink.update_guild_data(guild_id, binds=guild_binds)

        return

    if bind_id:
        # group, badge, gamepass, and asset binds
        if len(existing_binds) > 1:
            # invalid bind. binds with IDs should only have one entry in the db.
            raise NotImplementedError(
                "Binds with IDs should only have one entry. More than one duplicate was found."
            )

        if roles:
            # Remove invalid guild roles
            guild_roles = set((await bloxlink.fetch_roles(guild_id)).keys())
            existing_roles = set(existing_binds[0].get("roles", []) + roles)

            # Moves binding to the end of the array, if we wanted order to stay could get the
            # index, then remove, then insert again at that index.
            guild_binds.remove(existing_binds[0])

            existing_binds[0]["roles"] = list(guild_roles & existing_roles)
            guild_binds.append(existing_binds[0])
        else:
            # In ideal circumstances, this case should be for entire group bindings only
            raise NotImplementedError("No roles to be assigned were passed.")

        if remove_roles:
            # Override roles to remove rather than append.
            guild_binds.remove(existing_binds[0])

            existing_binds[0]["removeRoles"] = remove_roles
            guild_binds.append(existing_binds[0])

        await bloxlink.update_guild_data(guild_id, binds=guild_binds)

    else:
        # everything else
        raise NotImplementedError("No bind_id was passed when trying to make a bind.")


async def delete_bind(
    guild_id: int | str,
    bind_type: Literal["group", "asset", "badge", "gamepass"],
    bind_id: int,
    **bind_data,
):
    """Remove a bind from the database.

    This works through performing a $pull from the binds array in the database.
    Alternatively you could update the entire binds array to have everything except the binding(s) being
    removed.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (Literal[group, asset, badge, gamepass]): The type of binding that is being removed.
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


async def apply_binds(
    member: hikari.Member | dict,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user=False,
) -> EmbedPrompt:
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

    Raises:
        Message: Raised if there was an issue getting a server's bindings.
        RuntimeError: Raised if the nickname endpoint on the bot API encountered an issue.
        BloxlinkForbidden: Raised when Bloxlink does not have permissions to give roles to a user.

    Returns:
        EmbedPrompt: The embed that will be shown to the user, may or may not include the components that
            will be shown, depending on if the user is restricted or not.
    """
    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)

    role_ids = []
    member_id = None
    username = ""
    nickname = ""
    avatar_url = ""

    # Get necessary user information.
    if isinstance(member, hikari.Member):
        role_ids = member.role_ids
        member_id = member.id
        username = member.username
        nickname = member.nickname
        avatar_url = member.display_avatar_url.url

    elif isinstance(member, dict):
        role_ids = member.get("role_ids", [])
        member_id = member.get("id")
        username = member.get("username", None)

        if not username:
            username = member.get("name", "")

        nickname = member.get("nickname", "")
        avatar_url = member.get("avatar_url", "")

    member_roles: dict = {}
    for member_role_id in role_ids:
        if role := guild.roles.get(member_role_id):
            member_roles[role.id] = {
                "id": role.id,
                "name": role.name,
                "managed": bool(role.bot_id) and role.name != "@everyone",
            }

    # add_roles:    set = set() # used exclusively for display purposes
    add_roles: list[hikari.Role] = []
    remove_roles: list[hikari.Role] = []
    possible_nicknames: list[list[hikari.Role | str]] = []
    warnings: list[str] = []
    chosen_nickname = None
    applied_nickname = None

    # Handle restrictions.
    restrict_result = None
    if moderate_user:
        restrict_result = await restriction.check_guild_restrictions(
            guild_id,
            {
                "id": member_id,
                "roles": member_roles,
                "account": roblox_account,
            },
        )

    if restrict_result is not None:
        await restrict_result.moderate(member_id, guild)

        if restrict_result.removed:
            return restrict_result.prompt(guild.name)

        if restrict_result.restriction == "disallowAlts":
            warnings.append(
                "This server does not allow alt accounts, because of this your other accounts have "
                "been kicked from this server."
            )

    restricted_flag = (
        False if (restrict_result is None or restrict_result.restriction == "disallowAlts") else True
    )

    # Get user's bindings (includes verified + unverified roles) to apply + nickname templates.
    user_binds, user_binds_response = await fetch(
        "POST",
        f"{BIND_API}/binds/{member_id}",
        headers={"Authorization": BIND_API_AUTH},
        body={
            "guild": {
                "id": guild.id,
                "roles": [
                    {"id": r.id, "name": r.name, "managed": bool(r.bot_id) and r.name != "@everyone"}
                    for r in guild.roles.values()
                ],
            },
            "member": {"id": member_id, "roles": member_roles},
            "roblox_account": roblox_account.to_dict() if roblox_account else None,
            "restricted": restricted_flag,
        },
    )

    if user_binds_response.status == 200:
        user_binds = user_binds["binds"]
    else:
        raise Message("Something went wrong getting this user's relevant bindings!")

    role_ids_to_give = []
    role_ids_to_remove = []
    for required_bind in user_binds["required"]:
        role_ids_to_give.extend(required_bind[1])
        role_ids_to_remove.extend(required_bind[2])

        if required_bind[3]:
            for bind_role_id in required_bind[1]:
                if role := guild.roles.get(int(bind_role_id)):
                    possible_nicknames.append([role, required_bind[3]])

    # Get the list of roles that the required bindings will give to the user.
    user_roles, user_roles_response = await fetch(
        "POST",
        f"{BIND_API}/binds/roles",
        headers={"Authorization": BIND_API_AUTH},
        body={
            "guild_id": guild.id,
            "user_roles": list(member_roles.keys()),
            "successful_binds": {
                "give": role_ids_to_give,
                "remove": role_ids_to_remove,
            },
        },
    )

    if user_roles_response.status != 200 or not user_roles["success"]:
        raise Message("Something went wrong when deciding which roles this user will get!")

    added_roles = user_roles["added_roles"]
    removed_roles = user_roles["removed_roles"]
    user_roles = user_roles["final_roles"]

    # Convert to IDs discord roles.
    for role_id in added_roles:
        if role := guild.roles.get(int(role_id)):
            add_roles.append(role)

    for role_id in removed_roles:
        if role := guild.roles.get(int(role_id)):
            remove_roles.append(role)

    # first apply the required binds, then ask the user if they want to apply the optional binds

    # real_add_roles = add_roles

    # remove_roles   = remove_roles.difference(add_roles) # added roles get priority
    # real_add_roles = add_roles.difference(set(member.roles)) # remove roles that are already on the user, also new variable so we can achieve idempotence

    # if real_add_roles or remove_roles:
    #     await bloxlink.edit_user_roles(member, guild_id, add_roles=real_add_roles, remove_roles=remove_roles)

    if possible_nicknames:
        if len(possible_nicknames) == 1:
            chosen_nickname = possible_nicknames[0][1]
        else:
            # get highest role with a nickname
            highest_role = sorted(possible_nicknames, key=lambda e: e[0].position, reverse=True)

            if highest_role:
                chosen_nickname = highest_role[0][1]

        if chosen_nickname:
            chosen_nickname_http, nickname_response = await fetch(
                "GET",
                f"{BIND_API}/nickname/parse/",
                headers={"Authorization": BIND_API_AUTH},
                body={
                    "user_data": {"name": username, "nick": nickname, "id": member_id},
                    "guild_id": guild.id,
                    "guild_name": guild.name,
                    "roblox_account": roblox_account.to_dict() if roblox_account else None,
                    "template": chosen_nickname,
                    "restricted": restricted_flag,
                },
            )

            if nickname_response.status == 200:
                chosen_nickname = chosen_nickname_http["nickname"]
            else:
                raise RuntimeError(f"Nickname API returned an error: {chosen_nickname_http}")

            if str(guild.owner_id) == str(member_id):
                warnings.append(
                    f"Since you're the Server Owner, I cannot modify your nickname.\nNickname: {chosen_nickname}"
                )
            else:
                try:
                    await bloxlink.rest.edit_member(guild_id, member_id, nickname=chosen_nickname)

                except hikari.errors.ForbiddenError:
                    warnings.append("I don't have permission to change the nickname of this user.")

                else:
                    applied_nickname = chosen_nickname

    try:
        if add_roles or remove_roles:
            await bloxlink.rest.edit_member(
                guild_id,
                member_id,
                roles=user_roles,
            )
    except hikari.errors.ForbiddenError:
        raise BloxlinkForbidden("I don't have permission to add roles to this user.") from None

    if restrict_result is not None and not restrict_result.removed:
        return restrict_result.prompt(guild.name)

    if add_roles or remove_roles or warnings:
        embed = hikari.Embed(
            title="Member Updated",
        )
        embed.set_author(
            name=username,
            icon=avatar_url,
            url=roblox_account.profile_link if roblox_account else None,
        )

        if add_roles:
            embed.add_field(name="Added Roles", value=",".join([r.mention for r in add_roles]))

        if remove_roles:
            embed.add_field(name="Removed Roles", value=",".join([r.mention for r in remove_roles]))

        if not (add_roles and remove_roles):
            embed.add_field(
                name="Roles",
                value="Your roles are already up to date! If this is a mistake, please contact this server's admins as they did not set up the bot correctly.",
            )

        if applied_nickname:
            embed.add_field(name="Nickname Changed", value=applied_nickname)

        if warnings:
            embed.add_field(name=f"Warning{'s' if len(warnings) >= 2 else ''}", value="\n".join(warnings))

    else:
        embed = hikari.Embed(description="No binds apply to you!")

    return EmbedPrompt(embed, components=[])


def json_binds_to_guild_binds(bind_list: list, category: str = None, id_filter: str = None) -> list:
    """Convert a bind from a dict/json representation to a GuildBind or GroupBind object.

    Args:
        bind_list (list): List of bindings to convert
        category (str, optional): Category to filter the binds by. Defaults to None.
        id_filter (str, optional): ID to filter the binds by. Defaults to None.
            Applied after the category if both are given.

    Raises:
        BloxlinkException: When no matching bind type is found from the json input.

    Returns:
        list: The list of bindings as GroupBinds or GuildBinds, filtered by the category & id.
    """
    binds = []

    id_filter_str = str(id_filter).lower() if id_filter else None

    print(id_filter)

    if id_filter:
        id_filter = (
            None if id_filter_str == "none" or id_filter_str == "view binds" else str(id_filter)
        )

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
    print(bind_list)
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
    if isinstance(bind, GroupBind):
        if bind.subtype == "linked_group":
            return "- _All users in **this** group receive the role matching their group rank name._"

    if not bind.entity.synced:
        try:
            await bind.entity.sync()
        except RobloxNotFound:
            pass
        except RobloxAPIError:
            pass

    roles = bind.roles if bind.roles else []
    role_str = ", ".join(f"<@&{val}>" for val in roles)
    remove_roles = bind.removeRoles if bind.removeRoles else []
    remove_role_str = ", ".join(f"<@&{val}>" for val in remove_roles)

    prefix = _bind_desc_prefix_gen(bind)
    content = _bind_desc_content_gen(bind)

    return (
        f"- _{prefix} {f'**{content}**' if content else ''} receive the "
        f"role{'s' if len(roles) > 1  else ''} {role_str}"
        f"{'' if len(remove_roles) == 0 else f', and have these roles removed: {remove_role_str}'}_"
    )


def _bind_desc_prefix_gen(bind: GroupBind | GuildBind) -> str | None:
    """Generate the prefix string for a bind's description.

    Args:
        bind (GroupBind | GuildBind): Bind to generate the prefix for.

    Returns:
        str | None: The prefix if one should be set.
    """
    if not isinstance(bind, GroupBind):
        return f"People who own the {bind.type}"

    prefix = None
    if bind.min and bind.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("rng")

    elif bind.min:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")

    elif bind.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("lte")

    elif bind.roleset:
        if bind.roleset < 0:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")
        else:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("equ")

    elif bind.guest:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gst")

    elif bind.everyone:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("all")

    return prefix


def _bind_desc_content_gen(bind: GroupBind | GuildData) -> str | None:
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
    if not isinstance(bind, GroupBind):
        return str(bind.entity).replace("**", "")

    group = bind.entity
    content = None

    if bind.min and bind.max:
        min_str = group.roleset_name_string(bind.min, bold_name=False)
        max_str = group.roleset_name_string(bind.max, bold_name=False)
        content = f"{min_str}** and **{max_str}"

    elif bind.min:
        content = group.roleset_name_string(bind.min, bold_name=False)

    elif bind.max:
        content = group.roleset_name_string(bind.max, bold_name=False)

    elif bind.roleset:
        content = group.roleset_name_string(abs(bind.roleset), bold_name=False)

    return content
