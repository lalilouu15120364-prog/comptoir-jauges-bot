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
# 📍 Configuration des quartiers
# ----------------------------------------
# id interne : {
#   "name": nom pour l'affichage,
#   "channel": nom du salon dédié
# }
DISTRICTS = {
    "mechumide": {
        "name": "Méchumide",
        "channel": "méchumide",
    },
    "pointe_du_crochet": {
        "name": "Pointe du Crochet",
        "channel": "pointe-du-crochet",
    },
    "voie_des_marins": {
        "name": "Voie du marin",
        "channel": "voie-du-marin",
    },
    "haut_quartier": {
        "name": "Haut quartier",
        "channel": "haut-quartier",
    },
    "marche_des_alizees": {
        "name": "Marché des Alizées",
        "channel": "alizés",
    },
    "port_principal": {
        "name": "Port principal",
        "channel": "grand-port",
    },
}

GAUGES = ["humeur", "tension", "activité", "menaces"]
MAX_JAUGE = 5

# ----------------------------------------
# 🧠 Données en mémoire
# districts_state[district_id]["gauges"][gauge] = valeur 0–5
# districts_state[district_id]["event"] = texte ou None
# ----------------------------------------
districts_state = {}
for district_id in DISTRICTS.keys():
    districts_state[district_id] = {
        "gauges": {g: 0 for g in GAUGES},
        "event": None,
    }

# id du panneau global (un seul message)
global_panel_message_id: int | None = None
# id des panneaux individuels : {district_id: message_id}
district_panel_message_ids: dict[str, int] = {}

# ----------------------------------------
# 🔧 Rendu des jauges
# ----------------------------------------
def render_gauge(value: int) -> str:
    value = max(0, min(MAX_JAUGE, value))
    filled = "■" * value
    empty = "□" * (MAX_JAUGE - value)
    return f"{filled}{empty} {value}/{MAX_JAUGE}"


def make_global_embed() -> discord.Embed:
    embed = discord.Embed(
        title="État général de Boralus",
        description="Résumé des quartiers du Comptoir.",
        colour=discord.Colour.gold(),
    )

    for district_id, cfg in DISTRICTS.items():
        state = districts_state[district_id]
        lines = []
        for gauge in GAUGES:
            value = state["gauges"][gauge]
            lines.append(f"**{gauge.capitalize()}** : {render_gauge(value)}")

        event_text = state["event"] or "Aucun événement enregistré pour le moment."
        lines.append(f"\n**Dernier événement :**\n{event_text}")

        embed.add_field(
            name=cfg["name"],
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text="Utilisez /comptoir pour mettre à jour les jauges.")
    return embed


def make_district_embed(district_id: str) -> discord.Embed:
    cfg = DISTRICTS[district_id]
    state = districts_state[district_id]

    embed = discord.Embed(
        title=f"Quartier : {cfg['name']}",
        colour=discord.Colour.blue(),
    )

    for gauge in GAUGES:
        value = state["gauges"][gauge]
        embed.add_field(
            name=gauge.capitalize(),
            value=render_gauge(value),
            inline=True,
        )

    event_text = state["event"] or "Aucun événement enregistré pour le moment."
    embed.add_field(
        name="Dernier événement",
        value=event_text,
        inline=False,
    )

    return embed

# ----------------------------------------
# 🟩 Mise à jour du panneau global
# ----------------------------------------
async def update_global_panel(guild: discord.Guild):
    """
    Met à jour (ou crée) le panneau global dans le salon #jauges-comptoir.
    """
    global global_panel_message_id

    panel_channel = discord.utils.get(guild.channels, name="jauges-comptoir")
    if panel_channel is None or not isinstance(panel_channel, discord.TextChannel):
        return  # pas de salon, on ne fait rien

    embed = make_global_embed()

    # Premier affichage
    if global_panel_message_id is None:
        msg = await panel_channel.send(embed=embed)
        global_panel_message_id = msg.id
    else:
        try:
            msg = await panel_channel.fetch_message(global_panel_message_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            # le message a été supprimé → on en recrée un
            msg = await panel_channel.send(embed=embed)
            global_panel_message_id = msg.id

# ----------------------------------------
# 🟥 Mise à jour d'un panneau de quartier
# ----------------------------------------
async def update_district_panel(guild: discord.Guild, district_id: str):
    """
    Met à jour (ou crée) le panneau individuel dans le salon du quartier.
    """
    cfg = DISTRICTS[district_id]
    channel = discord.utils.get(guild.channels, name=cfg["channel"])
    if channel is None or not isinstance(channel, discord.TextChannel):
        return

    embed = make_district_embed(district_id)

    msg_id = district_panel_message_ids.get(district_id)
    if msg_id is None:
        msg = await channel.send(embed=embed)
        district_panel_message_ids[district_id] = msg.id
    else:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            district_panel_message_ids[district_id] = msg.id

# ----------------------------------------
# 📌 Slash Command : /comptoir
# ----------------------------------------
district_choices = [
    app_commands.Choice(name="Méchumide", value="mechumide"),
    app_commands.Choice(name="Pointe du Crochet", value="pointe_du_crochet"),
    app_commands.Choice(name="Voie des Marins", value="voie_des_marins"),
    app_commands.Choice(name="Haut quartier", value="haut_quartier"),
    app_commands.Choice(name="Marché des Alizées", value="marche_des_alizees"),
    app_commands.Choice(name="Port principal", value="port_principal"),
]

gauge_choices = [
    app_commands.Choice(name="Humeur", value="humeur"),
    app_commands.Choice(name="Tension", value="tension"),
    app_commands.Choice(name="Activité", value="activité"),
    app_commands.Choice(name="Menaces", value="menaces"),
]


@tree.command(name="comptoir", description="Met à jour les jauges des quartiers.")
@app_commands.describe(
    quartier="Choisissez le quartier à modifier.",
    jauge="Choisissez la jauge à modifier.",
    valeur="Valeur de la jauge (0 à 5).",
    evenement="Dernier événement marquant (optionnel).",
)
@app_commands.choices(quartier=district_choices, jauge=gauge_choices)
async def comptoir(
    interaction: discord.Interaction,
    quartier: app_commands.Choice[str],
    jauge: app_commands.Choice[str],
    valeur: int,
    evenement: str | None = None,
):
    # Validation de la valeur
    if not 0 <= valeur <= MAX_JAUGE:
        await interaction.response.send_message(
            "❌ La valeur doit être entre 0 et 5.", ephemeral=True
        )
        return

    district_id = quartier.value
    gauge_key = jauge.value

    # Mise à jour des données
    districts_state[district_id]["gauges"][gauge_key] = valeur
    if evenement:
        districts_state[district_id]["event"] = evenement

    cfg = DISTRICTS[district_id]
    gauge_label = gauge_key.capitalize()

    # Réponse à l'utilisateur
    await interaction.response.send_message(
        f"✨ **Jauge mise à jour !**\n"
        f"Quartier **{cfg['name']}** – {gauge_label} → {render_gauge(valeur)}",
        ephemeral=True,
    )

    # Mise à jour des panneaux (global + individuel)
    if interaction.guild is not None:
        await update_global_panel(interaction.guild)
        await update_district_panel(interaction.guild, district_id)

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
