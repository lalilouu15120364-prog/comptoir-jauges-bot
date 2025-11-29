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
# 🎚️ Les jauges du Comptoir (détaillées)
# ----------------------------------------
# Pour chaque quartier : 4 jauges + un texte d'événement
DEFAULT_EVENT = "Aucun événement enregistré pour le moment."

districts = {
    "Méhumide": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
    "Pointe du Crochet": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
    "Voie des Marins": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
    "Haut quartier": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
    "Marché des Alizées": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
    "Port principal": {
        "humeur": 0,
        "tension": 0,
        "activite": 0,
        "menaces": 0,
        "evenement": DEFAULT_EVENT,
    },
}

MAX_JAUGE = 5


# ----------------------------------------
# 🔧 Fonction utilitaire pour afficher une jauge
# ----------------------------------------
def render_gauge(value: int) -> str:
    value = max(0, min(MAX_JAUGE, value))
    filled = "■" * value
    empty = "□" * (MAX_JAUGE - value)
    return f"{filled}{empty} {value}/{MAX_JAUGE}"


# ----------------------------------------
# 🟩 PANNEAU GLOBAL (tableau complet dans un embed)
# ----------------------------------------
global_panel_message_id = None   # rempli automatiquement si panneau créé


async def update_global_panel(channel: discord.TextChannel):
    """Met à jour le panneau global détaillé dans un message unique."""
    global global_panel_message_id

    lines = []

    for name, data in districts.items():
        lines.append(f"__**{name}**__")
        lines.append(f"Humeur : {render_gauge(data['humeur'])}")
        lines.append(f"Tension : {render_gauge(data['tension'])}")
        lines.append(f"Activité : {render_gauge(data['activite'])}")
        lines.append(f"Menaces : {render_gauge(data['menaces'])}")
        lines.append("")  # ligne vide
        lines.append("Dernier événement :")
        lines.append(data["evenement"])
        lines.append("")  # séparation entre quartiers

    description = "\n".join(lines)

    embed = discord.Embed(
        title="État détaillé des quartiers de Boralus",
        description=description,
        color=discord.Color.gold(),
    )

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


# ----------------------------------------
# 📌 Slash Command : /comptoir
# ----------------------------------------
@tree.command(name="comptoir", description="Met à jour les jauges détaillées d'un quartier.")
@app_commands.describe(
    quartier="Choisissez le quartier à modifier.",
    jauge="Choisissez la jauge à mettre à jour.",
    valeur="Valeur de la jauge (0 à 5).",
    evenement="(Optionnel) Dernier événement à afficher pour ce quartier."
)
@app_commands.choices(quartier=[
    app_commands.Choice(name="Méhumide", value="Méhumide"),
    app_commands.Choice(name="Pointe du Crochet", value="Pointe du Crochet"),
    app_commands.Choice(name="Voie des Marins", value="Voie des Marins"),
    app_commands.Choice(name="Haut quartier", value="Haut quartier"),
    app_commands.Choice(name="Marché des Alizées", value="Marché des Alizées"),
    app_commands.Choice(name="Port principal", value="Port principal"),
])
@app_commands.choices(jauge=[
    app_commands.Choice(name="Humeur", value="humeur"),
    app_commands.Choice(name="Tension", value="tension"),
    app_commands.Choice(name="Activité", value="activite"),
    app_commands.Choice(name="Menaces", value="menaces"),
])
async def comptoir(
    interaction: discord.Interaction,
    quartier: app_commands.Choice[str],
    jauge: app_commands.Choice[str],
    valeur: int,
    evenement: str | None = None,
):
    if not 0 <= valeur <= MAX_JAUGE:
        await interaction.response.send_message("❌ La valeur doit être entre 0 et 5.", ephemeral=True)
        return

    data = districts[quartier.value]
    data[jauge.value] = valeur

    if evenement:
        data["evenement"] = evenement

    # Confirmation côté utilisateur
    await interaction.response.send_message(
        f"✨ **Jauge mise à jour !**\n"
        f"{quartier.value} · **{jauge.name}** → {render_gauge(valeur)}",
        ephemeral=True,
    )

    # mise à jour du panneau global si un salon a été défini
    panel_channel = discord.utils.get(interaction.guild.channels, name="jauges-comptoir")
    if panel_channel:
        await update_global_panel(panel_channel)


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
