import os
import json
import asyncio
from typing import Dict, Any

import discord
from discord.ext import commands
from discord import app_commands

# =========================
# Configuration de base
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

# Tes IDs de salons Discord (remplis)
CHANNEL_IDS = {
    "global_panel": 1444120310142996511,     # #jauges-comptoir

    "mechumide": 1443595233664438336,        # #🏠-méchumide
    "pointe_du_crochet": 1443595578171982037,# #⚓-pointe-du-crochet
    "alizes": 1443595687433605230,           # #🐚-alizés
    "voie_du_marin": 1443595825023553596,    # #⛵-voie-du-marin
    "haut_quartier": 1443595958343696599,    # #👑-haut-quartier
    "grand_port": 1443596212690354186,       # #🚢-grand-port
}

GAUGES_FILE = "gauges.json"

# Définition des quartiers et jauges
QUARTERS = {
    "mechumide": {"label": "Méchumide", "emoji": "🏠"},
    "pointe_du_crochet": {"label": "Pointe du Crochet", "emoji": "⚓"},
    "alizes": {"label": "Alizés", "emoji": "🐚"},
    "voie_du_marin": {"label": "Voie du Marin", "emoji": "⛵"},
    "haut_quartier": {"label": "Haut Quartier", "emoji": "👑"},
    "grand_port": {"label": "Grand Port", "emoji": "🚢"},
}

GAUGE_KEYS = {
    "humeur": "Humeur",
    "tension": "Tension",
    "activite": "Activité",
    "menaces": "Menaces",
}

DEFAULT_GAUGE_VALUE = 0

# =========================
# Utilitaires jauges
# =========================

def render_bar(value: int, max_value: int = 5) -> str:
    value = max(0, min(max_value, int(value)))
    return "■" * value + "□" * (max_value - value)

def default_gauges() -> Dict[str, Dict[str, int]]:
    return {
        q: {k: DEFAULT_GAUGE_VALUE for k in GAUGE_KEYS.keys()}
        for q in QUARTERS.keys()
    }

