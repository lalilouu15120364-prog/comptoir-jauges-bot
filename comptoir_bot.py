import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ----------------------------------------
# 🔐 TOKEN via variable d'environnement
# ----------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise RuntimeError("❌ Erreur : La variable d'environnement DISCORD_TOKEN n'est pas définie.")


# ----------------------------------------
# 🤖 INTENTS
# ----------------------------------------
intents = discord.Intents.default()
intents.message_content = False  # Pas nécessaire pour les slash commands
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# ----------------------------------------
# 🎚️ Config des quartiers & salons
# ----------------------------------------

# Valeurs des jauges (0 à 5)
district_values: dict[str, int] = {
    "Méhumide": 0,
    "Pointe du Crochet": 0,
    "Voie des Marins": 0,
    "Haut quartier": 0,
    "Marché des Alizées": 0,
    "Port principal": 0,
}

MAX_JAUGE = 5

# Nom / morceau de nom des salons pour chaque quartier
# (on cherche un salon dont le nom contient ce texte en minuscules)
DISTRICT_CHANNEL_HINTS: dict[str, str] = {
    "Méhumide": "méchumide",
    "Pointe du Crochet": "pointe-du-crochet",
    "Voie des Marins": "voie-du-marin",
    "Haut quartier": "haut-quartier",
    "Marché des Alizées": "alizés",      # ou "alizées" selon ton salon
    "Port principal": "grand-port",
}

# Salon du panneau global
GLOBAL_PANEL_CHANNEL_HINT = "jauges-comp"  # un morceau du nom du salon global

# ID du message panneau global (créé automatiquement)
global_panel_message_id: int | None = None

# IDs des panneaux par quartier : { "Méhumide": message_id, ... }
district_panel_message_ids: dict[str, int] = {name: None for name in district_values.keys()}


# ----------------------------------------
# 🔧 Utilitaires
# ----------------------------------------

def render_gauge(value: int) -> str:
    """Transforme une valeur 0–5 en barre de jauge."""
    value = max(0, min(MAX_JAUGE, value))
    filled = "■" * value
    empty = "□" * (MAX_JAUGE - value)
    return filled + empty


def find_channel_by_hint(guild: discord.Guild, hint: str) -> discord.TextChannel | None:
    """Retourne le premier salon texte dont le nom contient 'hint' (en minuscules)."""
    hint = hint.lower()
    for channel in guild.text_channels:
        if hint in channel.name.lower():
            return channel
    return None


def make_global_embed() -> discord.Embed:
    """Embed du panneau global."""
    embed = discord.Embed(
        title="État des quartiers de Boralus",
        description="Panneau récapitulatif des jauges du Comptoir.",
        colour=discord.Colour.dark_gold(),
    )

    for name, val in district_values.items():
        embed.add_field(
            name=name,
            value=render_gauge(val),
            inline=False,
        )

    embed.set_footer(text="Utilisez /comptoir pour mettre à jour les jauges.")
    return embed


def make_district_embed(district_name: str) -> discord.Embed:
    """Embed pour un seul quartier."""
    value = district_values.get(district_name, 0)

    embed = discord.Embed(
        title=f"{district_name} — Jauge du quartier",
        description="Suivi local de ce quartier.",
        colour=discord.Colour.blue(),
    )
    embed.add_field(name="État actuel", value=render_gauge(value), inline=False)
    embed.set_footer(text="Mise à jour via /comptoir")
    return embed


# ----------------------------------------
# 🟩 Mise à jour des panneaux
# ----------------------------------------

async def update_global_panel(channel: discord.TextChannel):
    """Crée ou met à jour le panneau global dans le salon donné."""
    global global_panel_message_id

    embed = make_global_embed()

    # Si on a déjà un message, on essaie de le modifier
    if global_panel_message_id is not None:
        try:
            msg = await channel.fetch_message(global_panel_message_id)
            await msg.edit(embed=embed, content=None)
            return
        except discord.NotFound:
            # Le message n'existe plus, on en recrée un
            global_panel_message_id = None

    # Création d'un nouveau message
    msg = await channel.send(embed=embed)
    global_panel_message_id = msg.id


async def update_district_panel(channel: discord.TextChannel, district_name: str):
    """Crée ou met à jour le panneau individuel d'un quartier."""
    message_id = district_panel_message_ids.get(district_name)
    embed = make_district_embed(district_name)

    if message_id is not None:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed, content=None)
            return
        except discord.NotFound:
            district_panel_message_ids[district_name] = None

    msg = await channel.send(embed=embed)
    district_panel_message_ids[district_name] = msg.id


# ----------------------------------------
# 📌 Slash Command : /comptoir
# ----------------------------------------

@tree.command(name="comptoir", description="Met à jour les jauges des quartiers.")
@app_commands.describe(
    quartier="Choisissez le quartier à modifier.",
    valeur="Valeur de la jauge (0 à 5)."
)
@app_commands.choices(quartier=[
    app_commands.Choice(name="Méhumide", value="Méhumide"),
    app_commands.Choice(name="Pointe du Crochet", value="Pointe du Crochet"),
    app_commands.Choice(name="Voie des Marins", value="Voie des Marins"),
    app_commands.Choice(name="Haut quartier", value="Haut quartier"),
    app_commands.Choice(name="Marché des Alizées", value="Marché des Alizées"),
    app_commands.Choice(name="Port principal", value="Port principal"),
])
async def comptoir(
    interaction: discord.Interaction,
    quartier: app_commands.Choice[str],
    valeur: int
):
    """Commande principale pour changer une jauge."""
    if not 0 <= valeur <= MAX_JAUGE:
        await interaction.response.send_message("❌ La valeur doit être entre 0 et 5.", ephemeral=True)
        return

    district_name = quartier.value
    district_values[district_name] = valeur

    # Réponse à l'utilisateur
    await interaction.response.send_message(
        f"✨ **Jauge mise à jour !**\n"
        f"{district_name} → {render_gauge(valeur)}"
    )

    guild = interaction.guild
    if guild is None:
        return

    # 🔄 Mise à jour du panneau global
    global_channel = find_channel_by_hint(guild, GLOBAL_PANEL_CHANNEL_HINT)
    if global_channel:
        await update_global_panel(global_channel)

    # 🔄 Mise à jour du panneau du quartier concerné
    hint = DISTRICT_CHANNEL_HINTS.get(district_name)
    if hint:
        district_channel = find_channel_by_hint(guild, hint)
        if district_channel:
            await update_district_panel(district_channel, district_name)


# ----------------------------------------
# 🔄 Mise en ligne du bot
# ----------------------------------------

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Slash commands synchronisées : {len(synced)}")
    except Exception as e:
        print("Erreur de sync :", e)


# ----------------------------------------
# ▶️ Launch
# ----------------------------------------
bot.run(TOKEN)
