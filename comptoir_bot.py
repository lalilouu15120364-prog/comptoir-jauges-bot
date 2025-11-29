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
# On n'a pas besoin du contenu des messages pour les slash commands
intents.message_content = False
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# ----------------------------------------
# ⚙️ Données des quartiers & jauges
# ----------------------------------------

MAX_JAUGE = 5

# Nom "RP" du quartier -> état des jauges
districts = {
    "Méhumide": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
    "Pointe du Crochet": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
    "Voie du Marin": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
    "Haut quartier": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
    "Marché des Alizées": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
    "Port principal": {
        "Humeur": 0,
        "Tension": 0,
        "Activité": 0,
        "Menaces": 0,
    },
}

# Quartier RP -> nom du salon de quartier
# (on matche en fin de nom pour tolérer les emojis devant)
district_channel_suffix = {
    "Méhumide": "méchumide",
    "Pointe du Crochet": "pointe-du-crochet",
    "Voie du Marin": "voie-du-marin",
    "Haut quartier": "haut-quartier",
    "Marché des Alizées": "alizés",
    "Port principal": "grand-port",
}

# IDs des messages des panneaux (en mémoire uniquement)
global_panel_message_id: int | None = None
district_panel_ids: dict[str, int] = {}  # quartier -> message_id


# ----------------------------------------
# 🔧 Fonctions utilitaires
# ----------------------------------------

def render_gauge(value: int) -> str:
    value = max(0, min(MAX_JAUGE, value))
    filled = "■" * value
    empty = "□" * (MAX_JAUGE - value)
    return f"{filled}{empty} {value}/{MAX_JAUGE}"


def make_global_embed() -> discord.Embed:
    embed = discord.Embed(
        title="État des quartiers de Boralus",
        description="Panneau général des jauges du Comptoir.",
        colour=discord.Colour.gold(),
    )

    for district_name, gauges in districts.items():
        text = (
            f"**Humeur :** {render_gauge(gauges['Humeur'])}\n"
            f"**Tension :** {render_gauge(gauges['Tension'])}\n"
            f"**Activité :** {render_gauge(gauges['Activité'])}\n"
            f"**Menaces :** {render_gauge(gauges['Menaces'])}\n"
        )
        embed.add_field(name=district_name, value=text, inline=False)

    embed.set_footer(text="Utilisez /comptoir pour mettre à jour les jauges.")
    return embed


def make_district_embed(district_name: str) -> discord.Embed:
    gauges = districts[district_name]
    embed = discord.Embed(
        title=f"Quartier : {district_name}",
        colour=discord.Colour.blurple(),
    )
    embed.add_field(name="Humeur", value=render_gauge(gauges["Humeur"]), inline=False)
    embed.add_field(name="Tension", value=render_gauge(gauges["Tension"]), inline=False)
    embed.add_field(name="Activité", value=render_gauge(gauges["Activité"]), inline=False)
    embed.add_field(name="Menaces", value=render_gauge(gauges["Menaces"]), inline=False)
    embed.set_footer(text="Mise à jour via /comptoir.")
    return embed


def find_channel_by_suffix(guild: discord.Guild, suffix: str) -> discord.TextChannel | None:
    suffix = suffix.lower()
    for channel in guild.text_channels:
        if channel.name.lower().endswith(suffix):
            return channel
    return None


def find_global_panel_channel(guild: discord.Guild) -> discord.TextChannel | None:
    # Ton salon s'appelle "jauges-comptoir" (avec ou sans emoji)
    for channel in guild.text_channels:
        if "jauges-comp" in channel.name.lower():
            return channel
    return None


# ----------------------------------------
# 🟩 Mise à jour des panneaux
# ----------------------------------------

async def update_global_panel(guild: discord.Guild):
    """Crée ou met à jour le panneau global dans #jauges-comptoir."""
    global global_panel_message_id

    channel = find_global_panel_channel(guild)
    if channel is None:
        return  # pas de salon dédié, on ne fait rien

    embed = make_global_embed()

    if global_panel_message_id is None:
        msg = await channel.send(embed=embed)
        global_panel_message_id = msg.id
    else:
        try:
            msg = await channel.fetch_message(global_panel_message_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            global_panel_message_id = msg.id


async def update_district_panel(guild: discord.Guild, district_name: str):
    """Crée ou met à jour le panneau individuel d'un quartier."""
    channel_suffix = district_channel_suffix.get(district_name)
    if channel_suffix is None:
        return

    channel = find_channel_by_suffix(guild, channel_suffix)
    if channel is None:
        return

    embed = make_district_embed(district_name)

    msg_id = district_panel_ids.get(district_name)
    if msg_id is None:
        msg = await channel.send(embed=embed)
        district_panel_ids[district_name] = msg.id
    else:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            district_panel_ids[district_name] = msg.id


# ----------------------------------------
# 📌 Commande /comptoir
# ----------------------------------------

@tree.command(name="comptoir", description="Met à jour les jauges des quartiers.")
@app_commands.describe(
    quartier="Choisissez le quartier à modifier.",
    jauge="Quelle jauge voulez-vous modifier ?",
    valeur="Valeur de la jauge (0 à 5).",
)
@app_commands.choices(
    quartier=[
        app_commands.Choice(name="Méhumide", value="Méhumide"),
        app_commands.Choice(name="Pointe du Crochet", value="Pointe du Crochet"),
        app_commands.Choice(name="Voie du Marin", value="Voie du Marin"),
        app_commands.Choice(name="Haut quartier", value="Haut quartier"),
        app_commands.Choice(name="Marché des Alizées", value="Marché des Alizées"),
        app_commands.Choice(name="Port principal", value="Port principal"),
    ],
    jauge=[
        app_commands.Choice(name="Humeur", value="Humeur"),
        app_commands.Choice(name="Tension", value="Tension"),
        app_commands.Choice(name="Activité", value="Activité"),
        app_commands.Choice(name="Menaces", value="Menaces"),
    ],
)
async def comptoir(
    interaction: discord.Interaction,
    quartier: app_commands.Choice[str],
    jauge: app_commands.Choice[str],
    valeur: int,
):
    if not 0 <= valeur <= MAX_JAUGE:
        await interaction.response.send_message(
            "❌ La valeur doit être comprise entre 0 et 5.", ephemeral=True
        )
        return

    district_name = quartier.value
    gauge_name = jauge.value

    # Mise à jour des données en mémoire
    districts[district_name][gauge_name] = valeur

    # Mise à jour des panneaux
    if interaction.guild is not None:
        await update_global_panel(interaction.guild)
        await update_district_panel(interaction.guild, district_name)

    # Petit retour sympa
    await interaction.response.send_message(
        f"✨ **Jauge mise à jour !**\n"
        f"Quartier **{district_name}** – **{gauge_name}** → {render_gauge(valeur)}",
        ephemeral=True,
    )


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