def load_gauges() -> Dict[str, Dict[str, int]]:
    if not os.path.exists(GAUGES_FILE):
        data = default_gauges()
        save_gauges(data)
        return data

    try:
        with open(GAUGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = default_gauges()
        save_gauges(data)
        return data

    base = default_gauges()
    for q, gauges in base.items():
        data.setdefault(q, {})
        for g, v in gauges.items():
            data[q].setdefault(g, v)

    save_gauges(data)
    return data

def save_gauges(data: Dict[str, Dict[str, int]]) -> None:
    with open(GAUGES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =========================
# Bot principal
# =========================

intents = discord.Intents.default()

class ComptoirBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.gauges = load_gauges()

        self.global_panel_message_id = None
        self.quarter_panel_message_ids = {k: None for k in QUARTERS.keys()}

    async def setup_hook(self):
        self.tree.add_command(comptoir)

    async def on_ready(self):
        print(f"[OK] Connecté en tant que {self.user}")
        await self.ensure_panels_exist()
        await self.tree.sync()
        print("[OK] Commandes synchronisées.")

    # =========================
    # Panneaux
    # =========================

    async def ensure_panels_exist(self):
        await self.ensure_global_panel()
        await self.ensure_quarter_panels()

    async def ensure_global_panel(self):
        channel = self.get_channel(CHANNEL_IDS["global_panel"])
        if not isinstance(channel, discord.TextChannel):
            print("[WARN] Salon global introuvable.")
            return

        marker = "**Panneau général du Comptoir**"

        async for msg in channel.history(limit=50):
            if msg.author.id == self.user.id and msg.content.startswith(marker):
                self.global_panel_message_id = msg.id
                break

        if self.global_panel_message_id is None:
            m = await channel.send(self.build_global_panel_content())
            self.global_panel_message_id = m.id
        else:
            await self.update_global_panel()

    async def ensure_quarter_panels(self):
        for q_key in QUARTERS.keys():
            channel = self.get_channel(CHANNEL_IDS[q_key])
            if not isinstance(channel, discord.TextChannel):
                print(f"[WARN] Salon introuvable pour {q_key}")
                continue

            header = f"**{QUARTERS[q_key]['emoji']} {QUARTERS[q_key]['label']} — État du quartier**"

            msg_id = None
            async for msg in channel.history(limit=50):
                if msg.author.id == self.user.id and msg.content.startswith(header):
                    msg_id = msg.id
                    break

            if msg_id is None:
                m = await channel.send(self.build_quarter_panel_content(q_key))
                self.quarter_panel_message_ids[q_key] = m.id
            else:
                self.quarter_panel_message_ids[q_key] = msg_id
                await self.update_quarter_panel(q_key)

    # =========================
    # Construction contenu
    # =========================

    def build_global_panel_content(self) -> str:
        lines = [
            "**Panneau général du Comptoir**",
            "_État global des quartiers de Boralus._\n"
        ]

        for q_key, q in QUARTERS.items():
            data = self.gauges[q_key]
            lines.append(f"{q['emoji']} **{q['label']}**")
            for g_key, g_label in GAUGE_KEYS.items():
                v = data[g_key]
                lines.append(f"• {g_label} : `{render_bar(v)} {v}/5`")
            lines.append("")

        return "\n".join(lines)

    def build_quarter_panel_content(self, q_key: str) -> str:
        q = QUARTERS[q_key]
        data = self.gauges[q_key]

        lines = [f"**{q['emoji']} {q['label']} — État du quartier**\n"]

        for g_key, g_label in GAUGE_KEYS.items():
            v = data[g_key]
            lines.append(f"• {g_label} : `{render_bar(v)} {v}/5`")

        return "\n".join(lines)

    # =========================
    # Mise à jour panneaux
    # =========================

    async def update_global_panel(self):
        channel = self.get_channel(CHANNEL_IDS["global_panel"])
        if not channel or not self.global_panel_message_id:
            return

        try:
            msg = await channel.fetch_message(self.global_panel_message_id)
            await msg.edit(content=self.build_global_panel_content())
        except discord.NotFound:
            m = await channel.send(self.build_global_panel_content())
            self.global_panel_message_id = m.id

    async def update_quarter_panel(self, q_key: str):
        channel = self.get_channel(CHANNEL_IDS[q_key])
        msg_id = self.quarter_panel_message_ids.get(q_key)

        if not channel:
            return

        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(content=self.build_quarter_panel_content(q_key))
        except:
            m = await channel.send(self.build_quarter_panel_content(q_key))
            self.quarter_panel_message_ids[q_key] = m.id

bot = ComptoirBot()

# =========================
# Slash command /comptoir
# =========================

QUARTIER_CHOICES = [
    app_commands.Choice(name=f"{q['emoji']} {q['label']}", value=k)
    for k, q in QUARTERS.items()
]

JAUGE_CHOICES = [
    app_commands.Choice(name=l, value=k)
    for k, l in GAUGE_KEYS.items()
]

@bot.tree.command(name="comptoir", description="Met à jour une jauge d'un quartier.")
@app_commands.choices(quartier=QUARTIER_CHOICES, jauge=JAUGE_CHOICES)
@app_commands.describe(
    quartier="Choisis un quartier",
    jauge="Choisis une jauge",
    valeur="Valeur (0 à 5)"
)
async def comptoir(interaction: discord.Interaction,
                   quartier: app_commands.Choice[str],
                   jauge: app_commands.Choice[str],
                   valeur: app_commands.Range[int, 0, 5]):

    bot.gauges = load_gauges()
    bot.gauges[quartier.value][jauge.value] = int(valeur)
    save_gauges(bot.gauges)

    await bot.update_global_panel()
    await bot.update_quarter_panel(quartier.value)

    await interaction.response.send_message(
        f"✨ Jauge mise à jour ! Quartier **{QUARTERS[quartier.value]['label']}** → "
        f"**{GAUGE_KEYS[jauge.value]}** : `{render_bar(valeur)} {valeur}/5`",
        ephemeral=True
    )

# =========================
# Lancer le bot
# =========================

if __name__ == "__main__":
    if not TOKEN:
        print("ERREUR : la variable DISCORD_TOKEN est manquante sur Render.")
    else:
        bot.run(TOKEN)
