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
# 🎚️ Les jauges du Comptoir
# ----------------------------------------
districts = {
    "Méhumide": 0,
    "Pointe du Crochet": 0,
    "Voie des Marins": 0,
    "Haut quartier": 0,
    "Marché des Alizées": 0,
    "Port principal": 0,
}

MAX_JAUGE = 5


# ----------------------------------------
# 🔧 Fonction utilitaire pour afficher les jauges
# ----------------------------------------
def render_gauge(value: int) -> str:
    filled = "■" * value
    empty = "□" * (MAX_JAUGE - value)
    return filled + empty


# ----------------------------------------
# 🟩 MESSAGE GLOBAL AUTOMATIQUE (panneau fixe)
# ----------------------------------------
global_panel_message_id = None   # rempli automatiquement si panneau créé


async def update_global_panel(channel: discord.TextChannel):
    """Met à jour le panneau global dans un message unique."""
    global global_panel_message_id

    panel_text = "__**État des quartiers de Boralus**__\n\n"
    for name, val in districts.items():
        panel_text += f"**{name}** : {render_gauge(val)}\n"

    if global_panel_message_id is None:
        msg = await channel.send(panel_text)
        global_panel_message_id = msg.id
    else:
        try:
            msg = await channel.fetch_message(global_panel_message_id)
            await msg.edit(content=panel_text)
        except discord.NotFound:
            msg = await channel.send(panel_text)
            global_panel_message_id = msg.id


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
async def comptoir(interaction: discord.Interaction, quartier: app_commands.Choice[str], valeur: int):
    if not 0 <= valeur <= MAX_JAUGE:
        await interaction.response.send_message("❌ La valeur doit être entre 0 et 5.", ephemeral=True)
        return

    districts[quartier.value] = valeur

    await interaction.response.send_message(
        f"✨ **Jauge mise à jour !**\n"
        f"{quartier.value} → {render_gauge(valeur)}"
    )

    # mise à jour du panneau si un salon a été défini
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
