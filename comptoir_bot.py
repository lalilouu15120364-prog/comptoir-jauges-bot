import os
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

import discord
from discord.ext import commands
from discord import app_commands

# =========================
# Mini serveur HTTP pour Render (Web Service gratuit)
# =========================

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_http_server():
    """Lance un mini serveur HTTP en arrière-plan pour faire plaisir a Render."""
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


# =========================
# Configuration de base
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

GAUGES_FILE = "gauges.json"

# IDs de salons (les tiens)
CHANNEL_IDS = {
    "global_panel": 1444120310142996511,     # #jauges-comptoir

    "mechumide": 1443595233664438336,        # #🏠-méchumide
    "pointe_du_crochet": 1443595578171982037,# #⚓-pointe-du-crochet
    "alizes": 1443595687433605230,           # #🐚-alizés
    "voie_du_marin": 1443595825023553596,    # #⛵-voie-du-marin
    "haut_quartier": 1443595958343696599,    # #👑-haut-quartier
    "grand_port": 1443596212690354186,       # #🚢-grand-port
}

# Quartiers
QUARTERS = {
    "mechumide": {"label": "Méchumide", "emoji": "🏠"},
    "pointe_du_crochet": {"label": "Pointe du Crochet", "emoji": "⚓"},
    "alizes": {"label": "Alizés", "emoji": "🐚"},
    "voie_du_marin": {"label": "Voie du Marin", "emoji": "⛵"},
    "haut_quartier": {"label": "Haut Quartier", "emoji": "👑"},
    "grand_port": {"label": "Grand Port", "emoji": "🚢"},
}

# Types de jauges
GAUGE_KEYS = {
    "humeur": "Humeur",
    "tension": "Tension",
    "activite": "Activité",
    "menaces": "Menaces",
}

DEFAULT_GAUGE_VALUE = 0


# =========================
# Utilitaires de jauges
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
    except Exception:
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

intents = discord.Intents.default()  # pas de message_content

class ComptoirBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.gauges: Dict[str, Dict[str, int]] = load_gauges()

        self.global_panel_message_id: Optional[int] = None
        self.quarter_panel_message_ids: Dict[str, Optional[int]] = {
            k: None for k in QUARTERS.keys()
        }

    async def setup_hook(self):
        self.tree.add_command(comptoir)

    async def on_ready(self):
        print(f"[OK] Connecté en tant que {self.user}")
        print("Initialisation des panneaux...")
        await self.ensure_panels_exist()
        await self.tree.sync()
        print("[OK] Panneaux prêts et commandes synchronisées.")

    # =========================
    # Panneaux
    # =========================

    async def ensure_panels_exist(self):
        await self.ensure_global_panel()
        await self.ensure_quarter_panels()

    async def ensure_global_panel(self):
        channel_id = CHANNEL_IDS["global_panel"]
        channel = self.get_channel(channel_id)

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
            channel_id = CHANNEL_IDS[q_key]
            channel = self.get_channel(channel_id)

            if not isinstance(channel, discord.TextChannel):
                print(f"[WARN] Salon introuvable pour {q_key}")
                continue

            header = f"**{QUARTERS[q_key]['emoji']} {QUARTERS[q_key]['label']} — État du quartier**"
            found_id: Optional[int] = None

            async for msg in channel.history(limit=50):
                if msg.author.id == self.user.id and msg.content.startswith(header):
                    found_id = msg.id
                    break

            if found_id is None:
                m = await channel.send(self.build_quarter_panel_content(q_key))
                self.quarter_panel_message_ids[q_key] = m.id
            else:
                self.quarter_panel_message_ids[q_key] = found_id
                await self.update_quarter_panel(q_key)

    # =========================
    # Construction du contenu
    # =========================

    def build_global_panel_content(self) -> str:
        lines = [
            "**Panneau général du Comptoir**",
            "_État global des quartiers de Boralus._\n",
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
    # Mise à jour des panneaux
    # =========================

    async def update_global_panel(self):
        channel_id = CHANNEL_IDS["global_panel"]
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            print("[WARN] Impossible de mettre à jour le panneau global.")
            return

        if self.global_panel_message_id is None:
            await self.ensure_global_panel()
            return

        try:
            msg = await channel.fetch_message(self.global_panel_message_id)
            await msg.edit(content=self.build_global_panel_content())
        except discord.NotFound:
            m = await channel.send(self.build_global_panel_content())
            self.global_panel_message_id = m.id

    async def update_quarter_panel(self, q_key: str):
        channel_id = CHANNEL_IDS[q_key]
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            print(f"[WARN] Impossible de mettre à jour le panneau pour {q_key}.")
            return

        msg_id = self.quarter_panel_message_ids.get(q_key)
        if msg_id is None:
            m = await channel.send(self.build_quarter_panel_content(q_key))
            self.quarter_panel_message_ids[q_key] = m.id
            return

        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(content=self.build_quarter_panel_content(q_key))
        except discord.NotFound:
            m = await channel.send(self.build_quarter_panel_content(q_key))
            self.quarter_panel_message_ids[q_key] = m.id


# =========================
# Instanciation du bot
# =========================

bot = ComptoirBot()

# =========================
# Slash command /comptoir
# =========================

QUARTIER_CHOICES = [
    app_commands.Choice(name=f"{q['emoji']} {q['label']}", value=k)
    for k, q in QUARTERS.items()
]

JAUGE_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in GAUGE_KEYS.items()
]

@bot.tree.command(name="comptoir", description="Met à jour une jauge d'un quartier.")
@app_commands.choices(quartier=QUARTIER_CHOICES, jauge=JAUGE_CHOICES)
@app_commands.describe(
    quartier="Choisis un quartier",
    jauge="Choisis une jauge",
    valeur="Valeur (0 à 5)",
)
async def comptoir(
    interaction: discord.Interaction,
    quartier: app_commands.Choice[str],
    jauge: app_commands.Choice[str],
    valeur: app_commands.Range[int, 0, 5],
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur le serveur.",
            ephemeral=True,
        )
        return

    bot.gauges = load_gauges()
    bot.gauges[quartier.value][jauge.value] = int(valeur)
    save_gauges(bot.gauges)

    await bot.update_global_panel()
    await bot.update_quarter_panel(quartier.value)

    q_label = QUARTERS[quartier.value]["label"]
    g_label = GAUGE_KEYS[jauge.value]
    bar = render_bar(int(valeur))

    await interaction.response.send_message(
        f"✨ Jauge mise à jour ! Quartier **{q_label}** → **{g_label}** : `{bar} {valeur}/5`",
        ephemeral=True,
    )


# =========================
# Lancement du bot
# =========================

def main():
    if not TOKEN:
        print("ERREUR : la variable DISCORD_TOKEN est manquante.")
        return

    # On lance le mini serveur HTTP pour Render (Web Service)
    start_http_server()

    # Puis on lance le bot Discord
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
