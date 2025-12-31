import discord
import os
import json
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv

from keep_alive import server_on

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

class NameModal(ui.Modal, title='กรุณาใส่ชื่อของคุณ'):
    name_input = ui.TextInput(
        label='ชื่อ',
        placeholder='ใส่ชื่อที่นี่...',
        min_length=1,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        log_channel_id = config.get('log_channel_id')
        verify_role_id = config.get('verify_role_id')
        
        role_status = "ไม่ได้ตั้งค่าระบบยศ"
        if verify_role_id:
            role = interaction.guild.get_role(int(verify_role_id))
            if role:
                try:
                    await interaction.user.add_roles(role)
                    role_status = f"เพิ่มยศ {role.name} สำเร็จ"
                except Exception:
                    role_status = f"เพิ่มยศไม่สำเร็จ (ขาดสิทธิ์)"
            else:
                role_status = "ไม่พบยศที่ตั้งค่าไว้"

        if log_channel_id:
            log_channel = interaction.client.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="บันทึกข้อมูลและปรับปรุงสถานะ", color=discord.Color.green())
                embed.add_field(name="ชื่อที่กรอก", value=self.name_input.value, inline=False)
                embed.add_field(name="ผู้ใช้", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                embed.add_field(name="สถานะยศ", value=role_status, inline=True)
                await log_channel.send(embed=embed)

        await interaction.response.send_message(f"ลงทะเบียนสำเร็จ! (ชื่อ: {self.name_input.value}, {role_status})", ephemeral=True)



class SetupView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='ลงทะเบียน', style=discord.ButtonStyle.primary, custom_id='setup_name_button')
    async def name_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(NameModal())

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.reactions = True
        
        super().__init__(
            command_prefix='.',
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        self.add_view(SetupView()) # Persistent view
        await self.tree.sync()
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("Command tree synced.")
        print("------")

    async def on_ready(self):
        pass

bot = MyBot()

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return

    guild = bot.get_guild(payload.guild_id)
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    if message.embeds:
        footer_text = message.embeds[0].footer.text
        if footer_text and "Role ID:" in footer_text:
            role_id = int(footer_text.split("Role ID: ")[1].split(" |")[0])
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            if role and member:
                await member.add_roles(role)

# --- 3. ส่วนตรวจจับการเอาอิโมจิออก (ถอนยศ) ---
@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    if message.embeds:
        footer_text = message.embeds[0].footer.text
        if footer_text and "Role ID:" in footer_text:
            role_id = int(footer_text.split("Role ID: ")[1].split(" |")[0])
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            if role and member:
                await member.remove_roles(role)

@bot.tree.command(name="setup", description="ส่งปุ่มลงทะเบียนไปยังห้องที่กำหนด")
@app_commands.describe(channel="ห้องที่ต้องการส่งปุ่ม")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="ระบบลงทะเบียน",
        description="คลิกปุ่มด้านล่างเพื่อใส่ชื่อของคุณ",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed, view=SetupView())
    await interaction.response.send_message(f"ส่งปุ่มไปที่ {channel.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="setlogs", description="ตั้งค่าห้องสำหรับบันทึก Log")
@app_commands.describe(channel="ห้องที่ต้องการใช้บันทึก Log")
async def setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config['log_channel_id'] = channel.id
    save_config(config)
    await interaction.response.send_message(f"ตั้งค่า Log Channel เป็น {channel.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="set_verify_role", description="ตั้งค่ายศที่จะได้รับเมื่อลงทะเบียนสำเร็จ")
@app_commands.describe(role="ยศที่ต้องการมอบให้")
async def set_verify_role(interaction: discord.Interaction, role: discord.Role):
    config = load_config()
    config['verify_role_id'] = role.id
    save_config(config)
    await interaction.response.send_message(f"ตั้งค่ายศเป็น {role.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="setup_rolegiver", description="ส่งระบบรับยศเพิ่มเติม")
@app_commands.describe(role="ยศที่ต้องการจะให้", emoji="อิโมจิที่ต้องการ")
async def setup_rolegiver(interaction: discord.Interaction, role: discord.Role, emoji: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ เฉพาะผู้ดูแลเท่านั้นที่ใช้งานได้", ephemeral=True)

    embed = discord.Embed(
        title="📝 ระบบรับยศเพิ่มเติม",
        description=(
            f"ยินดีต้อนรับสู่ระบบจัดการยศเอง **{interaction.guild.name}**\n\n"
            f"ขณะนี้คุณสามารถรับยศ: {role.mention} ได้ด้วยตนเอง\n"
            "-------------------------------------------\n"
            f"📑 **วิธีการ:** กดอิโมจิ {emoji} ด้านล่างนี้\n"
            "📊 **สถานะ** กดเพื่อรับยศ / กดเพื่อถอนยศ\n"
            "-------------------------------------------\n"
        ),
        color=0x2b2d31
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Role ID: {role.id} | พัฒนาโดย BMT-Organization")

    await interaction.response.send_message(f"✅ ส่งระบบรับยศ {role.name} เรียบร้อยแล้ว!", ephemeral=True)

    message = await interaction.channel.send(embed=embed)

    try:
        await interaction.add_reactioh(emoji)
    except:
        await interaction.followup.send("⚠️ บอทไม่สามารถใส่อิโมจิได้ โปรดใช้อิโมจิมาตรฐานหรืออิโมจิจากเซิร์ฟเวอร์นี้", ephemeral=True)

server_on()

if __name__ == "__main__":

    try:
        if TOKEN:
            bot.run(TOKEN)
        else:
            print("Error: DISCORD_TOKEN not found in .env file.")
    except Exception as e:
        print(f"Error: {e}")
